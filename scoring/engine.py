"""
KhaiScan Scoring Engine — Combines category scores into a weighted
overall score, calculates confidence, and produces the final verdict.
"""
from __future__ import annotations
from models import RulesResult, LoreResult, TokenData, ScoreResult
from rules.config import CATEGORY_WEIGHTS, VERDICT_MAP


def _get_verdict(score: int) -> str:
    for lo, hi, label in VERDICT_MAP:
        if lo <= score <= hi:
            return label
    return "UNKNOWN"


def calculate_score(
    rules_result: RulesResult,
    lore_result: LoreResult | None,
    token_data: TokenData,
) -> ScoreResult:
    """
    Compute the final 0–100 score, confidence %, strengths, risks, and verdict.

    Weighting:
      Security    25%
      Holders     20%
      Launch      15%
      Market      15%
      Lore        10%
      Developer   10%
      Smart Money  5%
    """
    lore_score = lore_result.lore_score if lore_result else 50.0

    category_scores: dict[str, float] = {
        "security":    rules_result.security_score,
        "holders":     rules_result.holder_score,
        "launch":      rules_result.launch_score,
        "developer":   rules_result.dev_score,
        "market":      rules_result.market_score,
        "smart_money": rules_result.smart_money_score,
        "lore":        float(lore_score),
    }

    # Weighted sum
    raw_score = sum(
        category_scores[cat] * weight
        for cat, weight in CATEGORY_WEIGHTS.items()
    )

    # ── Confidence ────────────────────────────────────────────────────
    confidence = (
        token_data.data_fields_available / token_data.data_fields_total
        if token_data.data_fields_total > 0
        else 0.5
    )

    # Apply confidence penalty
    if confidence < 0.4:
        raw_score -= 12
    elif confidence < 0.6:
        raw_score -= 6
    elif confidence < 0.75:
        raw_score -= 2

    overall = max(0, min(100, round(raw_score)))

    # ── Strengths & Risks ─────────────────────────────────────────────
    strengths: list[str] = []
    risks: list[str] = []

    for verdict in rules_result.verdicts.values():
        if verdict.score >= 80:
            strengths.append(f"{verdict.display_name}: {verdict.label}")
        elif verdict.score <= 30:
            risks.append(f"{verdict.display_name}: {verdict.label}")

    # Honeypot is a hard override: cap score at 20 (RUG territory)
    hpot = rules_result.verdicts.get("is_honeypot")
    if hpot and hpot.value is True:
        overall = min(overall, 20)

    return ScoreResult(
        overall_score=overall,
        confidence=round(confidence, 2),
        category_scores=category_scores,
        strengths=strengths[:6],
        risks=risks[:6],
        verdict=_get_verdict(overall),
    )
