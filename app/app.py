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
from io import BytesIO
from typing import Optional
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Optional translation support
try:
    from deep_translator import GoogleTranslator as _GoogleTranslator  # type: ignore
except Exception:
    _GoogleTranslator = None  # type: ignore

# Map language codes to recommended Noto font filenames (TTF)
_LANG_TO_NOTO_TTF = {
    "hi": "NotoSansDevanagari-Regular.ttf",
    "mr": "NotoSansDevanagari-Regular.ttf",
    "ne": "NotoSansDevanagari-Regular.ttf",
    "bn": "NotoSansBengali-Regular.ttf",
    "te": "NotoSansTelugu-Regular.ttf",
    "gu": "NotoSansGujarati-Regular.ttf",
    "kn": "NotoSansKannada-Regular.ttf",
    "ml": "NotoSansMalayalam-Regular.ttf",
    "pa": "NotoSansGurmukhi-Regular.ttf",
    "ur": "NotoSansArabic-Regular.ttf",
    "si": "NotoSansSinhala-Regular.ttf",
    "ta": "NotoSansTamil-Regular.ttf",
}

# Common regional languages (can extend as needed)
_LANGUAGES = {
    "English (original)": "en",
    "Hindi": "hi",
    "Bengali": "bn",
    "Telugu": "te",
    "Marathi": "mr",
    "Tamil": "ta",
    "Gujarati": "gu",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Punjabi": "pa",
    "Urdu": "ur",
    "Nepali": "ne",
    "Sinhala": "si",
}

# Default letter template
_DEFAULT_TEMPLATE = (
    "Date: {date}\n\n"
    "Dear Parent/Guardian of {student_name} (Student ID: {student_id}),\n\n"
    "We are writing to inform you that your child has been identified as at High risk of school drop-out based on our monitoring indicators.\n\n"
    "Key indicators:\n"
    "- Attendance: {attendance_pct:.1f}%\n"
    "- Average Score: {avg_score:.1f}\n"
    "- Outstanding Balance: {balance_outstanding:,.0f}\n\n"
    "We strongly encourage you to engage with the school as soon as possible so that together we can support your child. Please contact the school office to discuss a support plan.\n\n"
    "Sincerely,\n"
    "School Administration"
)

def _send_email_with_pdf(to_email: str, student_name: str, student_id: str, 
                        pdf_bytes: bytes, lang_name: str, smtp_config: dict) -> bool:
    """Send email with PDF attachment to parent."""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = smtp_config['from_email']
        msg['To'] = to_email
        msg['Subject'] = f"Important: Your Child's Academic Progress - {student_name}"
        
        # Email body
        body = f"""
Dear Parent/Guardian of {student_name} (Student ID: {student_id}),

Please find attached an important letter regarding your child's academic progress.

This letter contains detailed information about your child's current academic status and recommendations for support.

If you have any questions, please contact the school office.

Best regards,
School Administration
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach PDF
        if pdf_bytes:
            attachment = MIMEBase('application', 'octet-stream')
            attachment.set_payload(pdf_bytes)
            encoders.encode_base64(attachment)
            attachment.add_header(
                'Content-Disposition',
                f'attachment; filename=parent_letter_{student_id}_{lang_name}.pdf'
            )
            msg.attach(attachment)
        
        # Send email
        server = smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port'])
        server.starttls()
        server.login(smtp_config['from_email'], smtp_config['password'])
        text = msg.as_string()
        server.sendmail(smtp_config['from_email'], to_email, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def _detect_student_language(student_data: dict) -> str:
    """Detect student language from student data. Returns language code or 'en' as default."""
    # Check if language is explicitly provided
    if "student_language" in student_data and student_data["student_language"]:
        lang = str(student_data["student_language"]).strip().lower()
        
        # Map common language names to codes
        lang_mapping = {
            "tamil": "ta", "தமிழ்": "ta",
            "hindi": "hi", "हिन्दी": "hi", "हिंदी": "hi",
            "bengali": "bn", "বাংলা": "bn",
            "telugu": "te", "తెలుగు": "te",
            "marathi": "mr", "मराठी": "mr",
            "gujarati": "gu", "ગુજરાતી": "gu",
            "kannada": "kn", "ಕನ್ನಡ": "kn",
            "malayalam": "ml", "മലയാളം": "ml",
            "punjabi": "pa", "ਪੰਜਾਬੀ": "pa",
            "urdu": "ur", "اردو": "ur",
            "nepali": "ne", "नेपाली": "ne",
            "sinhala": "si", "සිංහල": "si",
            "english": "en", "en": "en"
        }
        
        if lang in lang_mapping:
            return lang_mapping[lang]
    
    # If no language detected, return English as default
    return "en"

def _translate_text(text: str, target_lang: str) -> Optional[str]:
    """Translate text to target language using Google Translator."""
    if not text.strip():
        return None
    if target_lang == "en":
        return text
    try:
        if _GoogleTranslator is None:
            return None
        translator = _GoogleTranslator(source="auto", target=target_lang)
        return translator.translate(text)
    except Exception:
        return None

def _ensure_noto_font_available(lang_code: str) -> Optional[str]:
    """Ensure a Noto font for the given language is present under assets/fonts, download if needed.
    Returns absolute path to the font if available, else None.
    """
    try:
        fname = _LANG_TO_NOTO_TTF.get(lang_code)
        if not fname:
            return None
        assets_dir = PROJECT_ROOT / "assets" / "fonts"
        assets_dir.mkdir(parents=True, exist_ok=True)
        target_path = assets_dir / fname
        if target_path.exists():
            return str(target_path)
        # Download from Google fonts repo
        base = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf"
        subdir = fname.replace("NotoSans", "NotoSans").split("-")[0].replace("Regular.ttf", "")
        # Build URL more deterministically per family
        family_dir = {
            "NotoSansDevanagari-Regular.ttf": "NotoSansDevanagari",
            "NotoSansBengali-Regular.ttf": "NotoSansBengali",
            "NotoSansTelugu-Regular.ttf": "NotoSansTelugu",
            "NotoSansGujarati-Regular.ttf": "NotoSansGujarati",
            "NotoSansKannada-Regular.ttf": "NotoSansKannada",
            "NotoSansMalayalam-Regular.ttf": "NotoSansMalayalam",
            "NotoSansGurmukhi-Regular.ttf": "NotoSansGurmukhi",
            "NotoSansArabic-Regular.ttf": "NotoSansArabic",
            "NotoSansSinhala-Regular.ttf": "NotoSansSinhala",
            "NotoSansTamil-Regular.ttf": "NotoSansTamil",
        }.get(fname)
        if family_dir is None:
            return None
        url = f"{base}/{family_dir}/{fname}"
        try:
            import requests  # type: ignore
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200 and resp.content:
                target_path.write_bytes(resp.content)
                return str(target_path)
        except Exception:
            pass
        return None
    except Exception:
        return None

from src.ingestion import fuse_from_frames
from src.rules import score_rules, RuleThresholds
from src.model import predict as model_predict

def _letter_to_pdf_bytes(text: str, title: str = "Parent Letter", preferred_script: str = "auto") -> bytes | None:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfbase.pdfmetrics import stringWidth, registerFont
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None

    buffer = BytesIO()
    width, height = A4
    margin = 20 * mm
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(title)
    
    # Set white background
    c.setFillColorRGB(1, 1, 1)  # White background
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Set obsidian black text color
    c.setFillColorRGB(0.1, 0.1, 0.1)  # Obsidian black
    
    # Try to register a Unicode TrueType font. We allow a preferred script to steer selection
    font_name = "Times-Roman"
    try:
        candidate_paths = []
        assets_dir = PROJECT_ROOT / "assets" / "fonts"

        # Buckets for better control
        latin_first = [
            str(Path("C:/Windows/Fonts/ARIALUNI.TTF")),
            str(Path("C:/Windows/Fonts/ArialUni.ttf")),
            str(Path("C:/Windows/Fonts/Nirmala.ttf")),
            str(Path("C:/Windows/Fonts/NirmalaUI.ttf")),
            str(assets_dir / "NotoSans-Regular.ttf"),
            str(assets_dir / "NotoSansTamil-Regular.ttf"),
            str(Path("C:/Windows/Fonts/Latha.ttf")),
        ]
        tamil_first = [
            str(Path("C:/Windows/Fonts/Latha.ttf")),        # Tamil-specific font first
            str(Path("C:/Windows/Fonts/Nirmala.ttf")),      # Supports Tamil
            str(Path("C:/Windows/Fonts/NirmalaUI.ttf")),    # Supports Tamil
            str(assets_dir / "NotoSansTamil-Regular.ttf"),  # Noto Tamil
            str(Path("C:/Windows/Fonts/ARIALUNI.TTF")),     # Arial Unicode
            str(Path("C:/Windows/Fonts/ArialUni.ttf")),     # Arial Unicode
            str(assets_dir / "NotoSans-Regular.ttf"),       # Noto Sans
        ]
        neutral = [
            str(Path("C:/Windows/Fonts/Nirmala.ttf")),
            str(Path("C:/Windows/Fonts/NirmalaUI.ttf")),
            str(Path("C:/Windows/Fonts/ARIALUNI.TTF")),
            str(Path("C:/Windows/Fonts/ArialUni.ttf")),
            str(assets_dir / "NotoSans-Regular.ttf"),
            str(assets_dir / "NotoSansTamil-Regular.ttf"),
            str(Path("C:/Windows/Fonts/Latha.ttf")),
        ]

        # Strong preference: choose a stable font per script to avoid cross-language issues
        forced_choice: Optional[str] = None
        try:
            if preferred_script == "latin":
                p = assets_dir / "NotoSans-Regular.ttf"
                if p.exists():
                    forced_choice = str(p)
            elif preferred_script == "tamil":
                # Prefer Tamil-specific fonts first for better rendering
                for sys_p in [
                    Path("C:/Windows/Fonts/Latha.ttf"),        # Tamil-specific font
                    Path("C:/Windows/Fonts/Nirmala.ttf"),      # Supports Tamil
                    Path("C:/Windows/Fonts/NirmalaUI.ttf"),    # Supports Tamil
                    Path("C:/Windows/Fonts/ARIALUNI.TTF"),     # Arial Unicode
                    Path("C:/Windows/Fonts/ArialUni.ttf"),     # Arial Unicode
                ]:
                    if sys_p.exists():
                        forced_choice = str(sys_p)
                        break
                if forced_choice is None:
                    p = assets_dir / "NotoSansTamil-Regular.ttf"
                    if p.exists():
                        forced_choice = str(p)
        except Exception:
            pass

        if forced_choice is not None:
            candidate_paths = [forced_choice]
        else:
            if preferred_script == "latin":
                # Force our bundled pan-Unicode Latin font first if present
                candidate_paths = [str(assets_dir / "NotoSans-Regular.ttf")] + latin_first
            elif preferred_script == "tamil":
                candidate_paths = tamil_first
            else:
                candidate_paths = neutral

        chosen: Optional[str] = None
        for p in candidate_paths:
            try:
                if Path(p).exists():
                    chosen = p
                    break
            except Exception:
                pass
        if chosen is not None:
            registerFont(TTFont("AppUnicode", chosen))
            font_name = "AppUnicode"
    except Exception:
        # Keep default font if registration fails
        pass

    text_obj = c.beginText()
    text_obj.setTextOrigin(margin, height - margin)
    text_obj.setFont(font_name, 11)
    text_obj.setFillColorRGB(0.1, 0.1, 0.1)  # Obsidian black text

    max_width = width - 2 * margin

    def _wrap_line(line: str) -> list[str]:
        words = line.split(" ") if line else [""]
        wrapped: list[str] = []
        current = ""
        for w in words:
            test = (current + (" " if current else "") + w).strip()
            if stringWidth(test, font_name, 11) <= max_width:
                current = test
            else:
                if current:
                    wrapped.append(current)
                current = w
        wrapped.append(current)
        if not wrapped:
            wrapped = [""]
        return wrapped

    for raw_line in text.splitlines():
        lines = _wrap_line(raw_line)
        for l in lines:
            text_obj.textLine(l)
            # Start new page if we run off the bottom
            if text_obj.getY() < margin:
                c.drawText(text_obj)
                c.showPage()
                text_obj = c.beginText()
                text_obj.setTextOrigin(margin, height - margin)
                text_obj.setFont(font_name, 11)
                text_obj.setFillColorRGB(0.1, 0.1, 0.1)  # Obsidian black text

    c.drawText(text_obj)
    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

st.set_page_config(page_title="Academic Progress Review", layout="wide")

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

st.title("Academic Progress Review")

with st.sidebar:
    st.header("Data Inputs")
    st.caption("Upload files below (CSV/XLSX).")
    att_file = st.file_uploader("Attendance file", type=["csv", "xlsx"], key="att")
    ass_file = st.file_uploader("Assessments file", type=["csv", "xlsx"], key="ass")
    fee_file = st.file_uploader("Fees file (can include parent_email column)", type=["csv", "xlsx"], key="fee")
    
    # Show data source status
    st.divider()
    st.subheader("Data Source")
    if att_file is not None or ass_file is not None or fee_file is not None:
        st.success("📁 Uploaded files")
        if att_file is not None:
            st.caption(f"✓ {att_file.name}")
        if ass_file is not None:
            st.caption(f"✓ {ass_file.name}")
        if fee_file is not None:
            st.caption(f"✓ {fee_file.name}")
    else:
        st.info("No uploads yet")

    st.divider()
    st.header("Risk Thresholds")
    min_att = st.slider("Min attendance rate", 0.0, 1.0, 0.80, 0.01)
    min_score = st.slider("Min average score", 0.0, 100.0, 50.0, 1.0)
    max_balance = st.number_input("Max outstanding balance", value=0.0, step=100.0)
    
    st.divider()
    st.header("Email Configuration")
    enable_email = st.checkbox("Enable email sending", value=False)
    
    if enable_email:
        st.info("The system will use parent email addresses from both the fees.csv and student_info.csv files for bulk mailing.")
        st.caption("Configure SMTP settings for sending parent letters")
        smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com", help="e.g., smtp.gmail.com for Gmail")
        smtp_port = st.number_input("SMTP Port", value=587, help="587 for TLS, 465 for SSL")
        from_email = st.text_input("From Email", value="", help="Your email address")
        email_password = st.text_input("Email Password", type="password", help="App password for Gmail")
        
        smtp_config = {
            'smtp_server': smtp_server,
            'smtp_port': int(smtp_port),
            'from_email': from_email,
            'password': email_password
        }
    else:
        smtp_config = None

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
def load_data():
    """Load data from hardcoded CSV files for testing"""
    try:
        # Hardcoded file paths for testing
        att_file = "data/inputs/attendance.csv"
        ass_file = "data/inputs/assessments.csv"
        fee_file = "data/inputs/fees.csv"
        student_file = "data/inputs/student_info.csv"
        
        # Read CSV files
        att_df = pd.read_csv(att_file)
        ass_df = pd.read_csv(ass_file)
        fee_df = pd.read_csv(fee_file)
        
        # Check if files are empty
        if att_df.empty or ass_df.empty or fee_df.empty:
            st.error("One or more CSV files are empty")
            return None
            
        # Merge the data
        merged = fuse_from_frames(att_df, ass_df, fee_df)
        
        # Add student info if available
        try:
            student_df = pd.read_csv(student_file)
            if not student_df.empty:
                merged = merged.merge(student_df, on="student_id", how="left")
        except Exception:
            pass  # Student info file is optional
        
        # Apply risk scoring rules
        rules_df = score_rules(
            merged, RuleThresholds(min_attendance_rate=0.80, min_avg_score=50.0, max_balance_outstanding=0.0)
        )
        
        # Try to add model predictions
        try:
            model_df = model_predict("data/inputs")
            if model_df is not None:
                return rules_df.merge(model_df, on="student_id", how="left")
        except Exception:
            pass
            
        return rules_df
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

@st.cache_data(show_spinner=False)
def _compute_from_uploads(att_file, ass_file, fee_file, min_att, min_score, max_balance):
    att_df = _read_uploaded(att_file)
    ass_df = _read_uploaded(ass_file)
    fee_df = _read_uploaded(fee_file)
    
    # Check if at least one file was uploaded and is not empty
    if att_df.empty and ass_df.empty and fee_df.empty:
        return None, None
    
    # Require all three uploads
    if att_df.empty or ass_df.empty or fee_df.empty:
        return None, None
    
    # At this point all dataframes are present
        
    merged = fuse_from_frames(att_df, ass_df, fee_df)
    
    # Add parent_email from fee_df if it exists and not already in merged
    if 'parent_email' in fee_df.columns and 'parent_email' not in merged.columns:
        email_df = fee_df[['student_id', 'parent_email']].copy()
        merged = merged.merge(email_df, on='student_id', how='left')
    
    # Try to load student info from file if available
    try:
        student_file = "data/inputs/student_info.csv"
        student_df = pd.read_csv(student_file)
        if not student_df.empty:
            # If student_df has parent_email and merged doesn't, or we want to prioritize student_info emails
            if 'parent_email' in student_df.columns:
                if 'parent_email' not in merged.columns:
                    merged = merged.merge(student_df[['student_id', 'parent_email']], on='student_id', how='left')
                else:
                    # Merge other columns except parent_email to avoid overwriting existing emails
                    cols_to_merge = [col for col in student_df.columns if col != 'parent_email' or col == 'student_id']
                    merged = merged.merge(student_df[cols_to_merge], on='student_id', how='left')
            else:
                merged = merged.merge(student_df, on="student_id", how="left")
    except Exception:
        pass  # Student info file is optional
    
    rules_df = score_rules(
        merged, RuleThresholds(min_attendance_rate=min_att, min_avg_score=min_score, max_balance_outstanding=max_balance)
    )
    return merged, rules_df

# Removed folder-based loading

# Load data - require all three uploads. No demo data fallback.
df = None

have_all_uploads = att_file is not None and ass_file is not None and fee_file is not None
if have_all_uploads:
    merged, rules_df = _compute_from_uploads(att_file, ass_file, fee_file, min_att, min_score, max_balance)
    if rules_df is not None and not rules_df.empty:
        df = rules_df
        st.success("Using uploaded files")

if df is None:
    # Create an empty dataset with required columns so UI shows zeros by default
    df = pd.DataFrame(
        columns=[
            "student_id",
            "attendance_rate",
            "avg_score",
            "balance_outstanding",
            "rule_risk_points",
            "rule_risk_level",
        ]
    )
    st.info("Please upload Attendance, Assessments, and Fees files to view actual data.")

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

# Derived display columns
if "attendance_rate" in fdf.columns:
    fdf["attendance_pct"] = pd.to_numeric(fdf["attendance_rate"], errors="coerce").fillna(0.0) * 100.0
else:
    fdf["attendance_pct"] = 0.0

# KPIs
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"<div class='metric-card'><h4>Students</h4><h2>{int(fdf.shape[0])}</h2></div>", unsafe_allow_html=True)
with k2:
    avg_att = 0.0 if fdf.empty else float(pd.to_numeric(fdf["attendance_pct"], errors="coerce").fillna(0.0).mean())
    st.markdown(f"<div class='metric-card'><h4>Avg Attendance</h4><h2>{avg_att:.1f}%</h2></div>", unsafe_allow_html=True)
with k3:
    avg_score_val = 0.0 if fdf.empty else float(pd.to_numeric(fdf["avg_score"], errors="coerce").fillna(0.0).mean())
    st.markdown(f"<div class='metric-card'><h4>Avg Score</h4><h2>{avg_score_val:.1f}</h2></div>", unsafe_allow_html=True)
with k4:
    outstanding_total = 0.0 if fdf.empty else float(pd.to_numeric(fdf["balance_outstanding"], errors="coerce").fillna(0.0).sum())
    st.markdown(f"<div class='metric-card'><h4>Outstanding Total</h4><h2>{outstanding_total:,.0f}</h2></div>", unsafe_allow_html=True)

# Tabs
tab_overview, tab_students, tab_trends, tab_settings, tab_letters = st.tabs(["Overview", "Students", "Trends", "Settings", "Parent Letters"])

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
        x=alt.X("attendance_pct", title="Attendance (%)"),
        y=alt.Y("avg_score", title="Average Score"),
        color=alt.Color("rule_risk_level:N", scale=alt.Scale(domain=["High","Medium","Low"], range=["#ff6b6b","#f7c948","#51cf66"])),
        tooltip=["student_id","attendance_pct","avg_score","balance_outstanding","rule_risk_level"]
    )
    st.altair_chart(scatter, use_container_width=True)

with tab_students:
    # Risk badge column
    def badge(level: str) -> str:
        label = str(level).strip().title()
        if label in {"High", "Medium", "Low"}:
            return f"<span class='risk-badge risk-{label}'>{label}</span>"
        return label

    table_cols = [
        "student_id",
        "attendance_pct",
        "avg_score",
        "balance_outstanding",
        "rule_risk_points",
        "rule_risk_level",
    ]
    if "student_name" in fdf.columns:
        table_cols.insert(1, "student_name")
    if "model_risk_score" in fdf.columns:
        table_cols.append("model_risk_score")
    # Ensure missing columns exist when df is empty default
    for c in table_cols:
        if c not in fdf.columns:
            fdf[c] = 0 if c not in {"student_id", "student_name"} else ""
    tdf = fdf[table_cols].copy()
    tdf.rename(columns={"rule_risk_level": "Risk"}, inplace=True)

    # Sorting controls
    sort_col1, _ = st.columns([1, 3])
    with sort_col1:
        sort_by_risk = st.checkbox("Sort by Risk (High → Low)", value=True)
    if sort_by_risk:
        _risk_rank = {"High": 2, "Medium": 1, "Low": 0}
        tdf["_risk_order"] = tdf["Risk"].astype(str).str.title().map(lambda x: _risk_rank.get(x, -1))
        # Secondary sorts to keep table stable and meaningful
        tdf = (
            tdf.sort_values(
                by=["_risk_order", "rule_risk_points", "attendance_pct", "avg_score"],
                ascending=[False, False, False, False],
            )
            .drop(columns=["_risk_order"])
        )

    # Style risk column with background colors instead of HTML badges (works in st.dataframe)
    def _style_risk(col):
        mapping = {
            "High": "background-color: #ffcccc; color: #9b0000; font-weight: 600;",
            "Medium": "background-color: #fff4cc; color: #9b6b00; font-weight: 600;",
            "Low": "background-color: #e8ffe8; color: #006b00; font-weight: 600;",
        }
        return [mapping.get(str(v), "") for v in col]

    st.dataframe(
        tdf.style.format(precision=2).hide(axis="index").apply(_style_risk, subset=["Risk"]),
        use_container_width=True,
    )

    st.divider()
    st.subheader("Student Detail")
    if fdf.empty:
        st.info("No students to display. Upload files to see student details.")
    else:
        colA, colB = st.columns([1,2])
        with colA:
            # Use name for selection when available
            if "student_name" in fdf.columns and fdf["student_name"].astype(str).str.len().gt(0).any():
                # Get unique student IDs first to avoid duplicates
                unique_students = fdf.drop_duplicates(subset=['student_id'])
                options = (
                    unique_students.apply(lambda r: f"{str(r['student_name']).strip()} (ID: {str(r['student_id'])})", axis=1).tolist()
                )
                choice = st.selectbox("Select student", options, key="select_student_with_name")
                # Extract the ID from the choice
                student_id = choice.split("(ID:")[-1].rstrip(")").strip()
            else:
                student_id = st.selectbox("Select student", fdf["student_id"].astype(str).unique().tolist(), key="select_student_by_id")
        with colB:
            srow = fdf[fdf["student_id"].astype(str) == str(student_id)].iloc[0]
            
            # Detect student language
            detected_lang = _detect_student_language(srow.to_dict())
            lang_display = {
                "ta": "Tamil (தமிழ்)",
                "hi": "Hindi (हिन्दी)", 
                "bn": "Bengali (বাংলা)",
                "te": "Telugu (తెలుగు)",
                "mr": "Marathi (मराठी)",
                "gu": "Gujarati (ગુજરાતી)",
                "kn": "Kannada (ಕನ್ನಡ)",
                "ml": "Malayalam (മലയാളം)",
                "pa": "Punjabi (ਪੰਜਾਬੀ)",
                "ur": "Urdu (اردو)",
                "ne": "Nepali (नेपाली)",
                "si": "Sinhala (සිංහල)",
                "en": "English"
            }.get(detected_lang, "English")
            
            st.markdown(
                f""
                f"<div class='metric-card'><h3>Student {str(srow.get('student_name', '') or student_id)}</h3>"
                f"<p>Risk: {badge(srow['rule_risk_level'])}</p>"
                f"<p>Attendance: {float(srow['attendance_pct']):.1f}%</p>"
                f"<p>Average Score: {float(srow['avg_score']):.1f}</p>"
                f"<p>Outstanding: {float(srow['balance_outstanding']):,.0f}</p>"
                f"<p>Language: {lang_display}</p>"
                f"</div>"
                f"",
                unsafe_allow_html=True,
            )
            
            # Generate PDF in student's language
            if srow['rule_risk_level'] == 'High':
                st.subheader("Generate Parent Letter")
                
                # Automatically use detected language
                lang_code = detected_lang
                lang_name = {
                    "ta": "Tamil (தமிழ்)",
                    "hi": "Hindi (हिन्दी)", 
                    "bn": "Bengali (বাংলা)",
                    "te": "Telugu (తెలుగు)",
                    "mr": "Marathi (मराठी)",
                    "gu": "Gujarati (ગુજરાતી)",
                    "kn": "Kannada (ಕನ್ನಡ)",
                    "ml": "Malayalam (മലയാളം)",
                    "pa": "Punjabi (ਪੰਜਾਬੀ)",
                    "ur": "Urdu (اردو)",
                    "ne": "Nepali (नेपाली)",
                    "si": "Sinhala (සිංහල)",
                    "en": "English"
                }.get(detected_lang, "English")
                
                st.info(f"Letter will be generated in: {lang_name}")
                
                # Bilingual option
                bilingual = st.checkbox("Include English and translation together", value=True, key="bilingual_student_detail")
                
                # Generate letter with detected language
                values = {
                    "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
                    "student_id": str(srow["student_id"]),
                    "student_name": str(srow.get("student_name", "")).strip() if "student_name" in srow else str(srow["student_id"]),
                    "attendance_pct": float(srow["attendance_pct"]),
                    "avg_score": float(srow["avg_score"]),
                    "balance_outstanding": float(srow["balance_outstanding"]),
                }
                
                try:
                    letter = _DEFAULT_TEMPLATE.format(**values)
                except Exception as e:
                    st.error(f"Template error: {e}")
                    letter = ""
                
                # Translation
                translated: Optional[str] = _translate_text(letter, lang_code)
                if lang_code != "en" and _GoogleTranslator is None:
                    st.warning("Install 'deep-translator' to enable translation: pip install deep-translator")
                if lang_code != "en" and translated is None and letter.strip():
                    st.error("Translation failed. Please try again or switch language.")
                
                # Compose bilingual text when requested
                combined_text = letter
                if lang_code != "en" and translated:
                    if bilingual:
                        combined_text = (
                            f"{letter}\n\n---\n\n{translated}"
                        )
                    else:
                        combined_text = translated
                
                # Download buttons
                st.download_button(
                    "Download letter (.txt)",
                    data=combined_text.encode("utf-8"),
                    file_name=(
                        f"parent_letter_{values['student_id']}_{lang_code if lang_code!='en' else 'en'}"
                        f"{'_bilingual' if bilingual and lang_code!='en' else ''}.txt"
                    ),
                    mime="text/plain",
                    disabled=(combined_text.strip() == ""),
                    key="download_txt_student_detail"
                )
                
                # PDF download - use simple approach for now
                pdf_bytes = None  # Initialize pdf_bytes to None
                if lang_code != "en" and translated and translated.strip():
                    # Generate PDF with translated text
                    pdf_bytes = _letter_to_pdf_bytes(combined_text, f"Parent Letter - {lang_name}", 
                                                   "tamil" if lang_code == "ta" else "latin")
                    
                st.download_button(
                    "Download PDF",
                    data=pdf_bytes if pdf_bytes is not None else b"",
                    file_name=f"parent_letter_{values['student_id']}_{lang_code}.pdf",
                    mime="application/pdf",
                    disabled=(pdf_bytes is None),
                    help="PDF with proper font support for the selected language.",
                    key="download_pdf_student_detail"
                )
                
                # Individual email sending
                if smtp_config and enable_email and "parent_email" in srow and pd.notna(srow["parent_email"]) and srow["parent_email"]:
                    st.divider()
                    st.subheader("Send Email")
                    if st.button("Send Email to Parent", type="secondary"):
                        with st.spinner("Sending email..."):
                            success = _send_email_with_pdf(
                                srow["parent_email"],
                                values["student_name"],
                                values["student_id"],
                                pdf_bytes if pdf_bytes else b"",
                                lang_name,
                                smtp_config
                            )
                            
                            if success:
                                st.success("✅ Email sent successfully!")
                            else:
                                st.error("❌ Failed to send email. Check console for details.")
                elif smtp_config and enable_email:
                    st.info("No parent email address available for this student.")

with tab_trends:
    st.caption("Trends across current dataset")
    # Attendance histogram
    hist_att = alt.Chart(fdf).mark_bar(opacity=0.8).encode(
        x=alt.X("attendance_pct", bin=alt.Bin(maxbins=20), title="Attendance (%)"), y="count()"
    )
    st.altair_chart(hist_att, use_container_width=True)

    # Score histogram
    hist_score = alt.Chart(fdf).mark_bar(opacity=0.8).encode(
        x=alt.X("avg_score", bin=alt.Bin(maxbins=20), title="Average Score"), y="count()"
    )
    st.altair_chart(hist_score, use_container_width=True)

with tab_settings:
    st.write("Download current results")
    csv_all = fdf.to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered table (CSV)", data=csv_all, file_name="risk_table.csv", mime="text/csv", key="download_csv_settings")

    if 'model_risk_score' in fdf.columns:
        st.caption("Model scores included where available (folder mode).")

with tab_letters:
    st.subheader("Letters to Parents (High Risk)")
    high_df = fdf[fdf["rule_risk_level"].astype(str).str.title() == "High"].copy()
    if high_df.empty:
        st.info("No students currently classified as High risk.")
    else:
        # Bulk email sending section
        if smtp_config and enable_email:
            st.divider()
            st.subheader("Bulk Email Sending")
            
            # Check if parent email column exists
            if "parent_email" in high_df.columns:
                email_ready_df = high_df[high_df["parent_email"].notna() & (high_df["parent_email"] != "")]
                if not email_ready_df.empty:
                    st.success(f"Found {len(email_ready_df)} high-risk students with email addresses")
                    st.info("Email addresses are collected from both fees.csv and student_info.csv files.")
                    
                    if st.button("Send Emails to All High-Risk Students", type="primary"):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        success_count = 0
                        failed_count = 0
                        
                        for i, (_, student) in enumerate(email_ready_df.iterrows()):
                            try:
                                # Detect student language
                                detected_lang = _detect_student_language(student.to_dict())
                                lang_code = detected_lang
                                lang_name = {
                                    "ta": "Tamil (தமிழ்)",
                                    "hi": "Hindi (हिन्दी)", 
                                    "bn": "Bengali (বাংলা)",
                                    "te": "Telugu (తెలుగు)",
                                    "mr": "Marathi (मराठी)",
                                    "gu": "Gujarati (ગુજરાતી)",
                                    "kn": "Kannada (ಕನ್ನಡ)",
                                    "ml": "Malayalam (മലയാളം)",
                                    "pa": "Punjabi (ਪੰਜਾਬੀ)",
                                    "ur": "Urdu (اردو)",
                                    "ne": "Nepali (नेपाली)",
                                    "si": "Sinhala (සිංහල)",
                                    "en": "English"
                                }.get(detected_lang, "English")
                                
                                # Generate letter
                                values = {
                                    "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
                                    "student_id": str(student["student_id"]),
                                    "student_name": str(student.get("student_name", "")).strip() if "student_name" in student else str(student["student_id"]),
                                    "attendance_pct": float(student["attendance_pct"]),
                                    "avg_score": float(student["avg_score"]),
                                    "balance_outstanding": float(student["balance_outstanding"]),
                                }
                                
                                letter = _DEFAULT_TEMPLATE.format(**values)
                                
                                # Translate if needed
                                translated = _translate_text(letter, lang_code)
                                combined_text = letter
                                if lang_code != "en" and translated:
                                    combined_text = f"{letter}\n\n---\n\n{translated}"
                                
                                # Generate PDF
                                pdf_bytes = _letter_to_pdf_bytes(combined_text, f"Parent Letter - {lang_name}", 
                                                               "tamil" if lang_code == "ta" else "latin")
                                
                                # Send email
                                if pdf_bytes:
                                    success = _send_email_with_pdf(
                                        student["parent_email"],
                                        values["student_name"],
                                        values["student_id"],
                                        pdf_bytes,
                                        lang_name,
                                        smtp_config
                                    )
                                    
                                    if success:
                                        success_count += 1
                                    else:
                                        failed_count += 1
                                else:
                                    failed_count += 1
                                
                                # Update progress
                                progress = (i + 1) / len(email_ready_df)
                                progress_bar.progress(progress)
                                status_text.text(f"Processed {i + 1}/{len(email_ready_df)} students...")
                                
                            except Exception as e:
                                failed_count += 1
                                print(f"Error processing student {student['student_id']}: {e}")
                        
                        # Show results
                        progress_bar.progress(1.0)
                        if success_count > 0:
                            st.success(f"✅ Successfully sent {success_count} emails!")
                        if failed_count > 0:
                            st.error(f"❌ Failed to send {failed_count} emails. Check console for details.")
                        
                        status_text.text(f"Completed: {success_count} successful, {failed_count} failed")
                else:
                    st.warning("No high-risk students have email addresses in the data.")
            else:
                st.warning("No 'parent_email' column found in the data. Please add parent email addresses to your input files.")
        
        st.divider()
        left, right = st.columns([1, 2])
        with left:
            student_choice = st.selectbox("Select student", high_df["student_id"].astype(str).unique().tolist(), key="select_student_letters_tab")

            default_template = (
                "Date: {date}\n\n"
                "Dear Parent/Guardian of {student_name} (Student ID: {student_id}),\n\n"
                "We are writing to inform you that your child has been identified as at High risk of school drop-out based on our monitoring indicators.\n\n"
                "Key indicators:\n"
                "- Attendance: {attendance_pct:.1f}%\n"
                "- Average Score: {avg_score:.1f}\n"
                "- Outstanding Balance: {balance_outstanding:,.0f}\n\n"
                "We strongly encourage you to engage with the school as soon as possible so that together we can support your child. Please contact the school office to discuss a support plan.\n\n"
                "Sincerely,\n"
                "School Administration"
            )
        with right:
            st.caption("Customize the letter template. Use placeholders: {date}, {student_id}, {student_name}, {attendance_pct}, {avg_score}, {balance_outstanding}.")
            template_text = st.text_area("Letter template", value=default_template, height=260)

        s = high_df[high_df["student_id"].astype(str) == str(student_choice)].iloc[0]
        values = {
            "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
            "student_id": str(s["student_id"]),
            "student_name": str(s.get("student_name", "")).strip() if "student_name" in s else str(s["student_id"]),
            "attendance_pct": float(s["attendance_pct"]),
            "avg_score": float(s["avg_score"]),
            "balance_outstanding": float(s["balance_outstanding"]),
        }
        try:
            letter = template_text.format(**values)
        except Exception as e:
            st.error(f"Template error: {e}")
            letter = ""

        # Automatically detect language for this student
        detected_lang = _detect_student_language(s.to_dict())
        lang_code = detected_lang
        lang_name = {
            "ta": "Tamil (தமிழ்)",
            "hi": "Hindi (हिन्दी)", 
            "bn": "Bengali (বাংলা)",
            "te": "Telugu (తెలుగు)",
            "mr": "Marathi (मराठी)",
            "gu": "Gujarati (ગુજરાતી)",
            "kn": "Kannada (ಕನ್ನಡ)",
            "ml": "Malayalam (മലയാളം)",
            "pa": "Punjabi (ਪੰਜਾਬੀ)",
            "ur": "Urdu (اردو)",
            "ne": "Nepali (नेपाली)",
            "si": "Sinhala (සිංහල)",
            "en": "English"
        }.get(detected_lang, "English")
        
        st.info(f"Letter will be generated in: {lang_name}")
        bilingual = st.checkbox("Include English and translation together", value=True, key="bilingual_letters_tab")

        def _translate_text(text: str, target_lang: str) -> Optional[str]:
            if not text.strip():
                return None
            if target_lang == "en":
                return text
            try:
                if _GoogleTranslator is None:
                    return None
                translator = _GoogleTranslator(source="auto", target=target_lang)
                return translator.translate(text)
            except Exception:
                return None

        translated: Optional[str] = _translate_text(letter, lang_code)
        if lang_code != "en" and _GoogleTranslator is None:
            st.warning("Install 'deep-translator' to enable translation: pip install deep-translator")
        if lang_code != "en" and translated is None and letter.strip():
            st.error("Translation failed. Please try again or switch language.")

        # Compose bilingual text when requested
        combined_text = letter
        if lang_code != "en" and translated:
            if bilingual:
                combined_text = (
                    f"{letter}\n\n---\n\n{translated}"
                )
            else:
                combined_text = translated

        st.divider()
        st.subheader("Preview")
        if bilingual and lang_code != "en" and translated:
            st.caption("English + translation")
            st.code(combined_text)
        elif lang_code != "en" and translated:
            st.caption(f"Translated to {lang_name}")
            st.code(combined_text)
        else:
            st.caption("English")
            st.code(letter)
        st.download_button(
            "Download letter (.txt)",
            data=combined_text.encode("utf-8"),
            file_name=(
                f"parent_letter_{values['student_id']}_{lang_code if lang_code!='en' else 'en'}"
                f"{'_bilingual' if bilingual and lang_code!='en' else ''}.txt"
            ),
            mime="text/plain",
            disabled=(combined_text.strip() == ""),
            key="download_txt_letters_tab"
        )

        # PDF download (requires reportlab)

        def _letter_to_pdf_bilingual_bytes(english_text: str, target_text: str, lang_code_for_target: str) -> bytes | None:
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.units import mm
                from reportlab.pdfbase.pdfmetrics import stringWidth, registerFont
                from reportlab.pdfbase.ttfonts import TTFont
            except Exception:
                return None

            buffer = BytesIO()
            width, height = A4
            margin = 20 * mm
            c = canvas.Canvas(buffer, pagesize=A4)
            c.setTitle("Parent Letter (Bilingual)")
            
            # Set white background
            c.setFillColorRGB(1, 1, 1)  # White background
            c.rect(0, 0, width, height, fill=1, stroke=0)
            
            # Set obsidian black text color
            c.setFillColorRGB(0.1, 0.1, 0.1)  # Obsidian black

            assets_dir = PROJECT_ROOT / "assets" / "fonts"

            # Choose fonts explicitly: one for Latin, one for target (based on language)
            latin_font = "Times-Roman"
            target_font = "Times-Roman"
            try:
                # Latin
                latin_candidates = [
                    str(assets_dir / "NotoSans-Regular.ttf"),
                    str(Path("C:/Windows/Fonts/ARIALUNI.TTF")),
                    str(Path("C:/Windows/Fonts/ArialUni.ttf")),
                    str(Path("C:/Windows/Fonts/Nirmala.ttf")),
                    str(Path("C:/Windows/Fonts/NirmalaUI.ttf")),
                ]
                chosen_latin = None
                for p in latin_candidates:
                    if Path(p).exists():
                        chosen_latin = p
                        break
                if chosen_latin:
                    registerFont(TTFont("AppLatin", chosen_latin))
                    latin_font = "AppLatin"

                # Target
                target_candidates = []
                # For Tamil, prioritize the bundled Noto Tamil font
                if lang_code_for_target == "ta":  # Tamil
                    target_candidates.extend([
                        str(assets_dir / "NotoSansTamil-Regular.ttf"),  # Noto Tamil (already available)
                        str(assets_dir / "NotoSansTamil-Bold.ttf"),     # Noto Tamil Bold
                        str(Path("C:/Windows/Fonts/Latha.ttf")),        # Tamil-specific
                        str(Path("C:/Windows/Fonts/Nirmala.ttf")),      # Supports Tamil
                        str(Path("C:/Windows/Fonts/NirmalaUI.ttf")),    # Supports Tamil
                        str(Path("C:/Windows/Fonts/ARIALUNI.TTF")),     # Arial Unicode
                        str(Path("C:/Windows/Fonts/ArialUni.ttf")),     # Arial Unicode
                    ])
                else:
                    # For other languages, use general Indic fonts
                    target_candidates.extend([
                        str(Path("C:/Windows/Fonts/Nirmala.ttf")),
                        str(Path("C:/Windows/Fonts/NirmalaUI.ttf")),
                        str(Path("C:/Windows/Fonts/Latha.ttf")),
                        str(Path("C:/Windows/Fonts/ARIALUNI.TTF")),
                        str(Path("C:/Windows/Fonts/ArialUni.ttf")),
                    ])
                chosen_target = None
                print(f"Looking for Tamil fonts in: {target_candidates}")
                for p in target_candidates:
                    if Path(p).exists():
                        chosen_target = p
                        print(f"Found Tamil font: {p}")
                        break
                if chosen_target:
                    try:
                        registerFont(TTFont("AppTarget", chosen_target))
                        target_font = "AppTarget"
                        print(f"Successfully registered target font: {chosen_target}")
                    except Exception as e:
                        # If font registration fails, keep using Times-Roman
                        print(f"Font registration failed: {e}")
                        pass
                else:
                    print("No target font found for Tamil")
            except Exception:
                pass

            text_obj = c.beginText()
            text_obj.setTextOrigin(margin, height - margin)
            text_obj.setFont(latin_font, 11)
            text_obj.setFillColorRGB(0.1, 0.1, 0.1)  # Obsidian black text

            max_width = width - 2 * margin

            def _wrap_line_with_font(line: str, font_name_wrap: str) -> list[str]:
                words = line.split(" ") if line else [""]
                wrapped: list[str] = []
                current = ""
                for w in words:
                    test = (current + (" " if current else "") + w).strip()
                    if stringWidth(test, font_name_wrap, 11) <= max_width:
                        current = test
                    else:
                        if current:
                            wrapped.append(current)
                        current = w
                wrapped.append(current)
                if not wrapped:
                    wrapped = [""]
                return wrapped

            # English section
            for raw_line in english_text.splitlines():
                for l in _wrap_line_with_font(raw_line, latin_font):
                    text_obj.textLine(l)
                    if text_obj.getY() < margin:
                        c.drawText(text_obj)
                        c.showPage()
                        text_obj = c.beginText()
                        text_obj.setTextOrigin(margin, height - margin)
                        text_obj.setFont(latin_font, 11)
                        text_obj.setFillColorRGB(0.1, 0.1, 0.1)  # Obsidian black text

            # Separator
            text_obj.textLine("")
            text_obj.textLine("---")
            text_obj.textLine("")

            # Target-language section
            print(f"Using target font: {target_font}")
            print(f"Target text sample: {target_text[:100]}...")
            text_obj.setFont(target_font, 11)
            for raw_line in target_text.splitlines():
                for l in _wrap_line_with_font(raw_line, target_font):
                    text_obj.textLine(l)
                    if text_obj.getY() < margin:
                        c.drawText(text_obj)
                        c.showPage()
                        text_obj = c.beginText()
                        text_obj.setTextOrigin(margin, height - margin)
                        text_obj.setFont(target_font, 11)
                        text_obj.setFillColorRGB(0.1, 0.1, 0.1)  # Obsidian black text

            c.drawText(text_obj)
            c.showPage()
            c.save()
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes

        def _bilingual_pdf_via_html(english_text: str, target_text: str, lang_code_for_target: str) -> bytes | None:
            """Use WeasyPrint (Pango/Harfbuzz) for complex script shaping (e.g., Malayalam)."""
            try:
                from weasyprint import HTML, CSS  # type: ignore
            except Exception:
                return None

            assets_dir = PROJECT_ROOT / "assets" / "fonts"
            latin_path = (assets_dir / "NotoSans-Regular.ttf")
            target_path = None
            try:
                ensured = _ensure_noto_font_available(lang_code_for_target)
                if ensured:
                    target_path = Path(ensured)
            except Exception:
                target_path = None

            # Fallbacks for target if ensure failed
            if target_path is None:
                # Try system fonts that support Tamil/Indic scripts
                for p in [
                    assets_dir / "NotoSansTamil-Regular.ttf",  # Noto Tamil (already available)
                    Path("C:/Windows/Fonts/Latha.ttf"),        # Tamil-specific font
                    Path("C:/Windows/Fonts/Nirmala.ttf"),      # Supports Tamil
                    Path("C:/Windows/Fonts/NirmalaUI.ttf"),    # Supports Tamil
                    Path("C:/Windows/Fonts/ARIALUNI.TTF"),     # Arial Unicode
                    Path("C:/Windows/Fonts/ArialUni.ttf"),     # Arial Unicode
                    Path("C:/Windows/Fonts/Mangal.ttf"),       # Hindi but may support Tamil
                ]:
                    if p.exists():
                        target_path = p
                        break

            # Build CSS with @font-face
            css_parts = []
            if latin_path.exists():
                css_parts.append(f"""
                @font-face {{
                    font-family: 'AppLatin';
                    src: url('file:///{latin_path.as_posix()}') format('truetype');
                    font-weight: normal; font-style: normal;
                }}
                """)
            if target_path is not None and target_path.exists():
                css_parts.append(f"""
                @font-face {{
                    font-family: 'AppTarget';
                    src: url('file:///{target_path.as_posix()}') format('truetype');
                    font-weight: normal; font-style: normal;
                }}
                """)

            css_parts.append("""
            body { 
                font-size: 12pt; 
                background-color: white; 
                color: rgb(10, 10, 10); 
            }
            .latin { 
                font-family: 'AppLatin', 'DejaVu Sans', sans-serif; 
                color: rgb(10, 10, 10); 
            }
            .target { 
                font-family: 'AppTarget', 'Noto Sans Tamil', 'Latha', 'Nirmala UI', 'Nirmala', 'Arial Unicode MS', sans-serif; 
                color: rgb(10, 10, 10); 
            }
            .block { 
                white-space: pre-wrap; 
                line-height: 1.4; 
                color: rgb(10, 10, 10); 
            }
            .sep { 
                margin: 12px 0; 
                border-top: 1px solid #888; 
            }
            """)

            html = f"""
            <html><head><meta charset='utf-8'></head>
            <body>
              <div class='latin block'>{english_text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')}</div>
              <div class='sep'></div>
              <div class='target block'>{target_text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')}</div>
            </body></html>
            """

            css = CSS(string="\n".join(css_parts))
            pdf_bytes = HTML(string=html).write_pdf(stylesheets=[css])
            return pdf_bytes

        # Single bilingual PDF (English + translation)
        bilingual_pdf = None
        if lang_code != "en" and translated and translated.strip():
            # Skip WeasyPrint on Windows due to dependency issues, use ReportLab directly
            bilingual_pdf = _letter_to_pdf_bilingual_bytes(letter, translated, lang_code)
        st.download_button(
            "Download bilingual PDF",
            data=bilingual_pdf if bilingual_pdf is not None else b"",
            file_name=f"parent_letter_{values['student_id']}_en_{lang_code if lang_code!='en' else 'en'}_bilingual.pdf",
            mime="application/pdf",
            disabled=(bilingual_pdf is None),
            help=(None if bilingual_pdf is not None else "Install 'weasyprint' for best script support, or ensure Unicode fonts are available."),
            key="download_bilingual_pdf_letters_tab"
        )

# Manual refresh button
if st.button("Refresh"):
    st.rerun()
