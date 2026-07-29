"""
KhaiScan -- Image Renderer.

Renders a ScanResult into a premium dark-themed PNG image
using an HTML template + Playwright (headless Chromium).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from models import ScanResult, TokenData, RulesResult, LoreResult, ScoreResult
from rules.config import VERDICT_EMOJI

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent
_TEMPLATE_NAME = "template.html"

_VERDICT_DESC = {
    "GEM":   "Elite setup. High conviction with strong fundamentals.",
    "SOLID": "Strong fundamentals. Good risk/reward.",
    "DEGEN": "Mixed signals. Tradeable but size accordingly.",
    "RISKY": "Significant concerns. High risk -- reduce size.",
    "AVOID": "Multiple red flags. Not recommended.",
    "RUG":   "Critical danger signals detected. Do not enter.",
}


def format_age(age_days: Optional[int], created_at_ts: Optional[float] = None) -> str:
    """Smart age display: hours/days/months/years as appropriate."""
    if age_days is None and created_at_ts is None:
        return "?"

    # For sub-day precision, use the raw timestamp
    if created_at_ts is not None:
        elapsed_secs = time.time() - created_at_ts
        if elapsed_secs < 0:
            return "0h"
        hours = elapsed_secs / 3600
        if hours < 24:
            return f"{max(1, int(hours))}h"
        days = elapsed_secs / 86400
    elif age_days is not None:
        days = age_days
    else:
        return "?"

    if days < 1:
        return "<1d"
    if days < 30:
        return f"{int(days)}d"
    if days < 365:
        months = int(days / 30)
        return f"{months}mo"
    years = days / 365
    if years < 2:
        return f"{years:.1f}y"
    return f"{int(years)}y"

# Jinja2 environment (loaded once)
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=False,
)


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

async def render_report_image(result: ScanResult) -> bytes:
    """
    Render the full scan report as a PNG image.

    Returns PNG bytes ready to send via Telegram's send_photo.
    Raises Exception if rendering fails.
    """
    html = _build_html(result)
    png_bytes = await _html_to_png(html)
    return png_bytes


# -----------------------------------------------------------------------
# HTML builder -- populates the Jinja2 template with ScanResult data
# -----------------------------------------------------------------------

def _build_html(result: ScanResult) -> str:
    td = result.token_data
    rr = result.rules_result
    lr = result.lore_result
    sr = result.score_result

    template = _jinja_env.get_template(_TEMPLATE_NAME)

    context = {
        # Header
        "timestamp": datetime.now().strftime("Today, %H:%M"),

        # Token identity
        "symbol": td.symbol or "?",
        "symbol_initial": (td.symbol or "?")[0].upper(),
        "name": td.name or td.symbol or "Unknown",
        "chain": _chain_label(td.chain or ""),
        "age": format_age(td.age_days, td.created_at_ts),
        "address": td.address or "",
        "image_url": td.image_url or "",
        "is_pre_migration": td.is_pre_migration,
        "is_new_token": (td.age_days is not None and td.age_days == 0) or (td.created_at_ts is not None and (time.time() - td.created_at_ts) < 86400),

        # Scores
        "overall_score": sr.overall_score,
        "verdict": sr.verdict,
        "verdict_emoji": VERDICT_EMOJI.get(sr.verdict, "?"),
        "verdict_desc": _VERDICT_DESC.get(sr.verdict, "Proceed with caution."),
        "score_color_class": _score_color_class(sr.overall_score),
        "coverage": round(sr.confidence * 100),
        "gauge_color": _score_color_hex(sr.overall_score),

        # Stats ribbon
        "price": _fmt_price(td.price_usd) or "N/A",
        "market_cap": _fmt_usd(td.market_cap) or "N/A",
        "liquidity": _fmt_usd(td.liquidity_usd) or "N/A",
        "volume_24h": _fmt_usd(td.volume_24h) or "N/A",
        "holders": f"{td.holder_count:,}" if td.holder_count else "N/A",

        # Health overview
        "categories": _build_categories(sr),
        "pct_strong": _pct_in_range(sr, 70, 101),
        "pct_good": _pct_in_range(sr, 45, 70),
        "pct_weak": _pct_in_range(sr, 20, 45),
        "pct_vweak": _pct_in_range(sr, 0, 20),

        # Basic info
        "basic_info": _build_basic_info(td),

        # Security
        "security_rows": _build_security_rows(rr, td),
        "security_status_class": _security_status_class(sr.category_scores.get("security", 50)),
        "security_status_label": _security_status_label(sr.category_scores.get("security", 50)),
        "security_status_icon": _security_status_icon(sr.category_scores.get("security", 50)),

        # Launch
        "launch_rows": _build_launch_rows(rr, td),

        # Holders
        "holder_rows": _build_holder_rows(rr, td),

        # Developer
        "dev_rows": _build_dev_rows(rr),

        # Market
        "market_rows": _build_market_rows(rr, td),

        # Smart money
        "smart_money_rows": _build_smart_money_rows(rr, td),

        # Lore
        "lore": _build_lore(lr),

        # Risk flags + Fraud Detection flags
        "risk_flags": _build_risk_flags(td),

        # Strengths / Risks
        "strengths": sr.strengths[:4] if sr.strengths else [],
        "risks": sr.risks[:4] if sr.risks else [],
    }

    return template.render(**context)


def _build_risk_flags(td: TokenData) -> list[str]:
    flags = []
    if td.fake_volume_detected:
        flags.append(f"🚨 FAKE VOLUME: {td.fake_volume_reason}")
    if td.airdrop_detected:
        flags.append(f"🚨 AIRDROP DETECTED: {td.airdrop_reason}")
    if td.suspicious_buys_detected:
        flags.append(f"🚨 SUSPICIOUS BUYS: {td.suspicious_buys_reason}")

    if td.risk_flags:
        for f in td.risk_flags:
            if f not in flags:
                flags.append(f)

    return flags[:8]


# -----------------------------------------------------------------------
# Playwright renderer (Persistent Browser Instance)
# -----------------------------------------------------------------------

_browser = None
_playwright = None
_browser_lock = asyncio.Lock()


async def _get_browser():
    global _browser, _playwright
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            from playwright.async_api import async_playwright
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
        return _browser


async def close_browser():
    """Cleanup Playwright browser on shutdown."""
    global _browser, _playwright
    async with _browser_lock:
        if _browser:
            await _browser.close()
            _browser = None
        if _playwright:
            await _playwright.stop()
            _playwright = None


async def _html_to_png(html: str) -> bytes:
    """Render HTML string to PNG bytes using a persistent Playwright Chromium browser."""
    browser = await _get_browser()
    context = await browser.new_context(
        viewport={"width": 800, "height": 800},
        device_scale_factor=2,  # Ultra HD quality, fast encode
    )
    page = await context.new_page()
    try:
        await page.set_content(html, wait_until="domcontentloaded")
        body_height = await page.evaluate("document.body.scrollHeight")
        await page.set_viewport_size({"width": 800, "height": body_height + 20})
        png_bytes = await page.screenshot(
            type="png",
            full_page=True,
            omit_background=False,
        )
        return png_bytes
    finally:
        await context.close()


# -----------------------------------------------------------------------
# Data builders for template context
# -----------------------------------------------------------------------

def _build_categories(sr: ScoreResult) -> list[dict]:
    """Build category bar data for the health overview."""
    cs = sr.category_scores
    cats = [
        ("Security",  "security",    "🛡"),
        ("Holders",   "holders",     "👥"),
        ("Market",    "market",      "💰"),
        ("Developer", "developer",   "🧠"),
        ("Lore",      "lore",        "✨"),
        ("Smart $",   "smart_money", "💎"),
    ]

    result = []
    for name, key, icon in cats:
        score = round(cs.get(key, 50))
        blocks = _build_bar_blocks(score, 5)
        result.append({
            "name": name,
            "icon": icon,
            "score": score,
            "blocks": blocks,
        })
    return result


def _build_bar_blocks(score: float, count: int = 5) -> list[dict]:
    """Build colored bar blocks for a score."""
    filled = round(max(0, min(100, score)) / 100 * count)
    color = _score_color_hex(score)
    blocks = []
    for i in range(count):
        if i < filled:
            blocks.append({"color": color})
        else:
            blocks.append({"color": "#1a2236"})
    return blocks


def _build_basic_info(td: TokenData) -> list[dict]:
    """Build basic info key-value rows."""
    rows = [
        ("Price", _fmt_price(td.price_usd)),
        ("Market Cap", _fmt_usd(td.market_cap)),
        ("FDV", _fmt_usd(td.fdv)),
        ("24h Volume", _fmt_usd(td.volume_24h)),
        ("Liquidity", _fmt_usd(td.liquidity_usd)),
        ("Age", format_age(td.age_days, td.created_at_ts)),
        ("DEX", td.dex_name),
        ("Holders", f"{td.holder_count:,}" if td.holder_count else None),
    ]
    return [{"key": k, "val": v} for k, v in rows if v]


def _build_security_rows(rr: RulesResult, td: TokenData) -> list[dict]:
    """Build security verdict rows."""
    is_solana = (td.chain or "") == "solana"
    rows = []

    # Honeypot
    v = rr.verdicts.get("is_honeypot")
    if v:
        rows.append({"key": "Honeypot Check", "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})
    elif is_solana:
        rows.append({"key": "Honeypot Check", "label": "Unable to verify", "dot_class": "dot-gray"})

    # Mint authority
    v = rr.verdicts.get("mint_disabled")
    if v:
        rows.append({"key": "Mint Authority", "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})
    elif td.mint_disabled is not None:
        label = "Disabled" if td.mint_disabled else "Active (risk)"
        dot = "dot-green" if td.mint_disabled else "dot-red"
        rows.append({"key": "Mint Authority", "label": label, "dot_class": dot})

    # Freeze authority (Solana)
    if td.freeze_disabled is not None:
        label = "Disabled (safe)" if td.freeze_disabled else "Active (risk)"
        dot = "dot-green" if td.freeze_disabled else "dot-red"
        rows.append({"key": "Freeze Authority", "label": label, "dot_class": dot})

    # Ownership
    v = rr.verdicts.get("ownership_renounced")
    if v:
        rows.append({"key": "Ownership", "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})
    elif td.ownership_renounced is not None:
        label = "Renounced" if td.ownership_renounced else "Not renounced"
        dot = "dot-green" if td.ownership_renounced else "dot-red"
        rows.append({"key": "Ownership", "label": label, "dot_class": dot})

    # Blacklist
    v = rr.verdicts.get("has_blacklist")
    if v:
        rows.append({"key": "Blacklist Function", "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})
    elif is_solana:
        rows.append({"key": "Blacklist Function", "label": "Unknown", "dot_class": "dot-gray"})

    # Buy/Sell Tax
    v_buy = rr.verdicts.get("buy_tax")
    v_sell = rr.verdicts.get("sell_tax")
    if v_buy:
        val = _fmt_pct(td.buy_tax) or "None"
        rows.append({"key": "Buy Tax", "label": f"{val} · {v_buy.label}", "dot_class": _emoji_to_dot(v_buy.emoji)})
    else:
        rows.append({"key": "Buy Tax", "label": "No data", "dot_class": "dot-gray"})

    if v_sell:
        val = _fmt_pct(td.sell_tax) or "None"
        rows.append({"key": "Sell Tax", "label": f"{val} · {v_sell.label}", "dot_class": _emoji_to_dot(v_sell.emoji)})
    else:
        rows.append({"key": "Sell Tax", "label": "No data", "dot_class": "dot-gray"})

    return rows


def _build_launch_rows(rr: RulesResult, td: TokenData) -> list[dict]:
    """Build launch analysis rows."""
    rows = []

    v = rr.verdicts.get("bundle_pct")
    if v:
        val = _fmt_pct(td.bundle_pct)
        rows.append({"key": "Bundle Activity", "value": val or "", "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})
    elif td.bundle_pct is not None:
        val = _fmt_pct(td.bundle_pct)
        dot = "dot-green" if td.bundle_pct < 5 else ("dot-yellow" if td.bundle_pct < 15 else "dot-red")
        label = "Minimal" if td.bundle_pct < 5 else ("Moderate" if td.bundle_pct < 15 else "High bundling")
        rows.append({"key": "Bundle Activity", "value": val or "", "label": label, "dot_class": dot})
    else:
        rows.append({"key": "Bundle Activity", "value": "", "label": "No data", "dot_class": "dot-gray"})

    v = rr.verdicts.get("insider_wallet_count")
    if v:
        val = str(int(v.value)) if v.value is not None else ""
        rows.append({"key": "Insider Wallets", "value": val, "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})

    return rows


def _build_holder_rows(rr: RulesResult, td: TokenData) -> list[dict]:
    """Build holder analysis rows."""
    rows = []

    v = rr.verdicts.get("top10_pct")
    if v:
        val = _fmt_pct(td.top10_pct)
        rows.append({"key": "Top 10 Holdings", "value": val or "", "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})

    v = rr.verdicts.get("largest_wallet_pct")
    if v:
        val = _fmt_pct(td.largest_wallet_pct)
        rows.append({"key": "Largest Wallet", "value": val or "", "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})

    v = rr.verdicts.get("insider_wallet_count")
    if v and v.value is not None:
        val = str(int(v.value))
        rows.append({"key": "Insider Wallets", "value": val, "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})
    elif td.insider_wallet_count is not None:
        rows.append({"key": "Insider Wallets", "value": str(td.insider_wallet_count), "label": "Detected", "dot_class": "dot-yellow"})

    v = rr.verdicts.get("lp_locked")
    if v:
        pct = f" ({td.lp_lock_pct:.1f}%)" if td.lp_lock_pct else ""
        rows.append({"key": "LP Lock", "value": "", "label": f"{v.label}{pct}", "dot_class": _emoji_to_dot(v.emoji)})
    elif td.lp_locked is not None:
        label = f"Locked ({td.lp_lock_pct:.1f}%)" if td.lp_locked and td.lp_lock_pct else ("Locked" if td.lp_locked else "Not locked")
        dot = "dot-green" if td.lp_locked else "dot-red"
        rows.append({"key": "LP Lock", "value": "", "label": label, "dot_class": dot})

    v = rr.verdicts.get("bundle_pct")
    if v:
        val = _fmt_pct(td.bundle_pct)
        rows.append({"key": "Bundle Activity", "value": val or "", "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})
    elif td.bundle_pct is not None:
        val = _fmt_pct(td.bundle_pct)
        dot = "dot-green" if td.bundle_pct < 5 else ("dot-yellow" if td.bundle_pct < 15 else "dot-red")
        label = "Minimal" if td.bundle_pct < 5 else ("Moderate" if td.bundle_pct < 15 else "High bundling")
        rows.append({"key": "Bundle Activity", "value": val or "", "label": label, "dot_class": dot})

    return rows


def _build_dev_rows(rr: RulesResult) -> list[dict]:
    """Build developer analysis rows."""
    rows = []
    label_map = {"dev_wallet_pct": "Dev Holdings", "dev_sold": "Dev Sold"}

    for key in ["dev_wallet_pct", "dev_sold"]:
        v = rr.verdicts.get(key)
        if v:
            val = _fmt_pct(v.value) if key == "dev_wallet_pct" and v.value is not None else ""
            rows.append({
                "key": label_map[key],
                "value": val,
                "label": v.label,
                "dot_class": _emoji_to_dot(v.emoji),
            })

    if not rows:
        rows.append({"key": "Dev Data", "value": "", "label": "Unavailable", "dot_class": "dot-gray"})

    return rows


def _build_market_rows(rr: RulesResult, td: TokenData) -> list[dict]:
    """Build market activity rows."""
    rows = []

    v = rr.verdicts.get("volume_mc_ratio")
    if v:
        val = f"{td.volume_mc_ratio:.2f}x" if td.volume_mc_ratio is not None else ""
        rows.append({"key": "Volume / MC", "value": val, "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})

    v = rr.verdicts.get("liq_mc_ratio")
    if v:
        val = f"{td.liq_mc_ratio:.1%}" if td.liq_mc_ratio is not None else ""
        rows.append({"key": "Liquidity / MC", "value": val, "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})

    return rows


def _build_smart_money_rows(rr: RulesResult, td: TokenData) -> list[dict]:
    """Build smart money rows."""
    rows = []

    v = rr.verdicts.get("smart_money_wallet_count")
    if v:
        val = str(int(v.value)) if v.value is not None else ""
        rows.append({"key": "Smart Wallets", "value": val, "label": v.label, "dot_class": _emoji_to_dot(v.emoji)})

    if td.smart_money_net_bias:
        bias_dot = {
            "bullish": "dot-green",
            "bearish": "dot-red",
            "neutral": "dot-yellow",
        }.get(td.smart_money_net_bias, "dot-gray")
        rows.append({
            "key": "Net Bias",
            "value": "",
            "label": td.smart_money_net_bias.title(),
            "dot_class": bias_dot,
        })

    if not rows:
        rows.append({"key": "Smart Money", "value": "", "label": "No data", "dot_class": "dot-gray"})

    return rows


def _build_lore(lr: Optional[LoreResult]) -> Optional[dict]:
    """Build lore data for the template."""
    if not lr or lr.lore_score == 0:
        if lr and lr.one_line_summary:
            return {
                "summary": lr.one_line_summary,
                "narrative": 0, "originality": 0, "virality": 0,
                "narrative_color": "color-gray",
                "originality_color": "color-gray",
                "virality_color": "color-gray",
                "score": 0,
                "score_color": "color-gray",
                "comps": [],
            }
        return None

    return {
        "summary": lr.one_line_summary,
        "narrative": lr.narrative_fit,
        "originality": lr.originality,
        "virality": lr.virality,
        "narrative_color": _lore_metric_color(lr.narrative_fit),
        "originality_color": _lore_metric_color(lr.originality),
        "virality_color": _lore_metric_color(lr.virality),
        "score": lr.lore_score,
        "score_color": _score_color_class(lr.lore_score),
        "comps": lr.comparable_tokens or [],
    }


# -----------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------

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


def _fmt_pct(val) -> Optional[str]:
    if val is None:
        return None
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return None


def _chain_label(chain: str) -> str:
    labels = {
        "solana": "Solana", "ethereum": "Ethereum", "bsc": "BSC",
        "base": "Base", "arbitrum": "Arbitrum", "polygon": "Polygon",
        "optimism": "Optimism", "avalanche": "Avalanche", "fantom": "Fantom",
    }
    return labels.get(chain, chain.title()) if chain else "Unknown"


def _score_color_hex(score: float) -> str:
    if score >= 70:
        return "#00e676"
    if score >= 45:
        return "#ffc107"
    if score >= 20:
        return "#ff9800"
    return "#f44336"


def _score_color_class(score: float) -> str:
    if score >= 70:
        return "color-green"
    if score >= 45:
        return "color-yellow"
    if score >= 20:
        return "color-orange"
    return "color-red"


def _lore_metric_color(val: int) -> str:
    """Color class for lore metrics (0-10 scale)."""
    if val >= 7:
        return "color-green"
    if val >= 4:
        return "color-yellow"
    return "color-red"


def _emoji_to_dot(emoji: str) -> str:
    """Convert verdict emoji to CSS dot class."""
    mapping = {
        "🟢": "dot-green",
        "🟡": "dot-yellow",
        "🟠": "dot-orange",
        "🔴": "dot-red",
        "⚪": "dot-gray",
    }
    return mapping.get(emoji, "dot-gray")


def _security_status_class(score: float) -> str:
    if score >= 70:
        return "security-good"
    if score >= 45:
        return "security-warn"
    return "security-bad"


def _security_status_label(score: float) -> str:
    if score >= 70:
        return "GOOD"
    if score >= 45:
        return "CAUTION"
    return "DANGER"


def _security_status_icon(score: float) -> str:
    if score >= 70:
        return "✅"
    if score >= 45:
        return "⚠️"
    return "🚫"


def _pct_in_range(sr: ScoreResult, low: int, high: int) -> int:
    """Calculate what % of category scores fall in a range."""
    cs = sr.category_scores
    if not cs:
        return 0
    total = len(cs)
    count = sum(1 for v in cs.values() if low <= round(v) < high)
    return round(count / total * 100) if total else 0
