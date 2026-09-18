"""
Structured field extraction (#5), split by speed:
- rule fields (patients, consciousness, weapons) come from keyword rules in under 1ms —
  these drive the color-coded tiles, where a small LLM was slow and made mistakes;
- LLM fields (headline, injuries) come from DeepSeek (OpenAI-SDK-compatible). Requires
  DEEPSEEK_API_KEY in .env; returns None when it's missing so the rest of the app still runs.
"""

import json
import os
import re

from openai import AsyncOpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"

WEAPON_PATTERN = re.compile(
    r"\b(knife|knives|gun|guns|pistol|handgun|firearm|shotgun|rifle|weapon|weapons|blade|machete|"
    r"bat|razor|axe|shot|shooting|stabbed|stabbing|armed)\b"
)
NO_WEAPON_PATTERN = re.compile(
    r"\b(no weapons?|unarmed|(?:doesn't|does not|don't|didn't|did not) have (?:a |any )?(?:weapon|gun|knife)s?)\b"
)
UNCONSCIOUS_PATTERN = re.compile(
    r"\b(unconscious|unresponsive|not responding|not answering|isn't answering|passed out|"
    r"not breathing|isn't breathing|won't wake|not waking|isn't moving|not moving|collapsed|"
    r"fainted|not awake|isn't awake|not conscious|isn't conscious|not talking|isn't talking)\b"
)
CONSCIOUS_PATTERN = re.compile(
    r"\b(awake|conscious|talking|responsive|breathing|speaking|can speak|alert|answering)\b"
)
NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "2": 2, "3": 3, "4": 4, "5": 5}
MULTI_PATIENT_PATTERN = re.compile(
    r"\b(two|three|four|five|2|3|4|5) (?:people|persons|patients|victims|kids|children|of them|men|women|guys) "
    r"(?:are |were |got )?(?:hurt|injured|down|bleeding|unconscious|not moving|shot|stabbed)\b"
)
EXTRA_PATIENT_PATTERN = re.compile(
    r"\b(?:another|also (?:a|an)|second) (?:person|woman|man|guy|victim|patient|child|kid)\b|\bboth\b"
)
PERSON_PATTERN = re.compile(
    r"\b(he|she|him|her|man|woman|guys?|person|patient|husband|wife|dad|mom|father|mother|son|"
    r"daughter|baby|child|kid|friend|someone|somebody|one of them)\b"
)


def extract_rule_fields(transcript: str) -> dict:
    text = transcript.lower()

    if NO_WEAPON_PATTERN.search(text):
        weapons = False
    elif WEAPON_PATTERN.search(text):
        weapons = True
    else:
        weapons = None

    if UNCONSCIOUS_PATTERN.search(text):
        consciousness = "unconscious"
    elif CONSCIOUS_PATTERN.search(text):
        consciousness = "conscious"
    else:
        consciousness = None

    multi = MULTI_PATIENT_PATTERN.search(text)
    if multi:
        patients = NUMBER_WORDS[multi.group(1)]
    elif EXTRA_PATIENT_PATTERN.search(text):
        patients = 2
    elif PERSON_PATTERN.search(text):
        patients = 1
    else:
        patients = None

    return {"numberOfPatients": patients, "consciousness": consciousness, "weapons": weapons}


SYSTEM_PROMPT = """You label a live 911 call transcript for a dispatcher's screen. The transcript \
may be partial. Respond in JSON only, with two fields:
- whatHappened: 2-4 word incident label (e.g. "stabbing", "choking", "fight"), or null.
- injuries: short phrase listing injuries mentioned, or null.

EXAMPLE INPUT: my dad is choking on food he can't speak and he's turning blue
EXAMPLE JSON OUTPUT: {"whatHappened": "choking", "injuries": null}"""

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI | None:
    global _client
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    if _client is None:
        _client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    return _client


async def extract_llm_fields(transcript: str) -> dict | None:
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
        temperature=0,
        max_tokens=60,
    )
    content = response.choices[0].message.content
    if not content:
        return None
    return json.loads(content)
