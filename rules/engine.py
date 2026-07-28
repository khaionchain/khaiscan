"""
KhaiScan Rules Engine — Applies rule thresholds to TokenData and produces
per-metric verdicts and per-category scores.
"""
from __future__ import annotations
from typing import Optional
from models import TokenData, RulesResult, MetricVerdict
from rules.config import RULES


def _range_verdict(name: str, cfg: dict, value: Optional[float]) -> MetricVerdict:
    """Match a numeric value against sorted threshold bands."""
    if value is None:
        return MetricVerdict(
            metric=name,
            display_name=cfg["display"],
            value=None,
            label="No data",
            emoji="⚪",
            score=50,
            category=cfg["category"],
        )
    for (lo, hi, label, emoji, score) in cfg["thresholds"]:
        if lo <= value < hi or (value == hi and hi == lo):
            return MetricVerdict(
                metric=name,
                display_name=cfg["display"],
                value=value,
                label=label,
                emoji=emoji,
                score=score,
                category=cfg["category"],
            )
    # Fall through: use last band for values above all thresholds
    lo, hi, label, emoji, score = cfg["thresholds"][-1]
    return MetricVerdict(
        metric=name,
        display_name=cfg["display"],
        value=value,
        label=label,
        emoji=emoji,
        score=score,
        category=cfg["category"],
    )


def _bool_verdict(name: str, cfg: dict, value) -> MetricVerdict:
    """Match a boolean (or None) value to its verdict."""
    label, emoji, score = cfg["values"].get(value, ("Unknown", "⚪", 50))
    return MetricVerdict(
        metric=name,
        display_name=cfg["display"],
        value=value,
        label=label,
        emoji=emoji,
        score=score,
        category=cfg["category"],
    )


def _category_avg(verdicts: dict, category: str) -> float:
    """Average score for all metrics in a category."""
    scores = [v.score for v in verdicts.values() if v.category == category]
    return round(sum(scores) / len(scores), 1) if scores else 50.0


def apply_rules(token_data: TokenData) -> RulesResult:
    """
    Apply all configured rules to a TokenData object.

    Returns a RulesResult with per-metric verdicts and per-category scores.
    """
    verdicts: dict[str, MetricVerdict] = {}

    for name, cfg in RULES.items():
        # Read raw value from token_data (derived fields already computed)
        value = getattr(token_data, name, None)

        if cfg["type"] == "range":
            verdict = _range_verdict(name, cfg, value)
        else:
            verdict = _bool_verdict(name, cfg, value)

        verdicts[name] = verdict

    return RulesResult(
        verdicts=verdicts,
        security_score=_category_avg(verdicts, "security"),
        holder_score=_category_avg(verdicts, "holders"),
        launch_score=_category_avg(verdicts, "launch"),
        dev_score=_category_avg(verdicts, "developer"),
        market_score=_category_avg(verdicts, "market"),
        smart_money_score=_category_avg(verdicts, "smart_money"),
    )
