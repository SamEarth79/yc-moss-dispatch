"""
Client for OpenRouter's Decisions API (Jev). Every Jev call goes through here so request shapes,
timeouts and failure handling live in one place. Requires OPENROUTER_API_KEY in .env; every
function returns None when it is missing or the call fails, so callers keep their fallback path.
"""

import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

JEV_BASE_URL = "https://openrouter.ai/api/alpha"
JEV_MODEL = "typesafe/jev-1.13"
JEV_CONFIDENCE_HIGH = 0.7
JEV_CONFIDENCE_LOW = 0.3
JEV_FOLLOW_THRESHOLD = 0.3
EXTRACTION_TIMEOUT_S = 1.5
JUDGE_TIMEOUT_S = 3.0

_NOUL_QUESTIONS = {
    "weapon": {
        "type": "noul",
        "instructions": "Is a weapon involved in this emergency call?",
        "criteria": {
            "true": "The caller says or strongly implies someone has or used a weapon such as a knife, gun, or blade.",
            "false": "No weapon is mentioned, or the caller says there was no weapon.",
        },
    },
    "unconscious": {
        "type": "noul",
        "instructions": "Is anyone unconscious or unresponsive?",
        "criteria": {
            "true": "Someone is not responding, not answering, collapsed, or not breathing.",
            "false": "Everyone mentioned is awake and responsive.",
        },
    },
    "police": {
        "type": "noul",
        "instructions": "Does this emergency call need the police?",
        "criteria": {
            "true": "The call involves violence, crime, weapons or threats needing police.",
            "false": "No police response is needed.",
        },
    },
    "ems": {
        "type": "noul",
        "instructions": "Does this emergency call need emergency medical services?",
        "criteria": {
            "true": "The call involves an injury or medical emergency needing medical responders.",
            "false": "No medical response is needed.",
        },
    },
    "fire": {
        "type": "noul",
        "instructions": "Does this emergency call need the fire department?",
        "criteria": {
            "true": "The call involves fire, smoke, a gas leak or a rescue needing the fire department.",
            "false": "No fire department response is needed.",
        },
    },
}

_PATIENT_CRITERIA = {"0": "Nobody is hurt or in medical distress."}
_PATIENT_CRITERIA["1"] = "Exactly 1 person is hurt or in medical distress."
_PATIENT_CRITERIA.update({str(n): f"Exactly {n} people are hurt or in medical distress." for n in range(2, 11)})

_PATIENTS_QUESTION = {
    "type": "choice",
    "instructions": "How many people are hurt or in medical distress?",
    "criteria": _PATIENT_CRITERIA,
}

_FOLLOWS_QUESTION = {
    "type": "noul",
    "instructions": "Does the dispatcher's reply give the same guidance as the protocol instruction?",
    "criteria": {
        "true": "The reply tells the caller to do what the protocol instruction says (paraphrasing or added reassurance is fine).",
        "false": "The reply contradicts the protocol, skips its steps, gives different guidance, or does not address it.",
    },
}

_client: AsyncOpenAI | None = None
_client_key: str | None = None


def _get_client() -> AsyncOpenAI | None:
    global _client, _client_key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    if _client is None or _client_key != api_key:
        _client = AsyncOpenAI(api_key=api_key, base_url=JEV_BASE_URL, max_retries=0)
        _client_key = api_key
    return _client


async def _decide(state: dict, questions: dict, timeout_s: float) -> dict | None:
    client = _get_client()
    if client is None:
        return None

    body = {"model": JEV_MODEL, "state": state, "questions": questions}
    try:
        response = await client.post(
            "/decisions",
            body=body,
            cast_to=dict,
            options={"timeout": timeout_s, "max_retries": 0},
        )
    except Exception as exc:
        logger.warning("Jev request failed: %s", type(exc).__name__)
        return None

    answers = response.get("answers") if isinstance(response, dict) else None
    if not isinstance(answers, dict):
        logger.warning("Jev response had no answers object")
        return None
    return answers


def _probability(answer: object) -> float | None:
    if not isinstance(answer, dict) or answer.get("type") != "noul":
        return None
    value = answer.get("noul")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        return None
    return float(value)


def _patients(answer: object) -> tuple[str, float] | None:
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        return None
    choice = answer.get("choice")
    confidence = answer.get("confidence")
    if choice not in _PATIENT_CRITERIA:
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        return None
    return choice, float(confidence)


_EXTRACTION_QUESTIONS = {**_NOUL_QUESTIONS, "patients": _PATIENTS_QUESTION}
EXTRACTION_QUESTION_COUNT = len(_EXTRACTION_QUESTIONS)


async def decide_extraction(text: str) -> dict | None:
    answers = await _decide({"caller_transcript": text}, _EXTRACTION_QUESTIONS, EXTRACTION_TIMEOUT_S)
    if answers is None:
        return None

    result: dict = {}
    for field in _NOUL_QUESTIONS:
        probability = _probability(answers.get(field))
        if probability is not None:
            result[field] = probability
    patients = _patients(answers.get("patients"))
    if patients is not None:
        result["patients"] = patients
    return result


async def decide_follows(
    protocol_chunk_text: str,
    dispatcher_text: str,
    caller_transcript: str,
    reason: str | None,
) -> float | None:
    state = {
        "caller_transcript": caller_transcript,
        "protocol_instruction": protocol_chunk_text,
        "dispatcher_reply": dispatcher_text,
    }
    if reason:
        state["dispatcher_reason"] = reason

    answers = await _decide(state, {"follows_protocol": _FOLLOWS_QUESTION}, JUDGE_TIMEOUT_S)
    if answers is None:
        return None
    return _probability(answers.get("follows_protocol"))
