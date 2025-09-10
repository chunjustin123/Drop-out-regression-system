from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import pandas as pd


@dataclass
class RuleThresholds:
    min_attendance_rate: float = 0.80
    min_avg_score: float = 50.0
    max_balance_outstanding: float = 0.0


def score_rules(df: pd.DataFrame, thresholds: RuleThresholds | Dict) -> pd.DataFrame:
    if isinstance(thresholds, dict):
        thresholds = RuleThresholds(**thresholds)

    df = df.copy()
    risk_points = 0

    # Attendance rule
    df["r_attendance"] = (df["attendance_rate"] < thresholds.min_attendance_rate).astype(int)
    risk_points += df["r_attendance"]

    # Academic rule
    df["r_scores"] = (df["avg_score"] < thresholds.min_avg_score).astype(int)
    risk_points += df["r_scores"]

    # Fees rule
    df["r_fees"] = (df["balance_outstanding"] > thresholds.max_balance_outstanding).astype(int)
    risk_points += df["r_fees"]

    df["rule_risk_points"] = df[["r_attendance", "r_scores", "r_fees"]].sum(axis=1)
    df["rule_risk_level"] = pd.cut(
        df["rule_risk_points"], bins=[-1, 0, 1, 3], labels=["Low", "Medium", "High"]
    )
    return df
