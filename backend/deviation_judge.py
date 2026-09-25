"""
Compares a dispatcher's reply against the protocol chunk on screen (DeepSeek, JSON mode).
Returns None when DEEPSEEK_API_KEY is missing so the caller can report "not configured".
"""

import json

from structured_extraction import DEEPSEEK_MODEL, _get_client

VERDICTS = ("followed", "deviated")

SYSTEM_PROMPT = """You audit a 911 dispatcher's reply against the protocol instruction that was on \
their screen. Decide whether the reply follows the protocol instruction or deviates from it \
(contradicts it, skips a step, or gives different guidance). Extra reassurance or rephrasing that \
keeps the same guidance is "followed". Respond in JSON only, with two fields:
- verdict: "followed" or "deviated"
- deviationSummary: if deviated, one sentence, at most 25 words, describing how the reply differs \
from the protocol; otherwise an empty string.

EXAMPLE JSON OUTPUT: {"verdict": "deviated", "deviationSummary": "Advised water instead of back blows and abdominal thrusts."}"""


async def judge_deviation(
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
