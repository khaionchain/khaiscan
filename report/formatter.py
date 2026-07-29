"""
KhaiScan -- Report Formatter v3.

Changes in this version:
- NO em dashes anywhere (replaced with plain text)
- Color legend added to health overview
- Chain-aware security (Solana-only metrics hidden for EVM)
- Cleaner language throughout
- All special chars safe for Telegram HTML
"""
from __future__ import annotations
from typing import Optional
from models import ScanResult, TokenData, RulesResult, LoreResult, ScoreResult
from report.image_renderer import format_age
from rules.config import VERDICT_EMOJI

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


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

def build_report(result: ScanResult) -> list[str]:
    """Build the full scan report. Returns 1 or 2 HTML strings."""
    td = result.token_data
    rr = result.rules_result
    lr = result.lore_result
    sr = result.score_result

    sections = [
        _section_header(td),
        _section_health(sr, rr),
        _section_basic_info(td),
        _section_security(rr, td),
        _section_holders(rr, td),
        _section_developer(rr),
        _section_market(rr, td),
        _section_smart_money(rr, td),
        _section_lore(lr),
        _section_risk_flags(td),
        _section_decision(sr),
        _section_why(sr, rr),
        _section_summary(sr, lr),
        "\n🤖 <i>KhaiScan · Powered by Gemini Flash</i>",
    ]

    full = "\n".join(s for s in sections if s.strip())
    if len(full) <= _MAX_LEN:
        return [full]
    return _split_report(sections)


def build_lore_report(td: TokenData, lr: LoreResult) -> str:
    """Build a focused lore-only report for /lore command."""
    symbol = td.symbol or "?"
    name   = td.name or symbol
    chain  = _chain_label(td.chain or "")

    if not lr or lr.lore_score == 0:
        reason = lr.one_line_summary if lr else "Narrative analysis unavailable."
        return (
            f"{_DIV}\n"
            f"✨ <b>LORE ANALYSIS</b>\n"
            f"{_DIV}\n\n"
            f"💎 <b>${_esc(symbol)}</b> · {_esc(name)} · {chain}\n\n"
            f"<i>{_esc(reason)}</i>\n\n"
            f"🤖 <i>KhaiScan Lore · Powered by Gemini Flash</i>"
        )

    comps = "  ".join(f"<code>${t}</code>" for t in lr.comparable_tokens) if lr.comparable_tokens else "None found"

    lines = [
        f"{_DIV}",
        f"✨ <b>LORE ANALYSIS</b>",
        f"{_DIV}",
        f"",
        f"💎 <b>${_esc(symbol)}</b> · {_esc(name)} · {chain}",
        f"",
        f"\"{_esc(lr.one_line_summary)}\"",
        f"",
        f"  Narrative Fit   {_score_emoji(lr.narrative_fit * 10)} {lr.narrative_fit}/10",
        f"  Originality     {_score_emoji(lr.originality * 10)} {lr.originality}/10",
        f"  Virality        {_score_emoji(lr.virality * 10)} {lr.virality}/10",
        f"  <b>Lore Score</b>     <b>{lr.lore_score}/100</b>",
        f"",
        f"  Comps: {comps}",
        f"",
        f"🤖 <i>KhaiScan Lore · Powered by Gemini Flash</i>",
    ]
    return "\n".join(lines)


def get_image_url(result: ScanResult) -> Optional[str]:
    """Return the token image URL if available."""
    if result.token_data:
        return result.token_data.image_url
    return None


# -----------------------------------------------------------------------
# Split helper
# -----------------------------------------------------------------------

def _split_report(sections: list[str]) -> list[str]:
    split_idx = 9
    msg1 = "\n".join(s for s in sections[:split_idx] if s.strip())
    msg2 = "\n".join(s for s in sections[split_idx:] if s.strip())
    if len(msg1) > _MAX_LEN:
        msg1 = msg1[:_MAX_LEN - 60].rsplit("\n", 1)[0] + "\n\n<i>continued below...</i>"
    return [m for m in [msg1, msg2] if m.strip()]


# -----------------------------------------------------------------------
# Section builders
# -----------------------------------------------------------------------

def _section_header(td: TokenData) -> str:
    symbol = td.symbol or "?"
    name   = td.name or symbol
    chain  = _chain_label(td.chain or "")
    age    = format_age(td.age_days, td.created_at_ts)

    pre_badge = ""
    if td.is_pre_migration:
        curve = f" · {td.bonding_curve_pct:.1f}% to migration" if td.bonding_curve_pct else ""
        pre_badge = f"\n⚡ <b>PRE-MIGRATION</b>{curve}"

    return (
        f"{_DIV}\n"
        f"🔍 <b>KHAISCAN REPORT</b>\n"
        f"{_DIV}\n\n"
        f"💎 <b>${_esc(symbol)}</b> · {_esc(name)} · {chain} · {age}"
        f"{pre_badge}\n"
        f"<code>{td.address}</code>"
    )


def _section_health(sr: ScoreResult, rr: RulesResult) -> str:
    verdict_emoji  = VERDICT_EMOJI.get(sr.verdict, "?")
    confidence_pct = round(sr.confidence * 100)
    verdict_desc   = _VERDICT_DESC.get(sr.verdict, "")

    cs = sr.category_scores

    rows = [
        ("Security",  "security",    "🛡"),
        ("Holders",   "holders",     "👥"),
        ("Launch",    "launch",      "🚀"),
        ("Market",    "market",      "💰"),
        ("Developer", "developer",   "🧠"),
        ("Lore",      "lore",        "✨"),
        ("Smart $",   "smart_money", "💎"),
    ]

    lines = [
        f"\n{_DIV}",
        f"📊 <b>HEALTH OVERVIEW</b>",
        _DIV,
        f"🎯 <b>{sr.overall_score}/100 -- {sr.verdict} {verdict_emoji}</b>  |  Coverage: {confidence_pct}%",
        f"<i>{_esc(verdict_desc)}</i>",
        f"<i>🟩 70+ | 🟨 45-69 | 🟧 20-44 | 🟥 &lt;20</i>",
        "",
    ]

    for label, key, icon in rows:
        score = cs.get(key, 50)
        bar   = _colored_bar(score, blocks=5)
        lines.append(f"  {icon} {label:<10} {bar} {round(score):>3}")

    return "\n".join(lines)


def _section_basic_info(td: TokenData) -> str:
    rows = [
        ("Price",      _fmt_price(td.price_usd)),
        ("Market Cap", _fmt_usd(td.market_cap)),
        ("FDV",        _fmt_usd(td.fdv)),
        ("24h Volume", _fmt_usd(td.volume_24h)),
        ("Liquidity",  _fmt_usd(td.liquidity_usd)),
        ("Age",        format_age(td.age_days, td.created_at_ts)),
        ("DEX",        td.dex_name or None),
        ("Holders",    f"{td.holder_count:,}" if td.holder_count else None),
    ]
    body = "\n".join(
        f"  {k:<14} <code>{v}</code>"
        for k, v in rows if v
    )
    return f"\n{_DIV}\n📈 <b>BASIC INFORMATION</b>\n{_DIV}\n{body}"


def _section_security(rr: RulesResult, td: TokenData) -> str:
    is_solana = (td.chain or "") == "solana"
    lines = [f"\n{_DIV}", "🛡 <b>SECURITY</b>", _DIV]
    has_content = False

    # Honeypot
    v = rr.verdicts.get("is_honeypot")
    if v:
        display = f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Honeypot Check':<22} {display}")
        has_content = True
    elif is_solana:
        lines.append(f"  {'Honeypot':<22} <i>N/A on Solana</i>")
        has_content = True

    # Mint authority
    v = rr.verdicts.get("mint_disabled")
    if v:
        display = f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Mint Authority':<22} {display}")
        has_content = True
    elif td.mint_disabled is not None:
        icon = "🟢 Disabled (safe)" if td.mint_disabled else "🔴 Active (risk)"
        lines.append(f"  {'Mint Authority':<22} {icon}")
        has_content = True

    # Freeze authority (Solana only)
    if td.freeze_disabled is not None:
        icon = "🟢 Disabled (safe)" if td.freeze_disabled else "🔴 Active (risk)"
        lines.append(f"  {'Freeze Authority':<22} {icon}")
        has_content = True

    # Ownership renounced
    v = rr.verdicts.get("ownership_renounced")
    if v:
        display = f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Ownership':<22} {display}")
        has_content = True
    elif td.ownership_renounced is not None:
        icon = "🟢 Renounced" if td.ownership_renounced else "🔴 Not renounced"
        lines.append(f"  {'Ownership':<22} {icon}")
        has_content = True

    # Blacklist function (EVM only)
    v = rr.verdicts.get("has_blacklist")
    if v:
        display = f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Blacklist Function':<22} {display}")
        has_content = True
    elif is_solana:
        lines.append(f"  {'Blacklist Function':<22} <i>N/A on Solana</i>")
        has_content = True

    # Buy / Sell tax
    v_buy  = rr.verdicts.get("buy_tax")
    v_sell = rr.verdicts.get("sell_tax")
    if v_buy or v_sell:
        buy_str  = f"{_fmt_pct(td.buy_tax)} {v_buy.emoji} {v_buy.label}" if v_buy else "N/A"
        sell_str = f"{_fmt_pct(td.sell_tax)} {v_sell.emoji} {v_sell.label}" if v_sell else "N/A"
        lines.append(f"  {'Buy Tax':<22} <code>{buy_str}</code>")
        lines.append(f"  {'Sell Tax':<22} <code>{sell_str}</code>")
        has_content = True
    elif is_solana:
        lines.append(f"  {'Buy / Sell Tax':<22} <i>N/A on Solana</i>")
        has_content = True

    if not has_content:
        lines.append("  <i>Security data unavailable for this token.</i>")

    return "\n".join(lines)


def _section_holders(rr: RulesResult, td: TokenData) -> str:
    lines = [f"\n{_DIV}", "👥 <b>HOLDER ANALYSIS</b>", _DIV]
    has_content = False

    # Top 10 concentration
    v = rr.verdicts.get("top10_pct")
    if v:
        val_str = _fmt_pct(td.top10_pct)
        display = f"<code>{val_str}</code>  {v.emoji} {_esc(v.label)}" if val_str else f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Top 10 Holdings':<22} {display}")
        has_content = True

    # Largest wallet
    v = rr.verdicts.get("largest_wallet_pct")
    if v:
        val_str = _fmt_pct(td.largest_wallet_pct)
        display = f"<code>{val_str}</code>  {v.emoji} {_esc(v.label)}" if val_str else f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Largest Wallet':<22} {display}")
        has_content = True

    # Insider wallets
    v = rr.verdicts.get("insider_wallet_count")
    if v:
        val_str = str(int(v.value)) if v.value is not None else ""
        display = f"<code>{val_str}</code>  {v.emoji} {_esc(v.label)}" if val_str else f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Insider Wallets':<22} {display}")
        has_content = True
    elif td.insider_wallet_count is not None:
        lines.append(f"  {'Insider Wallets':<22} <code>{td.insider_wallet_count}</code>")
        has_content = True

    # LP lock
    v = rr.verdicts.get("lp_locked")
    if v:
        lock_pct = f" ({td.lp_lock_pct:.1f}%)" if td.lp_lock_pct else ""
        display = f"{v.emoji} {_esc(v.label)}{lock_pct}"
        lines.append(f"  {'LP Lock':<22} {display}")
        has_content = True
    elif td.lp_locked is not None:
        icon = f"🟢 Locked ({td.lp_lock_pct:.1f}%)" if td.lp_locked and td.lp_lock_pct else ("🟢 Locked" if td.lp_locked else "🔴 Not locked")
        lines.append(f"  {'LP Lock':<22} {icon}")
        has_content = True

    # Bundle activity (from InsightX, GMGN, or RugCheck)
    v = rr.verdicts.get("bundle_pct")
    if v:
        val_str = _fmt_pct(td.bundle_pct)
        display = f"<code>{val_str}</code>  {v.emoji} {_esc(v.label)}" if val_str else f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Bundle Activity':<22} {display}")
        has_content = True
    elif td.bundle_pct is not None:
        lines.append(f"  {'Bundle Activity':<22} <code>{_fmt_pct(td.bundle_pct)}</code>")
        has_content = True

    # Bonding curve progress (for Pump.fun pre-migration)
    if td.is_pre_migration and td.bonding_curve_pct is not None:
        lines.append(f"  {'Bonding Curve':<22} ⚡ {td.bonding_curve_pct:.1f}% complete")
        has_content = True

    # InsightX link
    ix_url = getattr(td, "insightx_url", None)
    if ix_url:
        lines.append(f"  <a href='{ix_url}'>View full holder graph on InsightX</a>")
    else:
        lines.append(f"  <a href='https://insightx.network/token/{td.address}'>View on InsightX</a>")

    if not has_content:
        lines.append("  <i>Holder data unavailable.</i>")

    return "\n".join(lines)


def _section_developer(rr: RulesResult) -> str:
    lines = [f"\n{_DIV}", "🧠 <b>DEVELOPER ANALYSIS</b>", _DIV]
    has_content = False

    for key in ["dev_wallet_pct", "dev_sold"]:
        v = rr.verdicts.get(key)
        if v:
            val_str = _fmt_pct(v.value) if key == "dev_wallet_pct" and v.value is not None else ""
            display = f"<code>{val_str}</code>  {v.emoji} {_esc(v.label)}" if val_str else f"{v.emoji} {_esc(v.label)}"
            label_map = {
                "dev_wallet_pct": "Dev Holdings",
                "dev_sold":       "Dev Sold",
            }
            lines.append(f"  {label_map[key]:<22} {display}")
            has_content = True

    if not has_content:
        lines.append(
            "  <i>Dev wallet data requires RugCheck to identify the creator address.</i>"
        )

    return "\n".join(lines)


def _section_market(rr: RulesResult, td: TokenData) -> str:
    lines = [f"\n{_DIV}", "📉 <b>MARKET ACTIVITY</b>", _DIV]

    # Volume / MC ratio
    vmr = td.volume_mc_ratio
    v = rr.verdicts.get("volume_mc_ratio")
    if v:
        val_str = f"<code>{vmr:.2f}x</code>" if vmr is not None else ""
        display = f"{val_str}  {v.emoji} {_esc(v.label)}" if val_str else f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Volume / MC':<22} {display}")

    # Liquidity / MC ratio
    lmr = td.liq_mc_ratio
    v = rr.verdicts.get("liq_mc_ratio")
    if v:
        val_str = f"<code>{lmr:.1%}</code>" if lmr is not None else ""
        display = f"{val_str}  {v.emoji} {_esc(v.label)}" if val_str else f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Liquidity / MC':<22} {display}")

    return "\n".join(lines)


def _section_smart_money(rr: RulesResult, td: TokenData) -> str:
    lines = [f"\n{_DIV}", "💎 <b>SMART MONEY</b>", _DIV]
    has_content = False

    v = rr.verdicts.get("smart_money_wallet_count")
    if v:
        val_str = str(int(v.value)) if v.value is not None else ""
        display = f"<code>{val_str}</code>  {v.emoji} {_esc(v.label)}" if val_str else f"{v.emoji} {_esc(v.label)}"
        lines.append(f"  {'Smart Wallets':<22} {display}")
        has_content = True

    if td.smart_money_net_bias:
        bias_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(
            td.smart_money_net_bias, "⚪"
        )
        lines.append(f"  {'Net Bias':<22} {bias_emoji} {td.smart_money_net_bias.title()}")
        has_content = True

    if not has_content:
        lines.append(
            "  <i>Smart money data requires a GMGN API key.</i>\n"
            "  <i>Get one at gmgn.ai (top-right icon) and add it to .env</i>"
        )

    return "\n".join(lines)


def _section_lore(lr: Optional[LoreResult]) -> str:
    if not lr:
        return ""

    if lr.lore_score == 0:
        return (
            f"\n{_DIV}\n✨ <b>LORE</b>\n{_DIV}\n\n"
            f"  <i>{_esc(lr.one_line_summary)}</i>"
        )

    comps = "  ".join(f"<code>${t}</code>" for t in lr.comparable_tokens) if lr.comparable_tokens else "None"

    lines = [
        f"\n{_DIV}",
        "✨ <b>LORE</b>",
        _DIV,
        "",
        f"  \"{_esc(lr.one_line_summary)}\"",
        "",
        f"  Narrative   {_score_emoji(lr.narrative_fit * 10)} {lr.narrative_fit}/10",
        f"  Originality {_score_emoji(lr.originality * 10)} {lr.originality}/10",
        f"  Virality    {_score_emoji(lr.virality * 10)} {lr.virality}/10",
        f"  Score       <b>{lr.lore_score}/100</b>",
        f"  Comps       {comps}",
    ]
    return "\n".join(lines)


def _section_risk_flags(td: TokenData) -> str:
    flags = []
    if td.fake_volume_detected and td.fake_volume_reason:
        flags.append(f"🚨 FAKE VOLUME: {_esc(td.fake_volume_reason)}")
    if td.airdrop_detected and td.airdrop_reason:
        flags.append(f"🚨 AIRDROP DETECTED: {_esc(td.airdrop_reason)}")
    if td.suspicious_buys_detected and td.suspicious_buys_reason:
        flags.append(f"🚨 SUSPICIOUS BUYS: {_esc(td.suspicious_buys_reason)}")

    if td.risk_flags:
        for f in td.risk_flags:
            esc_f = _esc(f)
            if esc_f not in flags:
                flags.append(esc_f)

    if not flags:
        return (
            f"\n{_DIV}\n⚠️ <b>RISK FLAGS & FRAUD</b>\n{_DIV}\n"
            f"  ✅ No additional flags detected"
        )

    lines = [f"\n{_DIV}", "⚠️ <b>RISK FLAGS & FRAUD</b>", _DIV]
    for flag in flags[:8]:
        lines.append(f"  · {flag}")
    return "\n".join(lines)


def _section_decision(sr: ScoreResult) -> str:
    verdict_emoji = VERDICT_EMOJI.get(sr.verdict, "?")
    return (
        f"\n{_DIV}\n"
        f"⚡ <b>DECISION ENGINE</b>\n"
        f"{_DIV}\n\n"
        f"  <b>{sr.overall_score} / 100 -- {sr.verdict} {verdict_emoji}</b>\n"
    )


def _section_why(sr: ScoreResult, rr: RulesResult) -> str:
    lines = [f"\n{_DIV}", "❓ <b>WHY THIS SCORE?</b>", _DIV, ""]

    cs = sr.category_scores
    lines.append(
        f"  🛡{round(cs.get('security', 50))} "
        f"👥{round(cs.get('holders', 50))} "
        f"🚀{round(cs.get('launch', 50))} "
        f"💰{round(cs.get('market', 50))} "
        f"🧠{round(cs.get('developer', 50))} "
        f"✨{round(cs.get('lore', 50))} "
        f"💎{round(cs.get('smart_money', 50))}"
    )
    lines.append("")

    if sr.strengths:
        lines.append("  ✅ <b>Strengths:</b>")
        for s in sr.strengths[:4]:
            lines.append(f"    · {_esc(s)}")

    if sr.risks:
        lines.append("  ⚠️ <b>Risks:</b>")
        for r in sr.risks[:4]:
            lines.append(f"    · {_esc(r)}")

    return "\n".join(lines)


def _section_summary(sr: ScoreResult, lr: Optional[LoreResult]) -> str:
    verdict_emoji = VERDICT_EMOJI.get(sr.verdict, "?")
    verdict_desc  = _VERDICT_DESC.get(sr.verdict, "Proceed with caution.")

    lore_note = ""
    if lr and lr.lore_score > 0 and lr.one_line_summary:
        lore_note = f"\n\n  ✨ <i>{_esc(lr.one_line_summary)}</i>"

    return (
        f"\n{_DIV}\n"
        f"📝 <b>SUMMARY</b>\n"
        f"{_DIV}\n\n"
        f"  {verdict_emoji} {_esc(verdict_desc)}{lore_note}"
    )


# -----------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------

def _colored_bar(score: float, blocks: int = 6) -> str:
    """
    Emoji progress bar using colored squares.
    Guaranteed to render on all Telegram clients (Android, iOS, desktop).

    Color is determined by the score:
      70+  = 🟩 green  (good)
      45+  = 🟨 yellow (caution)
      20+  = 🟧 orange (warning)
      <20  = 🟥 red    (critical)
    Empty blocks use ⬛.
    """
    filled = round(max(0, min(100, score)) / 100 * blocks)
    if score >= 70:
        fill = "🟩"
    elif score >= 45:
        fill = "🟨"
    elif score >= 20:
        fill = "🟧"
    else:
        fill = "🟥"
    return fill * filled + "⬛" * (blocks - filled)


def _score_emoji(score: int) -> str:
    if score >= 70:
        return "🟢"
    if score >= 40:
        return "🟡"
    return "🔴"


def _fmt_metric_value(key: str, value) -> str:
    if value is None:
        return ""
    try:
        if key in ("top10_pct", "largest_wallet_pct", "dev_wallet_pct",
                   "bundle_pct", "buy_tax", "sell_tax", "lp_lock_pct"):
            return f"{float(value):.1f}%"
        if key in ("insider_wallet_count", "smart_money_wallet_count"):
            return str(int(value))
    except (ValueError, TypeError):
        pass
    return ""


def _fmt_pct(val) -> Optional[str]:
    if val is None:
        return None
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return None


def _fmt_price(price: Optional[float]) -> Optional[str]:
    if price is None:
        return None
    if price < 0.000001:
        return f"${price:.10f}".rstrip("0").rstrip(".")
    if price < 0.01:
        return f"${price:.6f}"
    if price < 1:
        return f"${price:.4f}"
    return f"${price:,.2f}"


def _fmt_usd(amount: Optional[float]) -> Optional[str]:
    if amount is None:
        return None
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.2f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    return f"${amount:.2f}"


def _chain_label(chain: str) -> str:
    labels = {
        "solana":    "Solana",
        "ethereum":  "Ethereum",
        "bsc":       "BSC",
        "base":      "Base",
        "arbitrum":  "Arbitrum",
        "polygon":   "Polygon",
        "optimism":  "Optimism",
        "avalanche": "Avalanche",
        "fantom":    "Fantom",
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
