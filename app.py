
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
    div[data-testid="stFileUploader"] {
        background: white; border: 1px dashed #9FB8C5; border-radius: 16px; padding: .4rem;
    }
    .stButton > button {
        border-radius: 12px; border: 0; padding: .65rem 1rem; font-weight: 700;
        background: linear-gradient(135deg, #0F766E, #0B5C67); color: white;
    }
    .stDownloadButton > button {
        border-radius: 12px; font-weight: 700;
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
        model="gemini-2.5-flash",
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
    all_markers = sorted(set(m["marker"] for r in reports for m in r["markers"]))
    records = []
    for marker in all_markers:
        vals = []
        unit = ""
        display = DISPLAY_NAMES.get(marker, marker.replace("_", " ").title())
        for r in reports:
            found = next((m for m in r["markers"] if m["marker"] == marker), None)
            vals.append(found["value"] if found else None)
            if found and found.get("unit"):
                unit = found["unit"]
                display = found.get("name") or display
        present = [v for v in vals if v is not None]
        if len(present) < 2:
            continue
        first, last = present[0], present[-1]
        change = last - first
        pct = (change / abs(first) * 100) if first != 0 else None
        records.append({
            "marker": marker,
            "name": display,
            "unit": unit,
            "values": vals,
            "first": first,
            "last": last,
            "change": change,
            "pct_change": pct,
        })
    return records

def call_gemini_explain(client, reports, comparison):
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
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return json.loads(response.text)

def local_explanation(comparison):
    changes = []
    for row in comparison:
        direction = "increased" if row["change"] > 0 else "decreased" if row["change"] < 0 else "remained unchanged"
        unit = f" {row['unit']}" if row["unit"] else ""
        changes.append({
            "marker": row["name"],
            "change_summary": f"{row['name']} {direction} from {row['first']}{unit} to {row['last']}{unit}.",
            "plain_explanation": "This comparison shows how this measured value changed across the reports you uploaded. Its personal significance depends on your medical history and clinician's interpretation.",
        })
    return {
        "overall_summary": "The comparison below shows values that appeared in at least two uploaded reports. SwasthAI has organized the changes over time so you can review them more easily before discussing them with your healthcare professional.",
        "key_changes": changes[:6],
        "doctor_questions": [
            "Which changes in these reports are most important in my situation?",
            "How should these results be interpreted alongside my medical history?",
            "Do any of these trends need follow-up or repeat testing?",
        ],
        "limitations": "This comparison is educational and cannot replace interpretation by a qualified healthcare professional.",
    }

def format_report_dates(reports):
    return [datetime.fromisoformat(r["date"]).strftime("%d %b %Y") for r in reports]

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

with st.container(border=False):
    uploaded_files = st.file_uploader(
        "Upload 2–5 medical reports",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="For the most reliable comparison, use reports containing repeated lab markers and enter each report's date correctly.",
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
                    value=datetime.today().date(),
                    key=f"date_{i}_{f.name}",
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
                    parsed.sort(key=lambda x: x["date"])
                    comparison = build_comparison(parsed)

                    if not comparison:
                        status.update(label="No comparable markers found", state="error")
                        st.error("We could not find enough common numeric markers across the uploaded reports. Try reports with overlapping tests, such as multiple CBC, HbA1c, thyroid or lipid reports.")
                    else:
                        st.write("Creating patient-friendly explanation...")
                        explanation = call_gemini_explain(client, parsed, comparison) if client else local_explanation(comparison)
                        status.update(label="Comparison ready", state="complete")
                        st.session_state.analysis = {
                            "reports": parsed,
                            "comparison": comparison,
                            "explanation": explanation,
                        }
            except Exception as e:
                st.error(f"We couldn't complete the analysis. Details: {e}")

# -----------------------------
# Results
# -----------------------------
if st.session_state.analysis:
    a = st.session_state.analysis
    reports = a["reports"]
    comparison = a["comparison"]
    explanation = a["explanation"]
    dates_display = format_report_dates(reports)

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

    st.markdown('<div class="section-title">What changed over time?</div>', unsafe_allow_html=True)

    table_rows = []
    for row in comparison:
        out = {"Marker": row["name"], "Unit": row["unit"]}
        for idx, value in enumerate(row["values"]):
            out[dates_display[idx]] = value if value is not None else "—"
        direction = "↑ Increased" if row["change"] > 0 else "↓ Decreased" if row["change"] < 0 else "→ No change"
        out["Overall change"] = f"{row['change']:+.2f} ({direction})"
        table_rows.append(out)
    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Trend chart
    chart_data = {}
    for row in comparison:
        vals = [v if v is not None else None for v in row["values"]]
        chart_data[row["name"]] = vals
    chart_df = pd.DataFrame(chart_data, index=dates_display)
    st.markdown('<div class="section-title">Trend view</div>', unsafe_allow_html=True)
    st.caption("Only markers found in at least two reports are shown. Different markers may use different units, so compare each line independently.")
    st.line_chart(chart_df)

    st.markdown('<div class="section-title">SwasthAI explanation</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="card">{explanation.get("overall_summary", "")}</div>', unsafe_allow_html=True)

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

    st.download_button(
        "Download comparison as CSV",
        data=csv_bytes(df),
        file_name="swasthai_report_comparison.csv",
        mime="text/csv",
    )

st.markdown("""
<div class="footer-note">
<b>Privacy-first MVP:</b> This prototype does not require login or a database. Uploaded files are processed for the current session only and are not intentionally retained by the application. Do not use this educational prototype for emergencies or as a substitute for professional medical care.
</div>
""", unsafe_allow_html=True)
