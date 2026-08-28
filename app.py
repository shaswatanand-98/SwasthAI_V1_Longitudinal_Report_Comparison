
import os
import io
import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF

st.set_page_config(
    page_title="SwasthAI | Your Health Journey",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------
# Styling
# -----------------------------
st.markdown("""
<style>
    .stApp {
        background:
            radial-gradient(circle at 10% 5%, rgba(57, 189, 178, .13), transparent 25%),
            radial-gradient(circle at 90% 10%, rgba(73, 120, 255, .10), transparent 24%),
            #F7FAFC;
        color: #17212B;
    }
    .block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
    .hero {
        background: linear-gradient(135deg, #0F766E 0%, #0B5C67 55%, #164E63 100%);
        padding: 2.2rem 2.4rem;
        border-radius: 24px;
        color: white;
        box-shadow: 0 18px 45px rgba(15, 118, 110, .18);
        margin-bottom: 1.4rem;
    }
    .hero h1 {font-size: 2.5rem; margin: 0 0 .4rem 0;}
    .hero p {font-size: 1.05rem; opacity: .9; margin: 0; max-width: 760px;}
    .pill {
        display: inline-block; padding: .35rem .75rem; margin: .2rem .3rem 0 0;
        border-radius: 999px; background: rgba(255,255,255,.16);
        border: 1px solid rgba(255,255,255,.20); font-size: .82rem;
    }
    .section-title {font-size: 1.35rem; font-weight: 750; margin: 1.2rem 0 .6rem;}
    .card {
        background: white; border: 1px solid #E6EDF2; border-radius: 18px;
        padding: 1.1rem 1.2rem; box-shadow: 0 7px 22px rgba(20,45,65,.05);
        height: 100%;
    }
    .metric-card {
        background: white; border: 1px solid #E6EDF2; border-radius: 16px;
        padding: .9rem 1rem; box-shadow: 0 6px 18px rgba(20,45,65,.04);
    }
    .small-label {font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; color: #64748B; font-weight: 700;}
    .big-number {font-size: 1.65rem; font-weight: 800; margin-top: .15rem;}
    .muted {color: #64748B;}
    .safe-box {
        background: #FFF8E8; border: 1px solid #F5D68A; border-radius: 14px;
        padding: .9rem 1rem; color: #6B4E00;
    }
    .footer-note {font-size: .82rem; color: #64748B; margin-top: 1rem;}
    /* ---------- Streamlit widget contrast fixes ---------- */
    div[data-testid="stFileUploader"] {
        background: #FFFFFF !important;
        border: 1px dashed #9FB8C5 !important;
        border-radius: 16px;
        padding: .65rem !important;
        color: #17212B !important;
    }
    div[data-testid="stFileUploader"] section,
    div[data-testid="stFileUploaderDropzone"] {
        background: #F8FAFC !important;
        border: 1px dashed #9FB8C5 !important;
        color: #17212B !important;
    }
    div[data-testid="stFileUploaderDropzone"] * {
        color: #334155 !important;
    }
    div[data-testid="stFileUploaderDropzone"] button,
    div[data-testid="stFileUploader"] button {
        background: #FFFFFF !important;
        color: #0F5F59 !important;
        border: 1px solid #7BA9A5 !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        opacity: 1 !important;
    }
    div[data-testid="stFileUploaderDropzone"] button:hover,
    div[data-testid="stFileUploader"] button:hover {
        background: #EAF6F4 !important;
        color: #0B5C67 !important;
    }
    /* Keep uploader action icons, including the add (+) icon, clearly visible. */
    div[data-testid="stFileUploader"] svg,
    div[data-testid="stFileUploaderDropzone"] svg {
        color: #0F5F59 !important;
        fill: none !important;
        stroke: currentColor !important;
        opacity: 1 !important;
    }
    div[data-testid="stFileUploader"] button svg,
    div[data-testid="stFileUploaderDropzone"] button svg {
        color: #0F5F59 !important;
        stroke: #0F5F59 !important;
        opacity: 1 !important;
    }
    .stButton > button,
    .stDownloadButton > button {
        border-radius: 12px !important;
        padding: .65rem 1rem !important;
        font-weight: 700 !important;
        opacity: 1 !important;
    }
    .stButton > button {
        border: 1px solid #0F766E !important;
        background: linear-gradient(135deg, #0F766E, #0B5C67) !important;
        color: #FFFFFF !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #0B5C67, #164E63) !important;
        color: #FFFFFF !important;
    }
    .stDownloadButton > button {
        background: #FFFFFF !important;
        color: #0F5F59 !important;
        border: 1px solid #7BA9A5 !important;
    }
    .stDownloadButton > button:hover {
        background: #EAF6F4 !important;
        color: #0B5C67 !important;
    }
    /* Date inputs, expanders and other interactive controls */
    div[data-baseweb="input"] {
        background: #FFFFFF !important;
        border-color: #CBD5E1 !important;
    }
    div[data-baseweb="input"] input {
        color: #17212B !important;
        -webkit-text-fill-color: #17212B !important;
        background: #FFFFFF !important;
        opacity: 1 !important;
    }
    details, details > summary,
    div[data-testid="stExpander"] {
        background: #FFFFFF !important;
        color: #17212B !important;
        border-color: #D9E3EA !important;
    }
    details summary * {
        color: #17212B !important;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------
# Helpers
# -----------------------------
CANONICAL = {
    "hba1c": ["hba1c", "hb a1c", "glycated hemoglobin", "glycosylated hemoglobin"],
    "fasting_glucose": ["fasting glucose", "fasting blood sugar", "fbs", "glucose fasting"],
    "postprandial_glucose": ["postprandial", "ppbs", "post prandial glucose"],
    "total_cholesterol": ["total cholesterol", "cholesterol total"],
    "ldl": ["ldl", "ldl cholesterol"],
    "hdl": ["hdl", "hdl cholesterol"],
    "triglycerides": ["triglycerides", "triglyceride"],
    "hemoglobin": ["hemoglobin", "haemoglobin", "hb"],
    "tsh": ["tsh", "thyroid stimulating hormone"],
    "creatinine": ["creatinine", "serum creatinine"],
    "vitamin_d": ["vitamin d", "25-oh vitamin d", "25 hydroxy vitamin d"],
    "vitamin_b12": ["vitamin b12", "b12"],
}

DISPLAY_NAMES = {
    "hba1c": "HbA1c", "fasting_glucose": "Fasting Glucose",
    "postprandial_glucose": "Postprandial Glucose", "total_cholesterol": "Total Cholesterol",
    "ldl": "LDL", "hdl": "HDL", "triglycerides": "Triglycerides",
    "hemoglobin": "Hemoglobin", "tsh": "TSH", "creatinine": "Creatinine",
    "vitamin_d": "Vitamin D", "vitamin_b12": "Vitamin B12",
}

def get_client():
    key = st.secrets.get("GEMINI_API_KEY", None) if hasattr(st, "secrets") else None
    key = key or os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    return genai.Client(api_key=key)

def canonical_name(name: str) -> str:
    n = name.lower().strip()
    for canon, aliases in CANONICAL.items():
        if any(a in n for a in aliases):
            return canon
    return re.sub(r"[^a-z0-9]+", "_", n).strip("_") or n

def extract_pdf_text(file_bytes):
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        return text.strip()
    except Exception:
        return ""

def fallback_parse(text):
    """Best-effort parser for common lab-report lines when no API key is available."""
    rows = []
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    for line in lines:
        low = line.lower()
        matched = None
        for canon, aliases in CANONICAL.items():
            if any(alias in low for alias in aliases):
                matched = canon
                break
        if not matched:
            continue
        nums = re.findall(r"(?<![A-Za-z])(\d+(?:\.\d+)?)", line)
        if not nums:
            continue
        value = float(nums[0])
        unit_match = re.search(r"\b(mg/dl|g/dl|%|miu/l|u/ml|ng/ml|pg/ml|mg/l)\b", low, re.I)
        rows.append({
            "marker": matched,
            "name": DISPLAY_NAMES.get(matched, matched.replace("_", " ").title()),
            "value": value,
            "unit": unit_match.group(1) if unit_match else "",
            "reference_range": "",
        })
    return rows

def call_gemini_extract(client, filename, mime_type, data, pdf_text=""):
    schema = {
        "type": "object",
        "properties": {
            "report_date": {"type": "string"},
            "markers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "number"},
                        "unit": {"type": "string"},
                        "reference_range": {"type": "string"},
                    },
                    "required": ["name", "value", "unit", "reference_range"],
                },
            },
        },
        "required": ["report_date", "markers"],
    }

    instruction = """You extract factual laboratory values from a medical diagnostic report.
Do not diagnose, infer missing values, or invent tests. Return only values explicitly present.
For report_date use YYYY-MM-DD if explicitly visible; otherwise return an empty string.
Only extract measurable test markers that have a numeric value. Preserve units and displayed reference range.
"""

    parts = [types.Part.from_text(text=instruction)]
    if pdf_text and len(pdf_text) > 40:
        parts.append(types.Part.from_text(text=f"REPORT TEXT:\n{pdf_text[:45000]}"))
    else:
        parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=types.Content(role="user", parts=parts),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
            temperature=0.0,
        ),
    )
    result = json.loads(response.text)
    clean = []
    for m in result.get("markers", []):
        try:
            clean.append({
                "marker": canonical_name(str(m["name"])),
                "name": DISPLAY_NAMES.get(canonical_name(str(m["name"])), str(m["name"])),
                "value": float(m["value"]),
                "unit": str(m.get("unit", "") or ""),
                "reference_range": str(m.get("reference_range", "") or ""),
            })
        except Exception:
            pass
    return result.get("report_date", "") or "", clean

def parse_report(client, uploaded, manual_date):
    data = uploaded.getvalue()
    mime = uploaded.type or ("application/pdf" if uploaded.name.lower().endswith(".pdf") else "image/jpeg")
    pdf_text = extract_pdf_text(data) if mime == "application/pdf" else ""

    if client:
        date, markers = call_gemini_extract(client, uploaded.name, mime, data, pdf_text)
        return manual_date.isoformat(), markers

    # Fallback works best for text PDFs and is intentionally transparent.
    markers = fallback_parse(pdf_text)
    return manual_date.isoformat(), markers

def build_comparison(reports):
    """Build a deterministic oldest-to-newest comparison.

    Markers with fewer than two observations are excluded. Markers reported in
    incompatible units are also excluded rather than silently comparing unlike
    measurements.
    """
    all_markers = sorted(set(m["marker"] for r in reports for m in r["markers"]))
    records = []
    skipped_unit_mismatch = []

    for marker in all_markers:
        vals = []
        units_seen = set()
        unit = ""
        display = DISPLAY_NAMES.get(marker, marker.replace("_", " ").title())
        reference_ranges = []

        for r in reports:
            found = next((m for m in r["markers"] if m["marker"] == marker), None)
            vals.append(found["value"] if found else None)
            if found:
                found_unit = str(found.get("unit", "") or "").strip().lower()
                if found_unit:
                    units_seen.add(found_unit)
                    unit = found.get("unit") or unit
                display = found.get("name") or display
                reference_ranges.append(str(found.get("reference_range", "") or "").strip())
            else:
                reference_ranges.append("")

        present = [v for v in vals if v is not None]
        if len(present) < 2:
            continue

        if len(units_seen) > 1:
            skipped_unit_mismatch.append(display)
            continue

        first, last = present[0], present[-1]
        change = last - first
        pct = (change / abs(first) * 100) if first != 0 else None
        records.append({
            "marker": marker,
            "name": display,
            "unit": unit,
            "values": vals,
            "reference_ranges": reference_ranges,
            "first": first,
            "last": last,
            "change": change,
            "pct_change": pct,
        })

    return records, skipped_unit_mismatch

def call_gemini_explain(client, reports, comparison, language="English"):
    compact_reports = [
        {"date": r["date"], "source": r["source"], "markers": r["markers"]}
        for r in reports
    ]
    prompt = f"""You are SwasthAI, a patient-facing longitudinal medical report assistant.
Your job is to explain ONLY the factual changes already extracted from the user's reports.

REPORT DATA:
{json.dumps(compact_reports, ensure_ascii=False)}

DETERMINISTIC COMPARISON:
{json.dumps(comparison, ensure_ascii=False)}

Write the patient-facing wording in {language}. Keep marker names and units recognizable.

Create a concise patient-friendly explanation in JSON with:
- overall_summary: 2-4 sentences describing broad patterns without diagnosis.
- key_changes: array of objects with marker, change_summary, plain_explanation.
- doctor_questions: 3-5 useful questions based on the observed changes.
- limitations: one short sentence saying context such as history, symptoms and clinician interpretation matters.

Safety rules:
- Do NOT diagnose a disease.
- Do NOT tell the user to start, stop or change medication.
- Do NOT claim urgency or emergency from laboratory values alone.
- Do NOT invent missing results or reference ranges.
- Use neutral language such as "increased", "decreased", "changed", and "worth discussing with your clinician".
- This is educational explanation, not medical advice.
"""
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return json.loads(response.text)

def local_explanation(comparison, language="English"):
    changes = []
    for row in comparison:
        direction = "increased" if row["change"] > 0 else "decreased" if row["change"] < 0 else "remained unchanged"
        unit = f" {row['unit']}" if row["unit"] else ""
        changes.append({
            "marker": row["name"],
            "change_summary": f"{row['name']} {direction} from {row['first']}{unit} to {row['last']}{unit}.",
            "plain_explanation": "This comparison shows how this measured value changed across the reports you uploaded. Its personal significance depends on your medical history and clinician's interpretation.",
        })
    if language == "Hindi":
        overall = "नीचे दी गई तुलना उन स्वास्थ्य मानकों को दिखाती है जो कम-से-कम दो अपलोड की गई रिपोर्टों में मिले। SwasthAI ने इन्हें समय के क्रम में व्यवस्थित किया है ताकि आप इन्हें अपने डॉक्टर के साथ आसानी से चर्चा कर सकें।"
        questions = [
            "मेरी स्थिति में इन रिपोर्टों के कौन-से बदलाव सबसे महत्वपूर्ण हैं?",
            "मेरी मेडिकल हिस्ट्री के साथ इन नतीजों को कैसे समझा जाना चाहिए?",
            "क्या इनमें से किसी ट्रेंड के लिए फॉलो-अप या दोबारा टेस्ट की जरूरत हो सकती है?",
        ]
        limitation = "यह तुलना केवल जानकारी के लिए है और योग्य स्वास्थ्य विशेषज्ञ की व्याख्या का विकल्प नहीं है।"
    else:
        overall = "The comparison below shows values that appeared in at least two uploaded reports. SwasthAI has organized the changes over time so you can review them more easily before discussing them with your healthcare professional."
        questions = [
            "Which changes in these reports are most important in my situation?",
            "How should these results be interpreted alongside my medical history?",
            "Do any of these trends need follow-up or repeat testing?",
        ]
        limitation = "This comparison is educational and cannot replace interpretation by a qualified healthcare professional."
    return {
        "overall_summary": overall,
        "key_changes": changes[:6],
        "doctor_questions": questions,
        "limitations": limitation,
    }

MONTH_LOOKUP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

def infer_date_from_filename(filename):
    """Best-effort default date from filenames such as Report_January_2025.pdf or 2025_01_15.pdf."""
    stem = os.path.splitext(os.path.basename(filename))[0].lower()

    # Treat underscores, dots and hyphens as separators before matching.
    # This makes names such as Sample_Report_January_2025 work reliably.
    normalized = re.sub(r"[_\-.]+", " ", stem)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # YYYY MM DD after normalization.
    match = re.search(
        r"(?<!\d)(20\d{2})\s+(0?[1-9]|1[0-2])\s+(0?[1-9]|[12]\d|3[01])(?!\d)",
        normalized,
    )
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
        except ValueError:
            pass

    # Month name + year, or year + month name.
    for month_name, month_num in sorted(MONTH_LOOKUP.items(), key=lambda x: -len(x[0])):
        match = re.search(rf"(?<![a-z]){month_name}\s+(20\d{{2}})(?!\d)", normalized)
        if match:
            return datetime(int(match.group(1)), month_num, 1).date()

        match = re.search(rf"(?<!\d)(20\d{{2}})\s+{month_name}(?![a-z])", normalized)
        if match:
            return datetime(int(match.group(1)), month_num, 1).date()

    # Year only.
    match = re.search(r"(?<!\d)(20\d{2})(?!\d)", normalized)
    if match:
        return datetime(int(match.group(1)), 1, 1).date()

    return datetime.today().date()

def sort_reports_chronologically(reports):
    """Return reports sorted by their confirmed report date, oldest to newest."""
    return sorted(reports, key=lambda r: datetime.fromisoformat(r["date"]))

def format_report_dates(reports):
    reports = sort_reports_chronologically(reports)
    return [datetime.fromisoformat(r["date"]).strftime("%d %b %Y") for r in reports]

def format_report_date_labels(reports):
    """Keep chart/table labels unique even if a user accidentally selects duplicate dates."""
    reports = sort_reports_chronologically(reports)
    labels = format_report_dates(reports)
    counts = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1

    used = {}
    final_labels = []
    for report, label in zip(reports, labels):
        if counts[label] == 1:
            final_labels.append(label)
        else:
            used[label] = used.get(label, 0) + 1
            source = os.path.splitext(report.get("source", ""))[0]
            final_labels.append(f"{label} ({source or used[label]})")
    return final_labels

def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

# -----------------------------
# State
# -----------------------------
if "analysis" not in st.session_state:
    st.session_state.analysis = None

# -----------------------------
# Header
# -----------------------------
st.markdown("""
<div class="hero">
    <div class="pill">SwasthAI V1</div>
    <div class="pill">Longitudinal Report Comparison</div>
    <h1>See what changed. Understand your health journey.</h1>
    <p>Upload medical reports from different dates. SwasthAI organizes comparable markers, shows changes over time, and turns them into a simple discussion brief for your next doctor visit.</p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
for col, title, text in [
    (c1, "1. Add reports", "Upload 2–5 reports from different dates."),
    (c2, "2. Compare changes", "Common markers are matched and arranged chronologically."),
    (c3, "3. Prepare for discussion", "Changes are explained in plain language with doctor questions."),
]:
    with col:
        st.markdown(f'<div class="card"><div class="small-label">{title}</div><div class="muted" style="margin-top:.45rem">{text}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Build your comparison</div>', unsafe_allow_html=True)
client = get_client()

reset_col, _ = st.columns([1, 2])
with reset_col:
    if st.button("Start a new comparison", use_container_width=True):
        st.session_state.analysis = None
        st.rerun()

st.caption("SwasthAI compares only values that are explicitly extracted from your uploaded reports. Review the report dates before running the comparison.")

# The initial comparison is generated in English. Users can switch the
# patient-facing explanation language after the factual comparison is ready.
output_language = "English"

with st.container(border=False):
    uploaded_files = st.file_uploader(
        "Upload 2–5 medical reports",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="For the most reliable comparison, use reports containing repeated lab markers and enter each report's date correctly. Dates are prefilled from filenames when possible, but always review them before comparing.",
    )

if not client:
    st.warning("Gemini API key is not configured. The app can still perform a limited text-PDF fallback, but full PDF/image extraction and AI explanations require GEMINI_API_KEY.")

if uploaded_files:
    if len(uploaded_files) < 2:
        st.info("Please upload at least 2 reports to compare changes over time.")
    elif len(uploaded_files) > 5:
        st.error("Please upload a maximum of 5 reports for this MVP.")
    else:
        st.markdown("#### Report dates")
        dates = {}
        cols = st.columns(min(3, len(uploaded_files)))
        for i, f in enumerate(uploaded_files):
            with cols[i % len(cols)]:
                dates[f.name] = st.date_input(
                    f"Date for {f.name}",
                    value=infer_date_from_filename(f.name),
                    key=f"date_v2_{i}_{f.name}",
                )

        if st.button("Compare my reports", use_container_width=True):
            try:
                with st.status("Building your longitudinal comparison...", expanded=True) as status:
                    st.write("Reading uploaded reports...")
                    parsed = []
                    for f in uploaded_files:
                        date, markers = parse_report(client, f, dates[f.name])
                        parsed.append({"date": date, "source": f.name, "markers": markers})
                    st.write("Matching comparable health markers...")
                    # Always put the user-confirmed report dates in chronological order.
                    parsed.sort(key=lambda x: datetime.fromisoformat(x["date"]))
                    comparison, skipped_unit_mismatch = build_comparison(parsed)

                    if not comparison:
                        status.update(label="No comparable markers found", state="error")
                        st.error("We could not find enough common numeric markers across the uploaded reports. Try reports with overlapping tests, such as multiple CBC, HbA1c, thyroid or lipid reports.")
                    else:
                        st.write("Creating patient-friendly explanation...")
                        explanation = call_gemini_explain(client, parsed, comparison, output_language) if client else local_explanation(comparison, output_language)
                        status.update(label="Comparison ready", state="complete")
                        st.session_state.analysis = {
                            "reports": parsed,
                            "comparison": comparison,
                            "explanation": explanation,
                            "skipped_unit_mismatch": skipped_unit_mismatch,
                            "language": output_language,
                        }
            except Exception as e:
                st.error(f"We couldn't complete the analysis. Details: {e}")

# -----------------------------
# Results
# -----------------------------
if st.session_state.analysis:
    a = st.session_state.analysis
    # Defensive sort: results, table, chart and narrative should always use the
    # same oldest-to-newest order, even if session state came from an earlier run.
    reports = sort_reports_chronologically(a["reports"])
    comparison, current_unit_mismatches = build_comparison(reports)
    skipped_unit_mismatch = a.get("skipped_unit_mismatch", current_unit_mismatches)
    explanation = a["explanation"]
    dates_display = format_report_dates(reports)
    date_labels = format_report_date_labels(reports)

    st.markdown('<div class="section-title">Your health journey at a glance</div>', unsafe_allow_html=True)

    changed_up = sum(1 for r in comparison if r["change"] > 0)
    changed_down = sum(1 for r in comparison if r["change"] < 0)
    cols = st.columns(4)
    stats = [
        ("Reports compared", str(len(reports))),
        ("Common markers", str(len(comparison))),
        ("Increased", str(changed_up)),
        ("Decreased", str(changed_down)),
    ]
    for col, (label, value) in zip(cols, stats):
        with col:
            st.markdown(f'<div class="metric-card"><div class="small-label">{label}</div><div class="big-number">{value}</div></div>', unsafe_allow_html=True)

    st.caption(f"Comparison period: {dates_display[0]} to {dates_display[-1]}. Only markers found in at least two reports are included.")
    if skipped_unit_mismatch:
        st.info("Some markers were not compared because the uploaded reports used different units: " + ", ".join(sorted(set(skipped_unit_mismatch))) + ".")

    st.markdown('<div class="section-title">What changed over time?</div>', unsafe_allow_html=True)

    table_rows = []
    for row in comparison:
        out = {"Marker": row["name"], "Unit": row["unit"]}
        for idx, value in enumerate(row["values"]):
            out[date_labels[idx]] = value if value is not None else "—"
        direction = "↑ Increased" if row["change"] > 0 else "↓ Decreased" if row["change"] < 0 else "→ No change"
        out["Overall change"] = f"{row['change']:+.2f} ({direction})"
        table_rows.append(out)
    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("Data check", expanded=False):
        quality_rows = []
        for report in reports:
            quality_rows.append({
                "Report date": datetime.fromisoformat(report["date"]).strftime("%d %b %Y"),
                "Source file": report["source"],
                "Numeric markers extracted": len(report["markers"]),
            })
        st.dataframe(pd.DataFrame(quality_rows), use_container_width=True, hide_index=True)
        st.caption("A higher extraction count does not mean a report is clinically more important. This check is included so you can spot a file that may not have been read as expected.")

    # Trend chart
    st.markdown('<div class="section-title">Trend view</div>', unsafe_allow_html=True)
    st.caption("Choose a marker to view its values across the report dates. This avoids mixing different medical units on one scale.")

    trend_options = {row["name"]: row for row in comparison}
    selected_marker = st.selectbox(
        "Select a marker",
        list(trend_options.keys()),
        key="trend_marker_selector",
    )
    selected_row = trend_options[selected_marker]
    trend_values = [value if value is not None else float("nan") for value in selected_row["values"]]

    # Use the actual uploaded report dates as categorical labels.
    # This prevents the chart from visually implying that measurements were taken
    # every month between two uploaded reports.
    # Explicit ordered categories prevent Streamlit/Altair from re-sorting labels
    # alphabetically (for example, placing 01 Jan 2026 before 01 Jun 2025).
    ordered_dates = pd.Categorical(
        dates_display,
        categories=dates_display,
        ordered=True,
    )
    trend_df = pd.DataFrame({
        "Report date": ordered_dates,
        "Value": trend_values,
    })
    st.line_chart(
        trend_df,
        x="Report date",
        y="Value",
        height=320,
    )

    first_date = dates_display[0]
    last_date = dates_display[-1]
    direction_text = (
        "increased" if selected_row["change"] > 0
        else "decreased" if selected_row["change"] < 0
        else "did not change"
    )
    unit_text = f" {selected_row['unit']}" if selected_row['unit'] else ""
    percent_text = (
        f" ({selected_row['pct_change']:+.1f}%)" if selected_row['pct_change'] is not None else ""
    )
    st.markdown(
        f'<div class="card"><b>{selected_marker} trend:</b> '
        f'{selected_row["first"]}{unit_text} on {first_date} → '
        f'{selected_row["last"]}{unit_text} on {last_date}. '
        f'This is an overall change of {selected_row["change"]:+.2f}{unit_text}{percent_text} and the value {direction_text} across the uploaded reports.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">SwasthAI explanation</div>', unsafe_allow_html=True)
    st.caption("Choose the language for the patient-facing explanation and doctor-visit questions. Lab values, units and the comparison table remain unchanged.")

    selected_explanation_language = st.selectbox(
        "Choose explanation language",
        ["English", "Hindi"],
        index=0 if a.get("language", "English") == "English" else 1,
        key="result_explanation_language",
    )

    # Only regenerate the narrative when the user actually switches language.
    # The factual extraction and deterministic comparison remain unchanged.
    if selected_explanation_language != a.get("language", "English"):
        try:
            with st.spinner(f"Updating explanation to {selected_explanation_language}..."):
                updated_explanation = (
                    call_gemini_explain(client, reports, comparison, selected_explanation_language)
                    if client else local_explanation(comparison, selected_explanation_language)
                )
            st.session_state.analysis["explanation"] = updated_explanation
            st.session_state.analysis["language"] = selected_explanation_language
            explanation = updated_explanation
            a = st.session_state.analysis
        except Exception as e:
            st.warning("The language was not changed because the explanation could not be regenerated. The existing explanation is still available.")

    st.markdown(f'<div class="card">{explanation.get("overall_summary", "")}</div>', unsafe_allow_html=True)

    # A quick deterministic summary keeps the core prototype useful even when AI wording varies.
    largest_absolute = max(comparison, key=lambda r: abs(r["change"]))
    largest_percent = max(
        [r for r in comparison if r["pct_change"] is not None],
        key=lambda r: abs(r["pct_change"]),
        default=None,
    )
    st.markdown("#### What stands out")
    insight_cols = st.columns(2)
    with insight_cols[0]:
        st.markdown(
            f'<div class="metric-card"><div class="small-label">Largest absolute movement</div>'
            f'<div style="font-size:1.1rem;font-weight:750;margin-top:.25rem">{largest_absolute["name"]}</div>'
            f'<div class="muted" style="margin-top:.25rem">{largest_absolute["change"]:+.2f} '
            f'{largest_absolute["unit"]} from first to last report</div></div>',
            unsafe_allow_html=True,
        )
    with insight_cols[1]:
        if largest_percent:
            st.markdown(
                f'<div class="metric-card"><div class="small-label">Largest relative movement</div>'
                f'<div style="font-size:1.1rem;font-weight:750;margin-top:.25rem">{largest_percent["name"]}</div>'
                f'<div class="muted" style="margin-top:.25rem">{largest_percent["pct_change"]:+.1f}% '
                f'from first to last report</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="metric-card"><div class="small-label">Largest relative movement</div><div class="muted" style="margin-top:.5rem">Not available because the first value was zero.</div></div>', unsafe_allow_html=True)

    st.markdown("#### Key changes in simple language")
    for item in explanation.get("key_changes", []):
        with st.expander(item.get("marker", "Health marker"), expanded=True):
            st.markdown(f"**What changed:** {item.get('change_summary', '')}")
            st.markdown(f"**In simple terms:** {item.get('plain_explanation', '')}")

    st.markdown("#### Prepare for your doctor visit")
    for q in explanation.get("doctor_questions", []):
        st.markdown(f"- {q}")

    limitation = explanation.get("limitations", "")
    st.markdown(f'<div class="safe-box"><strong>Important:</strong> {limitation} SwasthAI does not diagnose conditions, replace a clinician, or recommend changing treatment.</div>', unsafe_allow_html=True)

    st.markdown("#### Export your comparison")
    st.caption("Download the structured comparison table for your own records or further discussion. The export contains only the values compared by this prototype.")
    st.download_button(
        "Download comparison as CSV",
        data=csv_bytes(df),
        file_name="swasthai_report_comparison.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.markdown("""
<div class="footer-note">
<b>Privacy-first MVP:</b> This prototype does not require login or a database. Uploaded files are processed for the current session only and are not intentionally retained by the application. SwasthAI organizes extracted report data for discussion; it does not diagnose conditions or replace professional medical care. Do not use it for emergencies.
</div>
""", unsafe_allow_html=True)
