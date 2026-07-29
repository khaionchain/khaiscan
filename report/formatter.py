"""
KhaiScan -- Report Formatter v4 (Tree-structured Telegram UX).

Matches modern Telegram bot layout aesthetics with tree branches (├, └),
compact statistics, audit breakdown, socials, quick links, and 1-tap copy address.
"""
from __future__ import annotations
import logging
from typing import Optional
from models import ScanResult, TokenData, RulesResult, LoreResult, ScoreResult
from report.image_renderer import format_age
from rules.config import VERDICT_EMOJI

logger = logging.getLogger(__name__)

_DIV = "━━━━━━━━━━━━━━━━━━━━━━━━━━"
_MAX_LEN = 4096

_VERDICT_DESC = {
    "GEM":   "Elite setup. High conviction with strong fundamentals.",
    "SOLID": "Strong fundamentals. Good risk/reward.",
    "DEGEN": "Mixed signals. Tradeable but size accordingly.",
    "RISKY": "Significant concerns. High risk -- reduce size.",
    "AVOID": "Multiple red flags. Not recommended.",
    "RUG":   "Critical danger signals detected. Do not enter.",
}


def build_report(result: ScanResult) -> list[str]:
    """Build the full scan report matching the sample tree layout."""
    td = result.token_data
    rr = result.rules_result
    lr = result.lore_result
    sr = result.score_result

    symbol = _esc(td.symbol or "?")
    name = _esc(td.name or symbol)
    chain = _chain_label(td.chain or "")
    age = format_age(td.age_days, td.created_at_ts)

    lines = []

    # 1. Header Line
    lines.append(f"❇️ <b>{name}</b> (${symbol})")
    lines.append(f"🌱 {age} · {chain}")
    lines.append("")

    # 2. Token Stats Tree
    lines.append("📊 <b>Token Stats</b>")
    stats = []
    if td.market_cap is not None:
        stats.append(("MC:", _fmt_usd(td.market_cap)))
    if td.price_usd is not None:
        stats.append(("USD:", _fmt_price(td.price_usd)))
    if td.liquidity_usd is not None:
        stats.append(("LIQ:", _fmt_usd(td.liquidity_usd)))
    if td.volume_24h is not None:
        stats.append(("VOL:", f"{_fmt_usd(td.volume_24h)} (24h)"))
    if td.holder_count:
        stats.append(("HLD:", f"{td.holder_count:,}"))
    if td.dex_name:
        stats.append(("DEX:", td.dex_name))
    stats.append(("AGE:", age))

    for i, (k, v) in enumerate(stats):
        branch = "└" if i == len(stats) - 1 else "├"
        lines.append(f"{branch} {k:<6} <b>{v}</b>")

    lines.append("")

    # 3. Socials
    social_links = []
    if td.website:
        social_links.append(f"<a href='{td.website}'>Web</a>")
    if td.twitter:
        social_links.append(f"<a href='{td.twitter}'>X</a>")
    if td.telegram:
        social_links.append(f"<a href='{td.telegram}'>TG</a>")

    if social_links:
        lines.append("🔗 <b>Socials</b>")
        lines.append(f"└ {' · '.join(social_links)}")
        lines.append("")

    # 4. Audit & Security Tree
    audit_score = sr.overall_score
    lines.append(f"🛡 <b>Audit [{audit_score}/100]</b>")
    audit_rows = []

    # Mint
    if td.mint_disabled is not None:
        val = "Disabled 🟢" if td.mint_disabled else "Active 🔴"
        audit_rows.append(("Mint Auth:", val))

    # Freeze
    if td.freeze_disabled is not None:
        val = "Disabled 🟢" if td.freeze_disabled else "Active 🔴"
        audit_rows.append(("Freeze Auth:", val))

    # Ownership
    if td.ownership_renounced is not None:
        val = "Renounced 🟢" if td.ownership_renounced else "Active 🔴"
        audit_rows.append(("Ownership:", val))

    # LP Lock
    if td.lp_locked is not None:
        lock_pct = f" ({td.lp_lock_pct:.1f}%)" if td.lp_lock_pct else ""
        val = f"Locked{lock_pct} 🟢" if td.lp_locked else "Not locked 🔴"
        audit_rows.append(("LP Lock:", val))

    # Top 10
    if td.top10_pct is not None:
        audit_rows.append(("Top 10:", f"{td.top10_pct:.1f}%"))

    # Bundled
    if td.bundle_pct is not None:
        label = " (Clean launch)" if td.bundle_pct < 5 else ""
        audit_rows.append(("Bundled:", f"{td.bundle_pct:.1f}%{label}"))

    # Insiders
    if td.insider_wallet_count is not None:
        audit_rows.append(("Insiders:", f"{td.insider_wallet_count}"))

    for i, (k, v) in enumerate(audit_rows):
        branch = "└" if i == len(audit_rows) - 1 else "├"
        lines.append(f"{branch} {k:<12} <b>{v}</b>")

    lines.append("")

    # 5. Lore Section (if available)
    if lr and lr.one_line_summary and lr.lore_score > 0:
        lines.append(f"✨ <b>Lore [{lr.lore_score}/100]</b>")
        lines.append(f"└ <i>\"{_esc(lr.one_line_summary)}\"</i>")
        lines.append("")

    # 6. Risk Flags
    flags = []
    if td.risk_flags:
        for f in td.risk_flags[:4]:
            flags.append(_esc(f))

    if flags:
        lines.append("⚠️ <b>Risk Flags</b>")
        for f in flags:
            lines.append(f"└ · {f}")
        lines.append("")

    # 7. Decision Engine
    verdict_emoji = VERDICT_EMOJI.get(sr.verdict, "🎲")
    verdict_desc = _VERDICT_DESC.get(sr.verdict, "")
    lines.append("⚡ <b>Decision Engine</b>")
    lines.append(f"└ <b>{sr.overall_score}/100 -- {sr.verdict} {verdict_emoji}</b>")
    lines.append(f"   <i>{_esc(verdict_desc)}</i>")
    lines.append("")

    # 8. Quick Links
    quick_links = []
    if (td.chain or "") == "solana":
        quick_links.append(f"<a href='https://dexscreener.com/solana/{td.address}'>DEX</a>")
        quick_links.append(f"<a href='https://solscan.io/token/{td.address}'>SOLSCAN</a>")
        quick_links.append(f"<a href='https://insightx.network/token/{td.address}'>INSIGHTX</a>")
    else:
        quick_links.append(f"<a href='https://dexscreener.com/{td.chain}/{td.address}'>DEX</a>")

    lines.append(" · ".join(quick_links))
    lines.append("")

    # 9. 1-Tap Copy Contract Address at Bottom
    lines.append(f"<code>{td.address}</code>")

    report_str = "\n".join(lines)
    return [report_str]


def build_lore_report(td: TokenData, lr: LoreResult) -> str:
    """Build a focused lore-only report for /lore command."""
    symbol = _esc(td.symbol or "?")
    name = _esc(td.name or symbol)
    chain = _chain_label(td.chain or "")

    if not lr or lr.lore_score == 0:
        reason = lr.one_line_summary if lr else "Narrative analysis unavailable."
        return (
            f"✨ <b>LORE ANALYSIS</b>\n\n"
            f"💎 <b>${symbol}</b> · {name} · {chain}\n\n"
            f"<i>{_esc(reason)}</i>"
        )

    comps = "  ".join(f"<code>${t}</code>" for t in lr.comparable_tokens) if lr.comparable_tokens else "None found"

    lines = [
        f"✨ <b>LORE ANALYSIS [{lr.lore_score}/100]</b>",
        f"💎 <b>${symbol}</b> · {name} · {chain}",
        "",
        f"\"{_esc(lr.one_line_summary)}\"",
        "",
        f"├ Narrative Fit   {lr.narrative_fit}/10",
        f"├ Originality     {lr.originality}/10",
        f"├ Virality        {lr.virality}/10",
        f"└ Comparable     {comps}",
        "",
        f"<code>{td.address}</code>",
    ]
    return "\n".join(lines)


def get_image_url(result: ScanResult) -> Optional[str]:
    """Return the token image URL if available."""
    if result.token_data:
        return result.token_data.image_url
    return None


def _fmt_usd(amount: Optional[float]) -> str:
    if amount is None:
        return "N/A"
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.2f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    return f"${amount:.2f}"


def _fmt_price(price: Optional[float]) -> str:
    if price is None:
        return "N/A"
    if price >= 1.0:
        return f"${price:.2f}"
    if price >= 0.0001:
        return f"${price:.6f}"
    return f"${price:.8f}"


def _chain_label(chain: str) -> str:
    labels = {
        "solana":    "Solana",
        "ethereum":  "Ethereum",
        "bsc":       "BSC",
        "base":      "Base",
        "arbitrum":  "Arbitrum",
        "polygon":   "Polygon",
    }
    return labels.get(chain, chain.title()) if chain else "Unknown"


def _esc(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
