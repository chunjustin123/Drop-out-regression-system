import sys
from pathlib import Path

# Ensure project root is on sys.path for `src` imports when run via Streamlit
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path as _PathAlias

from src.ingestion import load_inputs, fuse_student_level_dataset, fuse_from_frames
from src.rules import score_rules, RuleThresholds
from src.model import predict as model_predict

st.set_page_config(page_title="Drop-out Risk Dashboard", layout="wide")

# Simple theming via CSS
st.markdown(
    """
    <style>
    .risk-badge { padding: 2px 8px; border-radius: 999px; font-weight: 600; }
    .risk-High { background:#ffcccc; color:#9b0000; }
    .risk-Medium { background:#fff4cc; color:#9b6b00; }
    .risk-Low { background:#e8ffe8; color:#006b00; }
    .metric-card { background:#f8f9fb; border:1px solid #e9edf2; padding:16px; border-radius:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Drop-out Risk Dashboard")

with st.sidebar:
    st.header("Data Inputs")
    inputs_dir = _PathAlias(st.text_input("Inputs directory (optional)", value="data/inputs"))
    st.caption("Or upload files below (CSV/XLSX). Uploaded files override folder inputs.")
    att_file = st.file_uploader("Attendance file", type=["csv", "xlsx"], key="att")
    ass_file = st.file_uploader("Assessments file", type=["csv", "xlsx"], key="ass")
    fee_file = st.file_uploader("Fees file", type=["csv", "xlsx"], key="fee")

    st.divider()
    st.header("Risk Thresholds")
    min_att = st.slider("Min attendance rate", 0.0, 1.0, 0.80, 0.01)
    min_score = st.slider("Min average score", 0.0, 100.0, 50.0, 1.0)
    max_balance = st.number_input("Max outstanding balance", value=0.0, step=100.0)

# Helper to read uploaded file
@st.cache_data(show_spinner=False)
def _read_uploaded(file) -> pd.DataFrame:
    if file is None:
        return pd.DataFrame()
    name = file.name.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(file)
    return pd.read_csv(file)

@st.cache_data(show_spinner=False)
def _compute_from_uploads(att_file, ass_file, fee_file, min_att, min_score, max_balance):
    att_df = _read_uploaded(att_file)
    ass_df = _read_uploaded(ass_file)
    fee_df = _read_uploaded(fee_file)
    if att_df.empty or ass_df.empty or fee_df.empty:
        return None, None
    merged = fuse_from_frames(att_df, ass_df, fee_df)
    rules_df = score_rules(
        merged, RuleThresholds(min_attendance_rate=min_att, min_avg_score=min_score, max_balance_outstanding=max_balance)
    )
    return merged, rules_df

@st.cache_data(show_spinner=False)
def _compute_from_folder(inputs_dir, min_att, min_score, max_balance):
    inputs = load_inputs(inputs_dir)
    merged = fuse_student_level_dataset(inputs)
    rules_df = score_rules(
        merged, RuleThresholds(min_attendance_rate=min_att, min_avg_score=min_score, max_balance_outstanding=max_balance)
    )
    return merged, rules_df

# Prefer uploads; fallback to folder
if att_file and ass_file and fee_file:
    merged, rules_df = _compute_from_uploads(att_file, ass_file, fee_file, min_att, min_score, max_balance)
else:
    try:
        merged, rules_df = _compute_from_folder(inputs_dir, min_att, min_score, max_balance)
    except Exception:
        merged, rules_df = None, None
        st.warning("Provide all three uploads or ensure files exist in the folder.")

if merged is None:
    st.info("Upload attendance, assessments, and fees files, or set a folder with inputs.")
    st.stop()

# Try model predictions if available (folder-based only)
try:
    model_df = model_predict(inputs_dir) if not (att_file and ass_file and fee_file) else None
    if model_df is not None:
        df = rules_df.merge(model_df, on="student_id", how="left")
    else:
        df = rules_df
except Exception:
    df = rules_df

# Filters
st.subheader("Filters")
fc1, fc2, fc3, fc4 = st.columns([1,1,1,2])
sel_levels = fc1.multiselect("Risk level", options=["High", "Medium", "Low"], default=["High", "Medium", "Low"])
min_att_f = fc2.slider("Min att.", 0.0, 1.0, 0.0, 0.01)
min_score_f = fc3.slider("Min score", 0.0, 100.0, 0.0, 1.0)
search_id = fc4.text_input("Search student_id contains", "")

fdf = df.copy()
if sel_levels:
    fdf = fdf[fdf["rule_risk_level"].astype(str).isin(sel_levels)]
if min_att_f > 0:
    fdf = fdf[fdf["attendance_rate"] >= min_att_f]
if min_score_f > 0:
    fdf = fdf[fdf["avg_score"] >= min_score_f]
if search_id:
    fdf = fdf[fdf["student_id"].astype(str).str.contains(search_id, case=False)]

# KPIs
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"<div class='metric-card'><h4>Students</h4><h2>{fdf.shape[0]}</h2></div>", unsafe_allow_html=True)
with k2:
    st.markdown(f"<div class='metric-card'><h4>Avg Attendance</h4><h2>{fdf['attendance_rate'].mean():.2f}</h2></div>", unsafe_allow_html=True)
with k3:
    st.markdown(f"<div class='metric-card'><h4>Avg Score</h4><h2>{fdf['avg_score'].mean():.1f}</h2></div>", unsafe_allow_html=True)
with k4:
    st.markdown(f"<div class='metric-card'><h4>Outstanding Total</h4><h2>{fdf['balance_outstanding'].sum():,.0f}</h2></div>", unsafe_allow_html=True)

# Tabs
tab_overview, tab_students, tab_trends, tab_settings = st.tabs(["Overview", "Students", "Trends", "Settings"])

with tab_overview:
    # Risk breakdown
    risk_counts = fdf["rule_risk_level"].astype(str).value_counts().reindex(["High","Medium","Low"]).fillna(0).reset_index()
    risk_counts.columns = ["risk", "count"]
    chart = alt.Chart(risk_counts).mark_bar().encode(
        x=alt.X("risk", sort=None), y="count", color=alt.Color("risk", scale=alt.Scale(domain=["High","Medium","Low"], range=["#ffcccc","#fff4cc","#e8ffe8"]))
    )
    st.altair_chart(chart, use_container_width=True)

    # Scatter
    scatter = alt.Chart(fdf).mark_circle(size=120, opacity=0.7).encode(
        x=alt.X("attendance_rate", title="Attendance Rate"),
        y=alt.Y("avg_score", title="Average Score"),
        color=alt.Color("rule_risk_level:N", scale=alt.Scale(domain=["High","Medium","Low"], range=["#ff6b6b","#f7c948","#51cf66"])),
        tooltip=["student_id","attendance_rate","avg_score","balance_outstanding","rule_risk_level"]
    )
    st.altair_chart(scatter, use_container_width=True)

with tab_students:
    # Risk badge column
    def badge(level: str) -> str:
        return f"<span class='risk-badge risk-{level}'>{level}</span>"

    table_cols = [
        "student_id",
        "attendance_rate",
        "avg_score",
        "balance_outstanding",
        "rule_risk_points",
        "rule_risk_level",
    ]
    if "model_risk_score" in fdf.columns:
        table_cols.append("model_risk_score")
    tdf = fdf[table_cols].copy()
    tdf["risk"] = tdf["rule_risk_level"].astype(str).apply(badge)
    st.dataframe(
        tdf.drop(columns=["rule_risk_level"]).style.format(precision=2).hide(axis="index").to_html(escape=False),
        use_container_width=True,
    )

    st.divider()
    st.subheader("Student Detail")
    colA, colB = st.columns([1,2])
    with colA:
        student_id = st.selectbox("Select student", fdf["student_id"].astype(str).tolist())
    with colB:
        srow = fdf[fdf["student_id"].astype(str) == str(student_id)].iloc[0]
        st.markdown(
            f""
            f"<div class='metric-card'><h3>Student {student_id}</h3>"
            f"<p>Risk: <span class='risk-badge risk-{str(srow['rule_risk_level'])}'>{str(srow['rule_risk_level'])}</span></p>"
            f"<p>Attendance: {float(srow['attendance_rate']):.2f}</p>"
            f"<p>Average Score: {float(srow['avg_score']):.1f}</p>"
            f"<p>Outstanding: {float(srow['balance_outstanding']):,.0f}</p>"
            f"</div>"
            f"",
            unsafe_allow_html=True,
        )

with tab_trends:
    st.caption("Trends across current dataset")
    # Attendance histogram
    hist_att = alt.Chart(fdf).mark_bar(opacity=0.8).encode(
        x=alt.X("attendance_rate", bin=alt.Bin(maxbins=20)), y="count()"
    )
    st.altair_chart(hist_att, use_container_width=True)

    # Score histogram
    hist_score = alt.Chart(fdf).mark_bar(opacity=0.8).encode(
        x=alt.X("avg_score", bin=alt.Bin(maxbins=20)), y="count()"
    )
    st.altair_chart(hist_score, use_container_width=True)

with tab_settings:
    st.write("Download current results")
    csv_all = fdf.to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered table (CSV)", data=csv_all, file_name="risk_table.csv", mime="text/csv")

    if 'model_risk_score' in fdf.columns:
        st.caption("Model scores included where available (folder mode).")

# Manual refresh button
if st.button("Refresh"):
    st.rerun()
