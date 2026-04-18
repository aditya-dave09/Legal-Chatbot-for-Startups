# 1. Install dependencies
!pip install streamlit requests pandas -q

# 2. Write the Streamlit app to a file
app_code = r"""
import os
import json
import time
import re
import math
import requests
import pandas as pd
import streamlit as st
from collections import defaultdict

st.set_page_config(page_title="AI Financial Regulatory Advisor", page_icon="🏦", layout="wide", initial_sidebar_state="expanded")

st.markdown('''
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    .app-header { background: linear-gradient(135deg, #0A2540 0%, #1A3A5C 100%); color: white; padding: 1.2rem 2rem; border-radius: 8px; margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between; }
    .app-header h1 { margin: 0; font-size: 1.4rem; font-weight: 600; }
    .app-header .subtitle { font-size: 0.8rem; color: #94A3B8; margin-top: 2px; }
    .rbi-badge { background: #F59E0B; color: #1C1917; padding: 3px 10px; border-radius: 20px; font-size: 0.72rem; font-weight: 600; }
    .metric-row { display: flex; gap: 12px; margin-bottom: 1.2rem; }
    .metric-card { background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px 18px; flex: 1; }
    .metric-card .label { font-size: 0.72rem; color: #64748B; text-transform: uppercase; }
    .metric-card .value { font-size: 1.4rem; font-weight: 600; color: #0F172A; }
    .gap-card { border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; background: white; }
    .gap-card.critical { border-left: 4px solid #EF4444; }
    .gap-card.high { border-left: 4px solid #F97316; }
    .chat-bubble { padding: 12px 16px; border-radius: 12px; margin-bottom: 8px; max-width: 82%; font-size: 0.9rem; }
    .chat-user { background: #0A2540; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .chat-bot { background: #F1F5F9; color: #0F172A; margin-right: auto; border-bottom-left-radius: 2px; }
    .section-title { font-size: 0.75rem; font-weight: 600; color: #64748B; text-transform: uppercase; border-bottom: 1px solid #E2E8F0; padding-bottom: 6px; margin-bottom: 12px; margin-top: 20px; }
</style>
''', unsafe_allow_html=True)

INTERNAL_POLICIES = {
    "POL-DIG-001": { "policy_id": "POL-DIG-001", "domain": "Digital_Payments", "section": "Section 3.1", "title": "UPI Transaction Cooling Period", "text": "New UPI beneficiaries added via mobile banking are subject to a mandatory cooling period of 12 hours before the first outward transaction can be processed. No outward UPI payments to newly added beneficiaries shall be permitted during this period. The branch manager may override for corporate accounts exceeding INR 10 crore turnover.", "effective_date": "2022-04-01", "last_reviewed": "2023-01-15" },
    "POL-DIG-002": { "policy_id": "POL-DIG-002", "domain": "Digital_Payments", "section": "Section 3.2", "title": "UPI Daily Transaction Limit", "text": "Maximum daily aggregate UPI limit per customer is INR 1,00,000 across all handles. P2P UPI capped at INR 25,000 per transaction. Enhancement up to INR 2,00,000 requires Form UPI-LE with CIBIL score above 700.", "effective_date": "2022-04-01", "last_reviewed": "2023-06-01" },
    "POL-LEN-002": { "policy_id": "POL-LEN-002", "domain": "Lending", "section": "Section 7.8", "title": "Key Facts Statement (KFS) for Retail Loans", "text": "KFS provided to borrowers at branch on the day of loan execution. Customers have 3 days to review before final disbursement. Follows IBA Model template 2019. Signature required same day.", "effective_date": "2021-06-01", "last_reviewed": "2023-08-15" },
    "POL-CYB-001": { "policy_id": "POL-CYB-001", "domain": "Cybersecurity", "section": "Section 11.3", "title": "Cyber Incident Reporting to RBI", "text": "Critical cyber incidents must be reported to RBI within 6 hours of detection. Major incidents within 24 hours. All reports via CSITE portal. Full RCA within 21 days.", "effective_date": "2022-06-01", "last_reviewed": "2024-02-01" },
    "POL-LIQ-001": { "policy_id": "POL-LIQ-001", "domain": "Liquidity_Treasury", "section": "Section 14.1", "title": "Liquidity Coverage Ratio (LCR) Reporting", "text": "Minimum LCR of 100% maintained at all times per Basel III. Daily monitoring by 10 AM. Monthly reports to RBI by 7th of following month. ALCO reviews weekly.", "effective_date": "2019-01-01", "last_reviewed": "2024-03-01" },
}

RBI_CIRCULARS = {
    "RBI-CIR-2024-001": { "circular_id": "RBI-CIR-2024-001", "circular_ref": "RBI/2024-25/47", "subject": "Enhancement of Security Measures for UPI Transactions", "issued_date": "2024-04-15", "compliance_deadline": "2024-07-01", "category": "Digital_Payments", "text": "The minimum cooling period for any new beneficiary registered on a mobile banking application or internet banking portal shall be 24 HOURS. This supersedes any internal bank policy prescribing a shorter cooling period. No exceptions for corporate accounts or HNIs. Banks implementing a shorter cooling period (e.g., 12 hours) must update their systems and internal policies by June 30, 2024." },
    "RBI-CIR-2024-003": { "circular_id": "RBI-CIR-2024-003", "circular_ref": "RBI/2024-25/29", "subject": "Key Facts Statement (KFS) for Loans", "issued_date": "2024-03-22", "compliance_deadline": "2024-10-01", "category": "Lending", "text": "KFS must be provided to the borrower at least 15 DAYS before the date of loan disbursement. Written consent acknowledging receipt of KFS required at least 72 hours before disbursement. Existing policies prescribing any shorter review period (such as 3 days) must be amended." },
}

def tokenize(text: str) -> list:
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return [t for t in text.split() if len(t) > 2]

def build_tfidf_index(documents: dict) -> dict:
    N = len(documents)
    tf = {}
    df = defaultdict(int)
    for doc_id, text in documents.items():
        tokens = tokenize(text)
        n = len(tokens)
        freq = defaultdict(int)
        for t in tokens: freq[t] += 1
        tf[doc_id] = {t: c/n for t, c in freq.items()}
        for t in freq: df[t] += 1
    idf = {t: math.log(N / cnt) for t, cnt in df.items()}
    tfidf = {}
    for doc_id, tfs in tf.items():
        tfidf[doc_id] = {t: tfs[t] * idf.get(t, 0) for t in tfs}
    return tfidf

def cosine_sim(a: dict, b: dict) -> float:
    dot = sum(a.get(t, 0) * b.get(t, 0) for t in a)
    na = math.sqrt(sum(v*v for v in a.values()))
    nb = math.sqrt(sum(v*v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0

def retrieve_policies(query: str, tfidf_index: dict, top_k: int = 4) -> list:
    q_tokens = tokenize(query)
    q_vec = defaultdict(float)
    for t in q_tokens: q_vec[t] += 1.0
    q_norm = max(len(q_tokens), 1)
    q_vec = {t: c/q_norm for t, c in q_vec.items()}
    scores = [(pid, cosine_sim(q_vec, pvec)) for pid, pvec in tfidf_index.items()]
    scores.sort(key=lambda x: x[1], reverse=True)
    return [(INTERNAL_POLICIES[pid], sc) for pid, sc in scores[:top_k] if pid in INTERNAL_POLICIES]

@st.cache_resource
def get_policy_index():
    return build_tfidf_index({pid: p["text"] for pid, p in INTERNAL_POLICIES.items()})

def call_groq(prompt: str, api_key: str) -> str:
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def call_mock_gap(circular: dict) -> str:
    gaps = {
        "RBI-CIR-2024-001": "**EXECUTIVE SUMMARY**\nThis circular mandates a 24-hour UPI cooling period, conflicting with the bank's 12-hour policy (POL-DIG-001). CRITICAL gap requiring immediate system updates.\n\n**GAP FINDINGS**\nGap 1:\n- Internal Policy: POL-DIG-001\n- RBI Requirement: 24 HOURS minimum cooling period\n- Current Status: Bank policy prescribes 12 hours\n- Risk Level: CRITICAL\n\n**MANDATORY ACTION PLAN**\nUpdate POL-DIG-001 to 24 hours and remove corporate overrides by June 30.",
        "RBI-CIR-2024-003": "**EXECUTIVE SUMMARY**\nThis circular mandates a 15-day KFS pre-disbursement window, conflicting with the current 3-day practice (POL-LEN-002).\n\n**GAP FINDINGS**\nGap 1:\n- Internal Policy: POL-LEN-002\n- RBI Requirement: KFS must be provided at least 15 DAYS before disbursement\n- Current Status: 3-day review period\n- Risk Level: HIGH\n\n**MANDATORY ACTION PLAN**\nUpdate POL-LEN-002 to 15 days by Oct 1.",
    }
    return gaps.get(circular["circular_id"], "No significant gap identified.")

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    provider = st.selectbox("LLM Provider", ["Mock (Demo Mode)", "Groq (API Key required)"])
    api_key = st.text_input("API Key", type="password") if "Groq" in provider else ""
    st.markdown("---")
    st.metric("Policies Loaded", len(INTERNAL_POLICIES))
    st.metric("Circulars Monitored", len(RBI_CIRCULARS))

st.markdown('<div class="app-header"><div><h1>🏦 AI Financial Regulatory Advisor</h1><div class="subtitle">Databricks Medallion Backend · TF-IDF Search · LLM Engine</div></div></div>', unsafe_allow_html=True)

tab_gap, tab_chat = st.tabs(["🔍 Gap Analysis Engine", "💬 Chatbot"])

with tab_gap:
    st.markdown('<div class="section-title">Select RBI Circular</div>', unsafe_allow_html=True)
    selected_cid = st.selectbox("Choose a circular:", list(RBI_CIRCULARS.keys()))
    circular = RBI_CIRCULARS[selected_cid]
    
    with st.expander(f"📄 {circular['circular_ref']} - {circular['subject']}", expanded=True):
        st.markdown(f"> {circular['text']}")
    
    if st.button("🔍 Run AI Gap Analysis", type="primary"):
        with st.spinner("Calculating semantic similarity and querying LLM..."):
            matches = retrieve_policies(circular["text"], get_policy_index(), top_k=2)
            st.markdown('<div class="section-title">Retrieved Internal Policies</div>', unsafe_allow_html=True)
            for p, score in matches:
                st.markdown(f"**{p['policy_id']}** (Match Score: {score:.2f}) - {p['title']}")
            
            st.markdown('<div class="section-title">AI Gap Analysis Report</div>', unsafe_allow_html=True)
            if "Groq" in provider and api_key:
                prompt = f"Perform Gap analysis. RBI Circular: {circular['text']}. Bank Policy: {matches[0][0]['text']}. Tell me the gap and action required."
                result = call_groq(prompt, api_key)
            else:
                result = call_mock_gap(circular)
            
            st.markdown(f'<div class="gap-card critical">{result.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

with tab_chat:
    st.markdown("Ask the AI about your internal policies.")
    if "msgs" not in st.session_state:
        st.session_state.msgs = [{"role": "assistant", "content": "How can I help you with compliance today?"}]
    for msg in st.session_state.msgs:
        st.markdown(f'<div class="chat-bubble {"chat-user" if msg["role"] == "user" else "chat-bot"}">{msg["content"]}</div>', unsafe_allow_html=True)
    if prompt := st.chat_input("E.g., What is our UPI cooling period?"):
        st.session_state.msgs.append({"role": "user", "content": prompt})
        st.rerun()
"""

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)

print("✅ app.py successfully saved to your Databricks cluster!")

# 3. Clean up, Start Streamlit, and Launch Tunnel
import time
import os

print("🧹 Cleaning up old processes...")
os.system("pkill -f streamlit")
os.system("pkill -f cloudflared")
time.sleep(2)

print("🚀 Starting Streamlit exactly on port 8501...")
get_ipython().system_raw('streamlit run app.py --server.port 8501 &')
time.sleep(4)

print("📥 Downloading correct Cloudflare Tunnel for your specific server...")
# This detects if your server is ARM (aarch64) or Intel/AMD and downloads the right one!
get_ipython().system_raw('''
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -O cloudflared
else
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
fi
chmod +x cloudflared
''')
time.sleep(2)

print("======================================================")
print("🌐 LOOK BELOW FOR THE LINK ENDING IN '.trycloudflare.com'")
print("======================================================")
!./cloudflared tunnel --url http://localhost:8501