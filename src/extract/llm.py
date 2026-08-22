"""LLM eligibility-rule extractor (M1).

Runs against a LOCAL Ollama model by default: free, offline, no API key, and
independent of the Python/PyTorch version because Ollama is a separate process
we reach over HTTP.

Providers are pluggable so the same prompt and parser can be scored against a
hosted model later without touching the pipeline -- that comparison is itself a
result worth reporting ("local 3B vs hosted model, same prompt").

    KISAN_LLM_PROVIDER = ollama (default) | gemini | anthropic
    KISAN_LLM_MODEL    = qwen2.5:3b (default for ollama)

Every response is cached by (provider, model, prompt) hash, so re-running the
full corpus after a crash costs nothing and results stay reproducible.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

import time

import requests

from ..config import CACHE
from ..schema.fields import FIELDS, DType
from ..schema.models import Rule, Operator, SourceSpan

log = logging.getLogger(__name__)

PROVIDER = os.environ.get("KISAN_LLM_PROVIDER", "ollama").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODELS = {
    "ollama": "qwen2.5:3b",
    "gemini": "gemini-3.6-flash",   # 2.0-flash was retired; see _gemini_models()
    "anthropic": "claude-sonnet-5",
}
MODEL = os.environ.get("KISAN_LLM_MODEL", DEFAULT_MODELS.get(PROVIDER, "qwen2.5:3b"))


# ------------------------------------------------------------------ prompt ---
def _field_catalogue() -> str:
    """Render the controlled vocabulary into the prompt.

    Built from FIELDS rather than hardcoded so the prompt cannot drift out of
    sync with the schema -- a drifted prompt produces rules the validator
    silently rejects, which looks like poor model recall.
    """
    lines = []
    for f in FIELDS.values():
        bits = [f"{f.name} ({f.dtype.value}"]
        if f.unit:
            bits.append(f", unit={f.unit}")
        bits.append(")")
        desc = f.description
        if f.dtype is DType.CATEGORICAL and f.allowed:
            allowed = ", ".join(f.allowed[:8]) + ("..." if len(f.allowed) > 8 else "")
            desc += f" [one of: {allowed}]"
        lines.append(f"  - {''.join(bits)}: {desc}")
    return "\n".join(lines)


SYSTEM = """You extract eligibility criteria from Indian government farming \
scheme documents and return them as strict JSON.

You will be given ONE paragraph. Return every condition a FARMER or APPLICANT \
must satisfy to qualify.

CRITICAL RULES:
1. Only use fields from the catalogue below. Never invent a field name.
2. Return ONE condition per rule. "farmers aged 18 to 40" is TWO rules \
(age gte 18, age lte 40).
3. Negation: "must not be a government employee" is \
{"field":"is_govt_employee","op":"eq","value":false,"negated":true} -- \
NOT op "neq".
4. Preference wording ("preference given to", "priority to") means \
"mandatory": false. It affects ranking, not eligibility.
5. Record units VERBATIM. If the text says acres, write "unit":"acre". \
Never convert to hectares yourself.
6. "source" must be the exact substring of the paragraph the rule came from.
7. MOST IMPORTANT: many paragraphs describe administrative procedure -- how \
states remit premium, how insurers are empanelled, cost norms, committee \
structures. These contain NO farmer eligibility criteria. For those, return \
exactly {"rules": []}. Do NOT invent criteria to seem useful.

Return ONLY a JSON object of the form:
{"rules": [{"field": str, "op": str, "value": any, "unit": str|null, \
"negated": bool, "mandatory": bool, "source": str}]}"""

OPERATORS = ", ".join(o.value for o in Operator)

FEWSHOT = [
    (
        "Small and marginal farmers holding up to 2 hectares of cultivable land, "
        "who are not income tax payees, are eligible under the scheme.",
        {"rules": [
            {"field": "farmer_class", "op": "in", "value": ["small", "marginal"],
             "unit": None, "negated": False, "mandatory": True,
             "source": "Small and marginal farmers"},
            {"field": "land_ha", "op": "lte", "value": 2, "unit": "hectare",
             "negated": False, "mandatory": True,
             "source": "holding up to 2 hectares of cultivable land"},
            {"field": "is_income_tax_payer", "op": "eq", "value": False,
             "unit": None, "negated": True, "mandatory": True,
             "source": "who are not income tax payees"},
        ]},
    ),
    (
        "The State Government shall remit the premium subsidy to the empanelled "
        "Insurance Company through the NCIP payment gateway within the stipulated "
        "timelines, failing which interest shall be payable.",
        {"rules": []},
    ),
    (
        "The following categories are excluded from the scheme: income tax payees, "
        "serving or retired government employees, and institutional land holders.",
        {"rules": [
            {"field": "is_income_tax_payer", "op": "eq", "value": False,
             "unit": None, "negated": True, "mandatory": True,
             "source": "income tax payees"},
            {"field": "is_govt_employee", "op": "eq", "value": False,
             "unit": None, "negated": True, "mandatory": True,
             "source": "serving or retired government employees"},
            {"field": "is_institutional_landholder", "op": "eq", "value": False,
             "unit": None, "negated": True, "mandatory": True,
             "source": "institutional land holders"},
        ]},
    ),
    # Added after error analysis: the model scored precision 1.00 but recall
    # 0.12 on `state`, emitting it only 3 times in 26 opportunities. No other
    # example carried a state rule, and few-shot examples teach not just output
    # format but WHICH FIELDS to look for. This one also demonstrates the
    # STATE enum spelling (uppercase, underscored) and residency phrasing,
    # which the corpus writes as "permanent resident of" / "native of".
    (
        "The applicant should be a permanent resident of Madhya Pradesh. "
        "The applicant should be between 18 to 55 years of age. The annual "
        "family income of the applicant should not exceed ₹1,50,000.",
        {"rules": [
            {"field": "state", "op": "eq", "value": "MADHYA_PRADESH",
             "unit": None, "negated": False, "mandatory": True,
             "source": "permanent resident of Madhya Pradesh"},
            {"field": "age", "op": "gte", "value": 18, "unit": "years",
             "negated": False, "mandatory": True,
             "source": "between 18 to 55 years of age"},
            {"field": "age", "op": "lte", "value": 55, "unit": "years",
             "negated": False, "mandatory": True,
             "source": "between 18 to 55 years of age"},
            {"field": "annual_income", "op": "lte", "value": 150000,
             "unit": "INR", "negated": False, "mandatory": True,
             "source": "annual family income of the applicant should not exceed ₹1,50,000"},
        ]},
    ),
    (
        "Preference will be given to women farmers belonging to SC/ST categories "
        "who own at least 0.5 acre of land.",
        {"rules": [
            {"field": "gender", "op": "eq", "value": "female", "unit": None,
             "negated": False, "mandatory": False, "source": "women farmers"},
            {"field": "social_category", "op": "in", "value": ["SC", "ST"],
             "unit": None, "negated": False, "mandatory": False,
             "source": "belonging to SC/ST categories"},
            {"field": "land_ha", "op": "gte", "value": 0.5, "unit": "acre",
             "negated": False, "mandatory": True,
             "source": "own at least 0.5 acre of land"},
        ]},
    ),
]


def build_prompt(text: str) -> str:
    shots = "\n\n".join(
        f"PARAGRAPH:\n{p}\n\nJSON:\n{json.dumps(a, ensure_ascii=False)}"
        for p, a in FEWSHOT
    )
    return (
        f"{SYSTEM}\n\nALLOWED FIELDS:\n{_field_catalogue()}\n\n"
        f"ALLOWED OPERATORS: {OPERATORS}\n\n"
        f"--- EXAMPLES ---\n{shots}\n\n"
        f"--- NOW EXTRACT ---\nPARAGRAPH:\n{text}\n\nJSON:"
    )


# --------------------------------------------------------------- providers ---
def _call_ollama(prompt: str) -> str:
    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            # Deterministic: the gold set must be reproducible, and sampling
            # noise would make the F1 score irreproducible run to run.
            "options": {"temperature": 0.0, "num_predict": 900},
        },
        timeout=300,
    )
    r.raise_for_status()
    return r.json().get("response", "")


# Free tier allows ~15 requests/minute. Pacing at 4.5s keeps us inside it;
# without this the run dies partway through with 429s and you lose the
# un-cached work.
_GEMINI_MIN_INTERVAL = 4.5
_gemini_last = 0.0


def _gemini_models(key: str) -> list[str]:
    """Model ids this key may call, newest-looking first."""
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                         headers={"x-goog-api-key": key}, timeout=30)
        r.raise_for_status()
        names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        return sorted(names, reverse=True)[:12]
    except Exception:
        return []


def _call_gemini(prompt: str) -> str:
    global _gemini_last
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at aistudio.google.com, "
            'then: setx GEMINI_API_KEY "your-key-here"  (and open a new terminal)')

    for attempt in range(4):
        wait = _GEMINI_MIN_INTERVAL - (time.time() - _gemini_last)
        if wait > 0:
            time.sleep(wait)
        _gemini_last = time.time()

        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
            headers={"x-goog-api-key": key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.0,
                                       "responseMimeType": "application/json"}},
            timeout=120,
        )
        if r.status_code == 429:
            back = 10 * (attempt + 1)
            log.warning("gemini rate limit, backing off %ss", back)
            time.sleep(back)
            continue
        if r.status_code == 404:
            # Google retires model ids on its own schedule, so a hardcoded
            # default WILL go stale. List what the key can actually reach
            # rather than making the reader guess.
            available = ", ".join(_gemini_models(key)) or "none listed"
            raise RuntimeError("\n".join([
                f"gemini 404: model {MODEL!r} is unavailable.",
                r.text[:200],
                f"Models this key can use: {available}",
                'Set one with:  setx KISAN_LLM_MODEL "<model-id>"',
            ]))
        if r.status_code >= 400:
            # Surface the API's own message: a wrong model name or an
            # unenabled key both return 400, and the body says which.
            raise RuntimeError(f"gemini {r.status_code}: {r.text[:300]}")
        data = r.json()
        cands = data.get("candidates") or []
        if not cands:
            log.warning("gemini returned no candidates: %s", str(data)[:200])
            return '{"rules": []}'
        return cands[0]["content"]["parts"][0]["text"]

    raise RuntimeError("gemini: rate limited after 4 attempts")


def _call_anthropic(prompt: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 1500, "temperature": 0.0,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


_PROVIDERS = {"ollama": _call_ollama, "gemini": _call_gemini,
              "anthropic": _call_anthropic}


def _call(prompt: str) -> str:
    cache_dir = CACHE.parent / "_llm"
    cache_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(f"{PROVIDER}|{MODEL}|{prompt}".encode()).hexdigest()[:24]
    path = cache_dir / f"{h}.json"
    if path.exists():
        return path.read_text(encoding="utf-8")

    fn = _PROVIDERS.get(PROVIDER)
    if fn is None:
        raise RuntimeError(f"unknown provider {PROVIDER!r}")
    out = fn(prompt)
    path.write_text(out, encoding="utf-8")
    return out


# ------------------------------------------------------------------ parsing ---
def _find_json(raw: str) -> dict[str, Any]:
    """Recover the JSON object from a response that may carry stray prose."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start == -1:
        return {"rules": []}
    depth = 0
    for i, ch in enumerate(raw[start:], start):
        depth += (ch == "{") - (ch == "}")
        if depth == 0:
            try:
                return json.loads(raw[start:i + 1])
            except json.JSONDecodeError:
                return {"rules": []}
    return {"rules": []}


def _span_for(text: str, src: Any) -> SourceSpan | None:
    """Locate the quoted source substring inside the paragraph.

    Models paraphrase or re-space their quotes, so the substring often is not
    found verbatim. When that happens both offsets stay -1 rather than
    computing end from a -1 start, which previously produced spans like
    (-1, 52) that point nowhere and silently corrupt span-level analysis.
    """
    if not isinstance(src, str) or not src:
        return None
    start = text.find(src)
    if start == -1:
        collapsed = " ".join(src.split())
        start = " ".join(text.split()).find(collapsed)
        if start == -1:
            return SourceSpan(text=src, start=-1, end=-1)
    return SourceSpan(text=src, start=start, end=start + len(src))


def extract(text: str) -> list[Rule]:
    """Extract eligibility rules from one paragraph.

    Rules the schema rejects are DROPPED, not repaired. A hallucinated field is
    a model error and must show up as reduced recall -- silently mapping it onto
    a nearby real field would hide exactly what the evaluation exists to expose.
    """
    data = _find_json(_call(build_prompt(text)))
    out: list[Rule] = []
    for item in data.get("rules", []) or []:
        if not isinstance(item, dict):
            continue
        src = item.get("source")
        try:
            rule = Rule(
                field=item.get("field", ""),
                op=item.get("op", "eq"),
                value=item.get("value"),
                unit=item.get("unit"),
                negated=bool(item.get("negated", False)),
                mandatory=bool(item.get("mandatory", True)),
                source=_span_for(text, src),
            )
        except Exception as e:                       # schema violation
            log.debug("dropped invalid rule %s: %s", item, e)
            continue
        out.append(rule)

    # Canonicalise "neq true" into "eq false, negated=true". This is a
    # REPRESENTATION fix, not an accuracy fix: both encode the same condition,
    # and the harness compares exact triples, so leaving two spellings of one
    # fact in the output would understate recall for reasons unrelated to
    # whether the model understood the sentence.
    for r in out:
        if r.op is Operator.NEQ and isinstance(r.value, bool):
            r.op, r.value, r.negated = Operator.EQ, (not r.value), True

    seen, uniq = set(), []
    for r in out:
        k = (r.field, r.op, str(r.value), r.negated)
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq
