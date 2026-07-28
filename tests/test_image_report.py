"""
Quick smoke test for the image renderer.

Run: .venv/bin/python tests/test_image_report.py

Generates a test report image and saves it to tests/test_output.png
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import TokenData, RulesResult, LoreResult, ScoreResult, ScanResult, MetricVerdict
from report.image_renderer import render_report_image


def _make_mock_result() -> ScanResult:
    """Create a realistic mock ScanResult matching the $ROCK screenshot."""
    td = TokenData(
        address="EkqbQhYmZ4Ax4Ek8dwsqA2NGaqfakkfmeENuJh7FvY6h",
        chain="solana",
        name="just a rock",
        symbol="ROCK",
        image_url="",
        price_usd=0.0000031,
        market_cap=31_100,
        fdv=31_100,
        volume_24h=729_400,
        liquidity_usd=19_700,
        age_days=0,
        dex_name="Meteora",
        holder_count=378,
        is_pre_migration=False,
        mint_disabled=True,
        freeze_disabled=True,
        ownership_renounced=True,
        has_blacklist=None,
        buy_tax=None,
        sell_tax=None,
        top10_pct=53.0,
        largest_wallet_pct=31.6,
        lp_locked=True,
        lp_lock_pct=100.0,
        bundle_pct=None,
        insider_wallet_count=0,
        dev_wallet_pct=0.8,
        dev_sold=True,
        smart_money_wallet_count=2,
        smart_money_net_bias="bullish",
        volume_mc_ratio=23.47,
        liq_mc_ratio=0.633,
    )
    td.risk_flags = []
    td.update_confidence()

    rr = RulesResult()
    rr.verdicts = {
        "is_honeypot": MetricVerdict(
            metric="is_honeypot", display_name="Honeypot",
            value=None, label="Unable to verify", emoji="⚪", score=40, category="security"
        ),
        "mint_disabled": MetricVerdict(
            metric="mint_disabled", display_name="Mint Authority",
            value=True, label="Disabled", emoji="🟢", score=100, category="security"
        ),
        "ownership_renounced": MetricVerdict(
            metric="ownership_renounced", display_name="Ownership",
            value=True, label="Renounced", emoji="🟢", score=100, category="security"
        ),
        "has_blacklist": MetricVerdict(
            metric="has_blacklist", display_name="Blacklist",
            value=None, label="Unknown", emoji="⚪", score=60, category="security"
        ),
        "top10_pct": MetricVerdict(
            metric="top10_pct", display_name="Top 10 Holdings",
            value=53.0, label="Concentrated", emoji="🟠", score=35, category="holders"
        ),
        "largest_wallet_pct": MetricVerdict(
            metric="largest_wallet_pct", display_name="Largest Wallet",
            value=31.6, label="Whale alert", emoji="🔴", score=15, category="holders"
        ),
        "lp_locked": MetricVerdict(
            metric="lp_locked", display_name="LP Lock",
            value=True, label="Locked", emoji="🟢", score=100, category="holders"
        ),
        "insider_wallet_count": MetricVerdict(
            metric="insider_wallet_count", display_name="Insider Wallets",
            value=0, label="Very low", emoji="🟢", score=100, category="launch"
        ),
        "dev_wallet_pct": MetricVerdict(
            metric="dev_wallet_pct", display_name="Dev Holdings",
            value=0.8, label="Minimal", emoji="🟢", score=100, category="developer"
        ),
        "dev_sold": MetricVerdict(
            metric="dev_sold", display_name="Dev Sold",
            value=True, label="Dev sold — bearish", emoji="🔴", score=10, category="developer"
        ),
        "volume_mc_ratio": MetricVerdict(
            metric="volume_mc_ratio", display_name="Volume / MC",
            value=23.47, label="Very Strong", emoji="🟢", score=100, category="market"
        ),
        "liq_mc_ratio": MetricVerdict(
            metric="liq_mc_ratio", display_name="Liquidity / MC",
            value=0.633, label="Very Healthy", emoji="🟢", score=100, category="market"
        ),
        "smart_money_wallet_count": MetricVerdict(
            metric="smart_money_wallet_count", display_name="Smart Wallets",
            value=2, label="Low interest", emoji="🟡", score=60, category="smart_money"
        ),
    }

    lr = LoreResult(
        one_line_summary="A Solana token named 'just a rock' with a symbol of 'ROCK' appears to be a memecoin without any clear cultural references.",
        narrative_fit=2,
        originality=9,
        virality=2,
        comparable_tokens=["MEME", "ELON"],
        lore_score=26,
    )

    sr = ScoreResult(
        overall_score=64,
        confidence=0.88,
        category_scores={
            "security": 75,
            "holders": 50,
            "launch": 75,
            "market": 100,
            "developer": 55,
            "lore": 26,
            "smart_money": 60,
        },
        strengths=[
            "Mint Authority: Disabled",
            "Ownership: Renounced",
            "LP Lock: Locked",
            "Insider Wallets: Very low",
        ],
        risks=[
            "Largest Wallet: Whale alert",
            "Dev Sold: Dev sold — bearish",
        ],
        verdict="DEGEN",
    )

    return ScanResult(
        token_data=td,
        rules_result=rr,
        lore_result=lr,
        score_result=sr,
    )


async def main():
    print("Generating test report image...")
    result = _make_mock_result()
    png_bytes = await render_report_image(result)

    out_path = os.path.join(os.path.dirname(__file__), "test_output.png")
    with open(out_path, "wb") as f:
        f.write(png_bytes)

    print(f"Test image saved to {out_path} ({len(png_bytes):,} bytes)")
    print(f"Open it to verify the design matches the target screenshot.")


if __name__ == "__main__":
    asyncio.run(main())
