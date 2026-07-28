"""
Unit tests for the KhaiScan Rules Engine.

Tests every threshold boundary and boolean verdict for all configured metrics.
"""
import pytest
from models import TokenData
from rules.engine import apply_rules


def _token(**kwargs) -> TokenData:
    """Helper: create a TokenData with given fields."""
    return TokenData(address="test", chain="solana", **kwargs)


# ──────────────────────────────────────────────────────────────────────
# SECURITY — Honeypot
# ──────────────────────────────────────────────────────────────────────

class TestHoneypot:
    def test_no_honeypot_scores_100(self):
        result = apply_rules(_token(is_honeypot=False))
        v = result.verdicts["is_honeypot"]
        assert v.score == 100
        assert v.emoji == "🟢"

    def test_honeypot_scores_0(self):
        result = apply_rules(_token(is_honeypot=True))
        v = result.verdicts["is_honeypot"]
        assert v.score == 0
        assert v.emoji == "🔴"

    def test_unknown_honeypot_scores_neutral(self):
        result = apply_rules(_token(is_honeypot=None))
        v = result.verdicts["is_honeypot"]
        assert 30 <= v.score <= 60


# ──────────────────────────────────────────────────────────────────────
# SECURITY — Mint Authority
# ──────────────────────────────────────────────────────────────────────

class TestMintDisabled:
    def test_disabled_mint_scores_100(self):
        result = apply_rules(_token(mint_disabled=True))
        assert result.verdicts["mint_disabled"].score == 100

    def test_active_mint_scores_low(self):
        result = apply_rules(_token(mint_disabled=False))
        assert result.verdicts["mint_disabled"].score <= 20


# ──────────────────────────────────────────────────────────────────────
# SECURITY — Tax
# ──────────────────────────────────────────────────────────────────────

class TestTax:
    def test_zero_buy_tax(self):
        result = apply_rules(_token(buy_tax=0.0))
        v = result.verdicts["buy_tax"]
        assert v.score == 100

    def test_low_buy_tax_is_acceptable(self):
        result = apply_rules(_token(buy_tax=3.0))
        v = result.verdicts["buy_tax"]
        assert v.score >= 75

    def test_moderate_buy_tax(self):
        result = apply_rules(_token(buy_tax=7.0))
        v = result.verdicts["buy_tax"]
        assert 40 <= v.score <= 60

    def test_high_buy_tax_scores_low(self):
        result = apply_rules(_token(buy_tax=15.0))
        v = result.verdicts["buy_tax"]
        assert v.score <= 15

    def test_zero_sell_tax(self):
        result = apply_rules(_token(sell_tax=0.0))
        assert result.verdicts["sell_tax"].score == 100


# ──────────────────────────────────────────────────────────────────────
# HOLDER HEALTH — Top 10
# ──────────────────────────────────────────────────────────────────────

class TestTop10Holdings:
    def test_healthy_below_30(self):
        result = apply_rules(_token(top10_pct=25.0))
        assert result.verdicts["top10_pct"].score == 100
        assert result.verdicts["top10_pct"].emoji == "🟢"

    def test_moderate_30_to_40(self):
        result = apply_rules(_token(top10_pct=35.0))
        v = result.verdicts["top10_pct"]
        assert 55 <= v.score <= 75

    def test_concentrated_40_to_60(self):
        result = apply_rules(_token(top10_pct=50.0))
        v = result.verdicts["top10_pct"]
        assert v.score <= 40

    def test_high_risk_above_60(self):
        result = apply_rules(_token(top10_pct=75.0))
        assert result.verdicts["top10_pct"].score <= 15

    def test_missing_data_is_neutral(self):
        result = apply_rules(_token(top10_pct=None))
        assert result.verdicts["top10_pct"].score == 50


# ──────────────────────────────────────────────────────────────────────
# HOLDER HEALTH — Largest Wallet
# ──────────────────────────────────────────────────────────────────────

class TestLargestWallet:
    def test_excellent_under_3_5(self):
        result = apply_rules(_token(largest_wallet_pct=2.0))
        assert result.verdicts["largest_wallet_pct"].score == 100

    def test_good_3_5_to_5(self):
        result = apply_rules(_token(largest_wallet_pct=4.0))
        v = result.verdicts["largest_wallet_pct"]
        assert 75 <= v.score <= 85

    def test_watch_5_to_10(self):
        result = apply_rules(_token(largest_wallet_pct=7.0))
        v = result.verdicts["largest_wallet_pct"]
        assert 40 <= v.score <= 60

    def test_whale_above_10(self):
        result = apply_rules(_token(largest_wallet_pct=15.0))
        assert result.verdicts["largest_wallet_pct"].score <= 20


# ──────────────────────────────────────────────────────────────────────
# LAUNCH — Bundles
# ──────────────────────────────────────────────────────────────────────

class TestBundles:
    def test_clean_launch(self):
        result = apply_rules(_token(bundle_pct=2.0))
        assert result.verdicts["bundle_pct"].score == 100

    def test_acceptable_launch(self):
        result = apply_rules(_token(bundle_pct=7.0))
        v = result.verdicts["bundle_pct"]
        assert 70 <= v.score <= 80

    def test_elevated_bundle(self):
        result = apply_rules(_token(bundle_pct=12.0))
        v = result.verdicts["bundle_pct"]
        assert 40 <= v.score <= 60

    def test_manipulated_launch(self):
        result = apply_rules(_token(bundle_pct=25.0))
        assert result.verdicts["bundle_pct"].score <= 15


# ──────────────────────────────────────────────────────────────────────
# MARKET — Volume / MC
# ──────────────────────────────────────────────────────────────────────

class TestVolumeRatio:
    def test_very_weak_volume(self):
        result = apply_rules(_token(volume_mc_ratio=0.05))
        assert result.verdicts["volume_mc_ratio"].score <= 15

    def test_weak_volume(self):
        result = apply_rules(_token(volume_mc_ratio=0.3))
        v = result.verdicts["volume_mc_ratio"]
        assert 35 <= v.score <= 45

    def test_healthy_volume(self):
        result = apply_rules(_token(volume_mc_ratio=0.8))
        v = result.verdicts["volume_mc_ratio"]
        assert 60 <= v.score <= 70

    def test_strong_volume(self):
        result = apply_rules(_token(volume_mc_ratio=2.0))
        v = result.verdicts["volume_mc_ratio"]
        assert 80 <= v.score <= 90

    def test_very_strong_volume(self):
        result = apply_rules(_token(volume_mc_ratio=5.0))
        assert result.verdicts["volume_mc_ratio"].score == 100


# ──────────────────────────────────────────────────────────────────────
# Category score aggregation
# ──────────────────────────────────────────────────────────────────────

class TestCategoryScores:
    def test_all_clean_security_scores_high(self):
        result = apply_rules(_token(
            is_honeypot=False,
            mint_disabled=True,
            ownership_renounced=True,
            has_blacklist=False,
            buy_tax=0.0,
            sell_tax=0.0,
        ))
        assert result.security_score >= 90

    def test_all_bad_security_scores_low(self):
        result = apply_rules(_token(
            is_honeypot=True,
            mint_disabled=False,
            ownership_renounced=False,
            has_blacklist=True,
            buy_tax=20.0,
            sell_tax=20.0,
        ))
        assert result.security_score <= 30

    def test_missing_data_gives_neutral_score(self):
        result = apply_rules(_token())  # All None
        # All unknowns should produce roughly neutral scores
        assert 35 <= result.security_score <= 65
        assert 35 <= result.holder_score <= 65
