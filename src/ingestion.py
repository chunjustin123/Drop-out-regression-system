from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import pandas as pd


@dataclass
class InputPaths:
    attendance: Path
    assessments: Path
    fees: Path


DEFAULT_MAPPINGS: Dict[str, Dict[str, str]] = {
    "attendance": {"student_id": "student_id", "date": "date", "present": "present"},
    "assessments": {
        "student_id": "student_id",
        "assessment_name": "assessment_name",
        "score": "score",
    },
    "fees": {
        "student_id": "student_id",
        "amount_due": "amount_due",
        "amount_paid": "amount_paid",
        "due_date": "due_date",
    },
}


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def load_inputs(inputs_dir: Path) -> InputPaths:
    def _pick(name: str) -> Path:
        for ext in [".csv", ".xlsx", ".xls"]:
            p = inputs_dir / f"{name}{ext}"
            if p.exists():
                return p
        # default to CSV path even if missing; callers will handle errors
        return inputs_dir / f"{name}.csv"

    return InputPaths(
        attendance=_pick("attendance"),
        assessments=_pick("assessments"),
        fees=_pick("fees"),
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _auto_map_attendance(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(df)
    # Student id
    for cand in ["student_id", "id", "student", "regno", "reg_no", "index_no", "admission_no"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_id"}, inplace=True)
            break
    # Student name (optional)
    for cand in ["student_name", "name", "full_name"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_name"}, inplace=True)
            break
    # Student language (optional)
    for cand in ["language", "lang", "preferred_language", "mother_tongue", "native_language"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_language"}, inplace=True)
            break
    # Date
    for cand in ["date", "attendance_date", "day", "recorded_date"]:
        if cand in df.columns:
            df.rename(columns={cand: "date"}, inplace=True)
            break
    # Present (boolean/flag)
    present_cands = [
        "present",
        "is_present",
        "attendance",
        "status",
        "attended",
        "present_flag",
        "p",
        "attendance_mark",
    ]
    for cand in present_cands:
        if cand in df.columns:
            df.rename(columns={cand: "present"}, inplace=True)
            break
    if "present" in df.columns:
        series = df["present"].astype(str).str.strip().str.lower()
        mapping = {"1": 1, "0": 0, "true": 1, "false": 0, "yes": 1, "no": 0, "y": 1, "n": 0, "p": 1, "a": 0}
        mapped = series.map(mapping)
        df["present"] = pd.to_numeric(mapped, errors="coerce").fillna(0).astype(int)
    return df


def _auto_map_assessments(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(df)
    for cand in ["student_id", "id", "student", "regno", "reg_no", "index_no", "admission_no"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_id"}, inplace=True)
            break
    for cand in ["student_name", "name", "full_name"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_name"}, inplace=True)
            break
    # Student language (optional)
    for cand in ["language", "lang", "preferred_language", "mother_tongue", "native_language"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_language"}, inplace=True)
            break
    for cand in ["assessment_name", "exam", "test", "assessment", "component", "name"]:
        if cand in df.columns:
            df.rename(columns={cand: "assessment_name"}, inplace=True)
            break
    for cand in ["score", "marks", "mark", "grade_value", "percentage"]:
        if cand in df.columns:
            df.rename(columns={cand: "score"}, inplace=True)
            break
    if "score" in df.columns:
        df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)
    else:
        df["score"] = 0.0
    return df


def _auto_map_fees(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(df)
    for cand in ["student_id", "id", "student", "regno", "reg_no", "index_no", "admission_no"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_id"}, inplace=True)
            break
    for cand in ["student_name", "name", "full_name"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_name"}, inplace=True)
            break
    # Student language (optional)
    for cand in ["language", "lang", "preferred_language", "mother_tongue", "native_language"]:
        if cand in df.columns:
            df.rename(columns={cand: "student_language"}, inplace=True)
            break
    for cand in ["amount_due", "due", "fee_due", "total_due"]:
        if cand in df.columns:
            df.rename(columns={cand: "amount_due"}, inplace=True)
            break
    for cand in ["amount_paid", "paid", "fee_paid", "total_paid"]:
        if cand in df.columns:
            df.rename(columns={cand: "amount_paid"}, inplace=True)
            break
    for cand in ["due_date", "deadline", "last_date", "date"]:
        if cand in df.columns:
            df.rename(columns={cand: "due_date"}, inplace=True)
            break
    if "amount_due" in df.columns:
        df["amount_due"] = pd.to_numeric(df["amount_due"], errors="coerce").fillna(0.0)
    else:
        df["amount_due"] = 0.0
    if "amount_paid" in df.columns:
        df["amount_paid"] = pd.to_numeric(df["amount_paid"], errors="coerce").fillna(0.0)
    else:
        df["amount_paid"] = 0.0
    return df


def fuse_student_level_dataset(
    inputs: InputPaths, mappings: Optional[Dict[str, Dict[str, str]]] = None
) -> pd.DataFrame:
    mappings = mappings or DEFAULT_MAPPINGS

    att = _read_table(inputs.attendance)
    ass = _read_table(inputs.assessments)
    fee = _read_table(inputs.fees)

    att = _normalize_columns(att).rename(columns=mappings["attendance"]) if mappings else _normalize_columns(att)
    ass = _normalize_columns(ass).rename(columns=mappings["assessments"]) if mappings else _normalize_columns(ass)
    fee = _normalize_columns(fee).rename(columns=mappings["fees"]) if mappings else _normalize_columns(fee)

    att = _auto_map_attendance(att)
    ass = _auto_map_assessments(ass)
    fee = _auto_map_fees(fee)

    return _aggregate_frames(att, ass, fee)


def fuse_from_frames(
    attendance_df: pd.DataFrame,
    assessments_df: pd.DataFrame,
    fees_df: pd.DataFrame,
    mappings: Optional[Dict[str, Dict[str, str]]] = None,
) -> pd.DataFrame:
    mappings = mappings or DEFAULT_MAPPINGS
    att = _normalize_columns(attendance_df).rename(columns=mappings["attendance"]) if mappings else _normalize_columns(attendance_df)
    ass = _normalize_columns(assessments_df).rename(columns=mappings["assessments"]) if mappings else _normalize_columns(assessments_df)
    fee = _normalize_columns(fees_df).rename(columns=mappings["fees"]) if mappings else _normalize_columns(fees_df)

    att = _auto_map_attendance(att)
    ass = _auto_map_assessments(ass)
    fee = _auto_map_fees(fee)

    return _aggregate_frames(att, ass, fee)


def _aggregate_frames(att: pd.DataFrame, ass: pd.DataFrame, fee: pd.DataFrame) -> pd.DataFrame:
    # Attendance aggregation: attendance_rate per student
    if "present" not in att.columns:
        raise KeyError("Attendance file must contain a 'present' or equivalent column (e.g., status, attended, p/a).")
    if "student_id" not in att.columns:
        raise KeyError("Attendance file must contain a 'student_id' column.")

    att["present"] = pd.to_numeric(att["present"], errors="coerce").fillna(0).astype(int)
    att_agg = (
        att.groupby("student_id")["present"].agg(["sum", "count"]).rename(columns={"sum": "days_present", "count": "days_total"})
    )
    att_agg["attendance_rate"] = (att_agg["days_present"] / att_agg["days_total"]).fillna(0.0)

    # Assessments aggregation: mean score per student
    if "student_id" not in ass.columns:
        raise KeyError("Assessments file must contain a 'student_id' column.")
    if "score" not in ass.columns:
        ass["score"] = 0.0
    ass["score"] = pd.to_numeric(ass["score"], errors="coerce").fillna(0.0)
    ass_agg = ass.groupby("student_id")["score"].mean().to_frame("avg_score").reset_index().set_index("student_id")

    # Fees aggregation: outstanding balance per student
    if "student_id" not in fee.columns:
        raise KeyError("Fees file must contain a 'student_id' column.")
    if "amount_due" not in fee.columns:
        fee["amount_due"] = 0.0
    if "amount_paid" not in fee.columns:
        fee["amount_paid"] = 0.0
    fee["amount_due"] = pd.to_numeric(fee["amount_due"], errors="coerce").fillna(0.0)
    fee["amount_paid"] = pd.to_numeric(fee["amount_paid"], errors="coerce").fillna(0.0)
    fee_agg = fee.groupby("student_id").apply(
        lambda g: pd.Series({
            "amount_due_total": g["amount_due"].sum(),
            "amount_paid_total": g["amount_paid"].sum(),
        })
    )
    fee_agg["balance_outstanding"] = (
        fee_agg["amount_due_total"] - fee_agg["amount_paid_total"]
    ).clip(lower=0)

    # Merge all to student level
    merged = (
        att_agg.join(ass_agg, how="outer")
        .join(fee_agg, how="outer")
        .reset_index()
        .fillna(0)
    )

    # Attach student_name if available from any input frame
    name_series = None
    if "student_name" in att.columns:
        name_series = att.groupby("student_id")["student_name"].first()
    if "student_name" in ass.columns:
        s = ass.groupby("student_id")["student_name"].first()
        name_series = s if name_series is None else name_series.combine_first(s)
    if "student_name" in fee.columns:
        s = fee.groupby("student_id")["student_name"].first()
        name_series = s if name_series is None else name_series.combine_first(s)
    
    # Attach student_language if available from any input frame
    language_series = None
    if "student_language" in att.columns:
        language_series = att.groupby("student_id")["student_language"].first()
    if "student_language" in ass.columns:
        s = ass.groupby("student_id")["student_language"].first()
        language_series = s if language_series is None else language_series.combine_first(s)
    if "student_language" in fee.columns:
        s = fee.groupby("student_id")["student_language"].first()
        language_series = s if language_series is None else language_series.combine_first(s)
    
    if name_series is not None or language_series is not None:
        merged = merged.set_index("student_id")
        if name_series is not None:
            merged["student_name"] = name_series
        if language_series is not None:
            merged["student_language"] = language_series
        merged = merged.reset_index()

    return merged
