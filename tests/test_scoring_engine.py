"""
Unit tests for the KhaiScan Scoring Engine.

Tests weighted score calculation, confidence degradation,
verdict label mapping, and honeypot hard override.
"""
import pytest
from models import TokenData, RulesResult, LoreResult, MetricVerdict
from scoring.engine import calculate_score, _get_verdict


def _rules(
    security: float = 80,
    holders: float = 80,
    launch: float = 80,
    dev: float = 80,
    market: float = 80,
    smart_money: float = 80,
) -> RulesResult:
    """Helper: create a RulesResult with given category scores."""
    return RulesResult(
        verdicts={},
        security_score=security,
        holder_score=holders,
        launch_score=launch,
        dev_score=dev,
        market_score=market,
        smart_money_score=smart_money,
    )


def _lore(score: int = 80) -> LoreResult:
    return LoreResult(
        one_line_summary="Test summary",
        narrative_fit=8,
        originality=7,
        virality=8,
        comparable_tokens=["PEPE"],
        lore_score=score,
    )


def _token(available: int = 14, total: int = 16) -> TokenData:
    """Helper: create token with controlled confidence."""
    td = TokenData(address="test", chain="solana")
    td.data_fields_available = available
    td.data_fields_total = total
    return td


# ──────────────────────────────────────────────────────────────────────
# Verdict label mapping
# ──────────────────────────────────────────────────────────────────────

class TestVerdictMapping:
    @pytest.mark.parametrize("score,expected", [
        (0,   "RUG"),
        (10,  "RUG"),
        (20,  "RUG"),
        (21,  "AVOID"),
        (40,  "AVOID"),
        (41,  "RISKY"),
        (55,  "RISKY"),
        (56,  "DEGEN"),
        (70,  "DEGEN"),
        (71,  "SOLID"),
        (85,  "SOLID"),
        (86,  "GEM"),
        (100, "GEM"),
    ])
    def test_verdict_boundaries(self, score, expected):
        assert _get_verdict(score) == expected


# ──────────────────────────────────────────────────────────────────────
# Score calculation
# ──────────────────────────────────────────────────────────────────────

class TestScoreCalculation:
    def test_all_80_scores_gives_solid(self):
        result = calculate_score(_rules(), _lore(80), _token())
        # Security(80)*0.25 + Holders(80)*0.20 + Launch(80)*0.15 +
        # Market(80)*0.15 + Lore(80)*0.10 + Dev(80)*0.10 + SM(80)*0.05 = 80
        assert 75 <= result.overall_score <= 85
        assert result.verdict in ("SOLID", "GEM")

    def test_all_100_gives_gem(self):
        result = calculate_score(
            _rules(100, 100, 100, 100, 100, 100),
            _lore(100),
            _token(16, 16),
        )
        assert result.overall_score >= 86
        assert result.verdict == "GEM"

    def test_all_0_gives_rug(self):
        result = calculate_score(
            _rules(0, 0, 0, 0, 0, 0),
            _lore(0),
            _token(8, 16),
        )
        assert result.overall_score <= 20
        assert result.verdict in ("RUG", "AVOID")

    def test_weights_sum_correctly(self):
        # Only security perfect (100), everything else 0
        # Expected ≈ 100 * 0.25 = 25 → AVOID
        result = calculate_score(
            _rules(security=100, holders=0, launch=0, dev=0, market=0, smart_money=0),
            _lore(0),
            _token(14, 16),
        )
        # Lore weight 0.10 = 0 (lore score 0), so security 25% = 25
        assert 20 <= result.overall_score <= 32


# ──────────────────────────────────────────────────────────────────────
# Confidence
# ──────────────────────────────────────────────────────────────────────

class TestConfidence:
    def test_full_data_no_penalty(self):
        result = calculate_score(_rules(80, 80, 80, 80, 80, 80), _lore(80), _token(16, 16))
        assert result.confidence == 1.0
        # Score should not be penalised
        assert result.overall_score >= 75

    def test_low_confidence_penalises_score(self):
        full_result = calculate_score(
            _rules(80, 80, 80, 80, 80, 80), _lore(80), _token(16, 16)
        )
        low_result = calculate_score(
            _rules(80, 80, 80, 80, 80, 80), _lore(80), _token(4, 16)
        )
        # Low confidence should result in a lower score
        assert low_result.overall_score < full_result.overall_score

    def test_confidence_value_range(self):
        result = calculate_score(_rules(), _lore(), _token(10, 16))
        assert 0.0 <= result.confidence <= 1.0

    def test_zero_total_fields_defaults_confidence(self):
        td = TokenData(address="t", chain="solana")
        td.data_fields_total = 0
        td.data_fields_available = 0
        result = calculate_score(_rules(), _lore(), td)
        assert 0.0 <= result.confidence <= 1.0


# ──────────────────────────────────────────────────────────────────────
# Honeypot hard override
# ──────────────────────────────────────────────────────────────────────

class TestHoneypotOverride:
    def test_honeypot_caps_score_at_20(self):
        # Even with great scores everywhere else, honeypot = instant RUG cap
        rr = _rules(100, 100, 100, 100, 100, 100)
        rr.verdicts["is_honeypot"] = MetricVerdict(
            metric="is_honeypot",
            display_name="Honeypot Risk",
            value=True,
            label="HONEYPOT DETECTED",
            emoji="🔴",
            score=0,
            category="security",
        )
        result = calculate_score(rr, _lore(100), _token(16, 16))
        assert result.overall_score <= 20
        assert result.verdict == "RUG"


# ──────────────────────────────────────────────────────────────────────
# Strengths and risks
# ──────────────────────────────────────────────────────────────────────

class TestStrengthsAndRisks:
    def test_high_score_verdicts_appear_in_strengths(self):
        from models import MetricVerdict
        rr = _rules()
        rr.verdicts["top10_pct"] = MetricVerdict(
            metric="top10_pct",
            display_name="Top 10 Holdings",
            value=20.0,
            label="Healthy",
            emoji="🟢",
            score=100,
            category="holders",
        )
        result = calculate_score(rr, _lore(), _token())
        assert any("Top 10" in s for s in result.strengths)

    def test_low_score_verdicts_appear_in_risks(self):
        from models import MetricVerdict
        rr = _rules()
        rr.verdicts["bundle_pct"] = MetricVerdict(
            metric="bundle_pct",
            display_name="Bundle Activity",
            value=30.0,
            label="High Risk",
            emoji="🔴",
            score=10,
            category="launch",
        )
        result = calculate_score(rr, _lore(), _token())
        assert any("Bundle" in r for r in result.risks)
