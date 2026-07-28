"""
KhaiScan -- AI Lore Engine.

Uses Groq (free) -- llama-3.1-8b-instant.

The key difference from naive lore: we write a JOURNALIST-STYLE narrative
using ALL available token context (description, social links, name analysis).
This gives Rick-bot quality output.

Groq free tier: 30,000 tokens/min, 14,400 requests/day, no credit card.
Get your free key at: https://console.groq.com/keys
"""
from __future__ import annotations
import json
import logging
import re
from typing import Optional

import aiohttp
import config
from models import TokenData, LoreResult

logger = logging.getLogger(__name__)

_GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.1-8b-instant"

_SYSTEM_PROMPT = """\
You are a crypto investigative journalist and meme coin analyst. You write \
factual, engaging narratives based ONLY on verifiable information provided to you. \
Never invent facts. Never make price predictions. Never add hype. \
Write in a dry, factual, slightly sardonic tone -- like a journalist covering \
an unusual story, not a crypto influencer pumping a coin."""

_LORE_PROMPT = """\
Analyse this Solana token and write a detailed lore report.

TOKEN DETAILS:
Name: {name}
Symbol: {symbol}
Description: {description}
Website: {website}
Twitter: {twitter}
Telegram: {telegram}

STEP 1 -- NAME ANALYSIS (always do this first):
Break down the token name and symbol for cultural references:
- Crypto personalities: Ansem, Murad, Hsaka, Kookius, Cobie, Gigachad, etc.
- Meme derivatives: "wif" = dogwifhat (WIF), "pepe", "shib", "bonk", "brett", "popcat", etc.
- Combined references: e.g. "Ansemwif" = Ansem (famous Solana whale known for viral market calls) + "wif" suffix from dogwifhat meme
- Real world events, viral moments, animals, people, places
- Internet culture references, TV shows, movies, historical figures

STEP 2 -- NARRATIVE:
Use STEP 1 analysis AND the description (if provided) to write a 2-3 sentence narrative.
If description is empty, base the narrative entirely on name analysis.
Be SPECIFIC and FACTUAL. Name the actual references you found.
Do NOT write vague summaries like "a Solana token with community focus."

STEP 3 -- SCORING:
Score narrative fit, originality, and virality based on your analysis.

Respond ONLY with valid JSON:
{{
  "one_line_summary": "2-3 sentences. Specific and factual. Name the actual cultural references found.",
  "narrative_fit": 7,
  "originality": 6,
  "virality": 8,
  "comparable_tokens": ["TOKEN1", "TOKEN2"],
  "lore_score": 70
}}

Scoring guide:
- narrative_fit (1-10): Fit with current meme coin meta
- originality (1-10): Novel vs copy-paste narrative
- virality (1-10): Shareability and emotional resonance
- lore_score (1-100): Overall narrative quality
- comparable_tokens: 2-3 well-known tokens with similar narratives (uppercase tickers only)

JSON only -- no markdown, no extra text.
"""


async def generate_lore(token_data: TokenData) -> LoreResult:
    """
    Generate lore analysis for a token.

    Uses Groq (free, fast). Always returns a LoreResult -- never raises.
    """
    name        = token_data.name or token_data.symbol or "Unknown"
    symbol      = token_data.symbol or "?"
    description = (token_data.description or "").strip()[:1500]

    # Build rich context from all available metadata
    website  = getattr(token_data, "website", "") or ""
    twitter  = getattr(token_data, "twitter", "") or ""
    telegram = getattr(token_data, "telegram", "") or ""

    if not description and not website and not twitter:
        description = "No description or social links available."

    prompt = _LORE_PROMPT.format(
        name=name,
        symbol=symbol,
        description=description or "Not provided.",
        website=website or "Not provided.",
        twitter=twitter or "Not provided.",
        telegram=telegram or "Not provided.",
    )

    # 1. Try Groq (primary -- free tier)
    if config.GROQ_API_KEY:
        result = await _call_groq(prompt)
        if result:
            return result

    # 2. No AI key configured
    return _fallback_lore(
        "Lore unavailable. Add GROQ_API_KEY to .env (free at console.groq.com/keys)"
    )


# -----------------------------------------------------------------------
# Groq backend (primary)
# -----------------------------------------------------------------------

async def _call_groq(prompt: str) -> Optional[LoreResult]:
    """Call Groq OpenAI-compatible API with system + user messages."""
    payload = {
        "model": _GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.65,
        "max_tokens":  500,
        "response_format": {"type": "json_object"},  # Force JSON output
    }
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _GROQ_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 401:
                    logger.warning("Groq: invalid API key")
                    return None
                if resp.status == 429:
                    logger.warning("Groq: rate limit hit")
                    return None
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Groq: HTTP %s -- %s", resp.status, body[:200])
                    return None
                data = await resp.json()
                raw  = data["choices"][0]["message"]["content"].strip()
                return _parse_lore_json(raw, source="Groq")
    except Exception as exc:
        logger.warning("Groq lore failed: %s", exc)
        return None




# -----------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------

def _parse_lore_json(raw: str, source: str = "") -> Optional[LoreResult]:
    """Parse and validate the AI JSON response into a LoreResult."""
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw.strip())

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("%s returned non-JSON: %s", source, raw[:200])
        return None

    summary = str(parsed.get("one_line_summary", "")).strip()
    if not summary:
        return None

    return LoreResult(
        one_line_summary=summary[:400],
        narrative_fit=_clamp(parsed.get("narrative_fit", 5), 0, 10),
        originality=_clamp(parsed.get("originality", 5), 0, 10),
        virality=_clamp(parsed.get("virality", 5), 0, 10),
        comparable_tokens=[
            str(t).upper() for t in (parsed.get("comparable_tokens") or [])[:3]
        ],
        lore_score=_clamp(parsed.get("lore_score", 50), 0, 100),
    )


def _fallback_lore(reason: str = "") -> LoreResult:
    """Return a neutral lore result when AI is unavailable."""
    return LoreResult(
        one_line_summary=reason or "Narrative analysis unavailable.",
        narrative_fit=0,
        originality=0,
        virality=0,
        comparable_tokens=[],
        lore_score=0,
    )


def _clamp(val, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(val)))
    except (TypeError, ValueError):
        return (lo + hi) // 2
