# SwasthAI V1 — Longitudinal Medical Report Comparison

## What this MVP demonstrates
A chronic-care patient uploads 2–5 medical reports from different dates. SwasthAI:
1. extracts measurable lab markers,
2. matches common markers across reports,
3. arranges values chronologically,
4. calculates changes,
5. shows a trend view, and
6. uses Gemini to explain the observed changes in plain language and generate questions for a doctor discussion.

## Product scope
This is deliberately one focused workflow for the MBA Digital Product Management project:
**Upload reports → compare longitudinal changes → explain changes → prepare for doctor discussion.**

Out of scope: diagnosis, medication changes, emergency triage, patient accounts, database/history, reminders, symptom tracking, prescription management, and other broader SwasthAI roadmap features.

## Run locally
```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your_api_key"
streamlit run app.py
```

On Windows PowerShell:
```powershell
$env:GEMINI_API_KEY="your_api_key"
streamlit run app.py
```

## Streamlit Cloud
Add this secret in Streamlit Cloud:
```toml
GEMINI_API_KEY = "your_api_key"
```

## Demo recommendation
Use 2–3 synthetic or consented, de-identified reports with overlapping markers. Do not upload sensitive real patient data during a classroom demo unless appropriate consent and privacy safeguards are in place.

## Safety
SwasthAI is an educational comparison tool. It does not diagnose disease, replace professional medical interpretation, or recommend treatment changes.
