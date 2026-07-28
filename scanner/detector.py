"""
KhaiScan — Chain detector.

Determines which blockchain a contract address belongs to based on
address format heuristics and DexScreener API data.
"""
from __future__ import annotations
import re
import logging
from typing import Optional
import aiohttp
from api.base import safe_get

logger = logging.getLogger(__name__)

# Solana: base58, 32-44 characters (no 0x prefix, no I/O/l/0 chars)
_SOLANA_RE = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')

# EVM: 0x followed by exactly 40 hex characters
_EVM_RE = re.compile(r'^0x[0-9a-fA-F]{40}$', re.IGNORECASE)

# Contract address extraction from arbitrary text
SOLANA_ADDR_PATTERN = re.compile(r'\b([1-9A-HJ-NP-Za-km-z]{32,44})\b')
EVM_ADDR_PATTERN = re.compile(r'\b(0x[0-9a-fA-F]{40})\b', re.IGNORECASE)


def detect_chain_from_address(address: str) -> Optional[str]:
    """
    Heuristic chain detection from address format alone.

    Returns 'solana', 'evm', or None if unrecognised.
    """
    address = address.strip()
    if _EVM_RE.match(address):
        return "evm"
    if _SOLANA_RE.match(address):
        return "solana"
    return None


async def detect_chain_with_api(
    address: str,
    session: aiohttp.ClientSession,
) -> tuple[str, Optional[str]]:
    """
    Full chain detection: heuristic first, then DexScreener lookup.

    Returns (address, chain_slug) where chain_slug is a DexScreener-compatible
    chain name ('solana', 'ethereum', 'bsc', 'base', etc.) or None if unknown.
    """
    address = address.strip()
    hint = detect_chain_from_address(address)

    if hint == "solana":
        return address, "solana"

    # For EVM, ask DexScreener to identify the exact chain
    data = await safe_get(
        session,
        f"https://api.dexscreener.com/latest/dex/tokens/{address}",
        label="DexScreener/ChainDetect",
    )
    if data and data.get("pairs"):
        # Pick the pair with highest liquidity and read chainId
        pairs = sorted(
            data["pairs"],
            key=lambda p: p.get("liquidity", {}).get("usd") or 0,
            reverse=True,
        )
        chain_id = pairs[0].get("chainId")  # e.g. "ethereum", "bsc", "base"
        if chain_id:
            return address, chain_id

    if hint == "evm":
        logger.warning("EVM address %s not found on DexScreener — chain unknown", address)
        return address, "evm"  # Best guess

    return address, None


def extract_addresses(text: str) -> list[str]:
    """
    Extract all contract addresses from a freeform text message.

    Returns a deduplicated list of addresses (Solana + EVM), longest first.
    """
    found = set()
    for match in EVM_ADDR_PATTERN.finditer(text):
        found.add(match.group(1))
    for match in SOLANA_ADDR_PATTERN.finditer(text):
        addr = match.group(1)
        # Filter out common false positives (short words that match base58)
        if len(addr) >= 32:
            found.add(addr)
    return sorted(found, key=len, reverse=True)
