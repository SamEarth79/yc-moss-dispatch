"""
Compares a dispatcher's reply against the protocol chunk on screen (DeepSeek, JSON mode).
Returns None when DEEPSEEK_API_KEY is missing so the caller can report "not configured".
"""

import json
import logging
import time

from jev_client import JEV_FOLLOW_THRESHOLD, decide_follows
from structured_extraction import DEEPSEEK_MODEL, _get_client

logger = logging.getLogger(__name__)

VERDICTS = ("followed", "deviated")

SYSTEM_PROMPT = """You audit a 911 dispatcher's reply against the protocol instruction that was on \
their screen. Decide whether the reply follows the protocol instruction or deviates from it \
(contradicts it, skips a step, or gives different guidance). Extra reassurance or rephrasing that \
keeps the same guidance is "followed". Respond in JSON only, with two fields:
- verdict: "followed" or "deviated"
- deviationSummary: if deviated, one sentence, at most 25 words, describing how the reply differs \
from the protocol; otherwise an empty string.

EXAMPLE JSON OUTPUT: {"verdict": "deviated", "deviationSummary": "Advised water instead of back blows and abdominal thrusts."}"""


SUMMARY_SYSTEM_PROMPT = """A 911 dispatcher's reply deviates from the protocol instruction that was on \
their screen. Respond in JSON only, with one field:
- deviationSummary: one sentence, at most 25 words, describing how the reply differs from the protocol.

EXAMPLE JSON OUTPUT: {"deviationSummary": "Advised water instead of back blows and abdominal thrusts."}"""


async def judge_deviation(
    dispatcher_text: str,
    reason: str | None,
    protocol_chunk_text: str,
    caller_transcript: str,
) -> dict | None:
    started = time.monotonic()
    follows_probability = await decide_follows(protocol_chunk_text, dispatcher_text, caller_transcript, reason)
    jev_latency_ms = round((time.monotonic() - started) * 1000, 1)

    if follows_probability is None:
        result = await _judge_with_deepseek(dispatcher_text, reason, protocol_chunk_text, caller_transcript)
        if result is None:
            return None
        logger.info("deviation judged: source=deepseek-fallback verdict=%s", result["verdict"])
        result["devLog"] = [_jev_verdict_entry(jev_latency_ms, "skipped (unavailable), DeepSeek fallback")]
        return result

    if follows_probability >= JEV_FOLLOW_THRESHOLD:
        logger.info("deviation judged: source=jev p_follows=%.3f verdict=followed", follows_probability)
        return {
            "verdict": "followed",
            "deviationSummary": "",
            "devLog": [_jev_verdict_entry(jev_latency_ms, f"P(follows)={follows_probability:.2f} → followed")],
        }

    summary = await _summarize_deviation_with_deepseek(dispatcher_text, reason, protocol_chunk_text)
    if summary is None:
        return None
    logger.info("deviation judged: source=jev p_follows=%.3f verdict=deviated", follows_probability)
    return {
        "verdict": "deviated",
        "deviationSummary": summary,
        "devLog": [_jev_verdict_entry(jev_latency_ms, f"P(follows)={follows_probability:.2f} → deviated")],
    }


def _jev_verdict_entry(latency_ms: float, summary: str) -> dict:
    return {"service": "jev", "callType": "verdict", "latencyMs": latency_ms, "summary": summary}


async def _summarize_deviation_with_deepseek(
    dispatcher_text: str,
    reason: str | None,
    protocol_chunk_text: str,
) -> str | None:
    client = _get_client()
    if client is None:
        return None

    user_message = f"Protocol instruction on screen: {protocol_chunk_text}\nDispatcher reply: {dispatcher_text}"
    if reason:
        user_message += f"\nDispatcher's stated reason: {reason}"

    response = await client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=150,
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Empty judge response")

    summary = json.loads(content).get("deviationSummary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Deviated verdict without a summary")
    return summary.strip()


async def _judge_with_deepseek(
    dispatcher_text: str,
    reason: str | None,
    protocol_chunk_text: str,
    caller_transcript: str,
) -> dict | None:
    client = _get_client()
    if client is None:
        return None

    user_message = (
        f"Caller transcript: {caller_transcript}\n"
        f"Protocol instruction on screen: {protocol_chunk_text}\n"
        f"Dispatcher reply: {dispatcher_text}"
    )
    if reason:
        user_message += f"\nDispatcher's stated reason: {reason}"

    response = await client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=200,
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Empty judge response")

    parsed = json.loads(content)
    verdict = parsed.get("verdict")
    if verdict not in VERDICTS:
        raise ValueError(f"Invalid verdict: {verdict!r}")

    summary = parsed.get("deviationSummary")
    if verdict == "deviated" and (not isinstance(summary, str) or not summary.strip()):
        raise ValueError("Deviated verdict without a summary")

    return {"verdict": verdict, "deviationSummary": summary.strip() if verdict == "deviated" else ""}
