"""
Structured field extraction (#5): parses the live transcript into what/where/who/
weapons/injuries/# of patients via an LLM call — upstream of Moss, its output could
feed the retrieval query text, but today just renders as its own panel. Uses DeepSeek
(OpenAI-SDK-compatible). Requires DEEPSEEK_API_KEY in .env; returns None (caller
renders "not configured") when it's missing so the rest of the app still runs.
"""

import json
import os

from openai import AsyncOpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"

SYSTEM_PROMPT = """You extract structured fields from a live 911 call transcript for a \
dispatcher's screen. The transcript may be partial/incomplete — only fill in fields you \
have actual evidence for; leave others null. Respond in JSON only.

EXAMPLE INPUT: my dad is choking on food he can't speak and he's turning blue
EXAMPLE JSON OUTPUT:
{
  "whatHappened": "choking",
  "location": null,
  "numberOfPatients": 1,
  "consciousness": "conscious",
  "injuries": null,
  "weapons": false
}"""

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI | None:
    global _client
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    if _client is None:
        _client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    return _client


async def extract_structured_fields(transcript: str) -> dict | None:
    client = _get_client()
    if client is None:
        return None

    response = await client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        return None
    return json.loads(content)
