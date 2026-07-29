"""
KhaiScan -- Fake Volume & Airdrop Detection.

Heuristic-based detection for:
- Fake/wash-traded volume (suspiciously high volume relative to holders/MC)
- Airdropped supply (tokens distributed without buys)
- Suspicious buy patterns (coordinated buys)

No extra API calls needed -- uses data already collected.
"""
from __future__ import annotations
import logging
from typing import Optional
from models import TokenData

logger = logging.getLogger(__name__)


def detect_fakes(td: TokenData) -> dict:
    """
    Analyse token data for signs of fake activity.

    Returns a dict with detection results to merge into TokenData.
    """
    results = {
        "fake_volume_detected": False,
        "fake_volume_reason": "",
        "airdrop_detected": False,
        "airdrop_reason": "",
        "suspicious_buys_detected": False,
        "suspicious_buys_reason": "",
    }

    _check_fake_volume(td, results)
    _check_airdrop(td, results)
    _check_suspicious_buys(td, results)

    return results


def _check_fake_volume(td: TokenData, results: dict):
    """
    Detect wash trading / fake volume.

    Signals:
    - Volume/MC ratio > 5x with < 100 holders = almost certainly fake
    - Volume/MC ratio > 10x regardless = highly suspicious
    - Volume > Liquidity * 20 = volume can't physically be real
    """
    vmr = td.volume_mc_ratio
    vol = td.volume_24h
    liq = td.liquidity_usd
    holders = td.holder_count

    if vmr is not None:
        if vmr > 10:
            results["fake_volume_detected"] = True
            results["fake_volume_reason"] = (
                f"Volume/MC ratio is {vmr:.1f}x -- extremely abnormal. "
                f"Likely wash trading or bot-driven volume."
            )
            return

        if vmr > 5 and holders is not None and holders < 100:
            results["fake_volume_detected"] = True
            results["fake_volume_reason"] = (
                f"Volume/MC is {vmr:.1f}x with only {holders} holders. "
                f"Volume appears artificially inflated."
            )
            return

    if vol is not None and liq is not None and liq > 0:
        vol_liq_ratio = vol / liq
        if vol_liq_ratio > 20:
            results["fake_volume_detected"] = True
            results["fake_volume_reason"] = (
                f"24h volume is {vol_liq_ratio:.0f}x the liquidity pool. "
                f"Physically impossible without wash trading."
            )
            return


def _check_airdrop(td: TokenData, results: dict):
    """
    Detect airdropped supply patterns.

    Signals:
    - Very high holder count relative to market cap (many holders got free tokens)
    - Risk flags mentioning airdrop/distribution
    - High top10 concentration with high holder count = controlled airdrop
    """
    holders = td.holder_count
    mc = td.market_cap

    # Check risk flags for airdrop mentions
    for flag in (td.risk_flags or []):
        flag_lower = flag.lower()
        if any(kw in flag_lower for kw in ("airdrop", "airdropped", "distributed", "mass transfer")):
            results["airdrop_detected"] = True
            results["airdrop_reason"] = f"Risk flag detected: {flag}"
            return

    # Heuristic: tiny market cap but many holders = likely airdropped
    if holders is not None and holders > 0 and mc is not None and mc > 0:
        mc_per_holder = mc / holders
        if mc_per_holder < 0.5 and holders > 500:
            results["airdrop_detected"] = True
            results["airdrop_reason"] = (
                f"${mc_per_holder:.2f} market cap per holder across {holders:,} holders. "
                f"Tokens likely airdropped to inflate holder count."
            )
            return

    # High holder count + high top10 = controlled airdrop
    if (holders is not None and holders > 1000 and
            td.top10_pct is not None and td.top10_pct > 60):
        results["airdrop_detected"] = True
        results["airdrop_reason"] = (
            f"{holders:,} holders but top 10 hold {td.top10_pct:.1f}%. "
            f"Holders likely received airdropped dust amounts."
        )


def _check_suspicious_buys(td: TokenData, results: dict):
    """
    Detect coordinated/suspicious buy patterns.

    Signals:
    - High insider wallet count with low holder count = coordinated launch
    - Bundle % > 20% = significant portion bought in coordinated bundles
    """
    bundle_pct = td.bundle_pct
    insider_count = td.insider_wallet_count
    holders = td.holder_count

    if bundle_pct is not None and bundle_pct > 20:
        results["suspicious_buys_detected"] = True
        results["suspicious_buys_reason"] = (
            f"{bundle_pct:.1f}% of supply acquired through bundled transactions. "
            f"Coordinated buying activity detected."
        )
        return

    if (insider_count is not None and insider_count > 5 and
            holders is not None and 0 < holders < 200):
        insider_ratio = (insider_count / holders) * 100
        if insider_ratio > 10:
            results["suspicious_buys_detected"] = True
            results["suspicious_buys_reason"] = (
                f"{insider_count} insider wallets among {holders} total holders "
                f"({insider_ratio:.0f}%). Coordinated launch detected."
            )
