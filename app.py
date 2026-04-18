"""
AI Financial Regulatory Advisor — Streamlit Application
app.py

Run locally:
    pip install streamlit requests pandas
    streamlit run app.py

Environment variables required:
    GROQ_API_KEY     — Groq API key (free at console.groq.com)
    GEMINI_API_KEY   — Optional alternative LLM

Architecture:
    - Reads data from embedded mock JSON (no live Spark session required for demo)
    - Calls external LLM API (Groq / Gemini / Mock) for gap analysis + translation
    - Two tabs: Gap Analysis | Chat & Translate
"""

import os
import json
import time
import re
import math
import requests
import pandas as pd
import streamlit as st
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Financial Regulatory Advisor",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS — Clean banking-grade aesthetic
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Import professional font */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    
    /* Top header bar */
    .app-header {
        background: linear-gradient(135deg, #0A2540 0%, #1A3A5C 100%);
        color: white;
        padding: 1.2rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .app-header h1 { margin: 0; font-size: 1.4rem; font-weight: 600; letter-spacing: -0.3px; }
    .app-header .subtitle { font-size: 0.8rem; color: #94A3B8; margin-top: 2px; }
    .rbi-badge {
        background: #F59E0B; color: #1C1917;
        padding: 3px 10px; border-radius: 20px; font-size: 0.72rem; font-weight: 600;
    }
    
    /* Metric cards */
    .metric-row { display: flex; gap: 12px; margin-bottom: 1.2rem; }
    .metric-card {
        background: white; border: 1px solid #E2E8F0;
        border-radius: 8px; padding: 14px 18px;
        flex: 1; min-width: 0;
    }
    .metric-card .label { font-size: 0.72rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-card .value { font-size: 1.4rem; font-weight: 600; color: #0F172A; margin-top: 4px; }
    .metric-card .delta { font-size: 0.75rem; color: #EF4444; margin-top: 2px; }
    .metric-card.ok .delta { color: #22C55E; }
    
    /* Gap finding card */
    .gap-card {
        border: 1px solid #E2E8F0; border-radius: 8px;
        padding: 16px 20px; margin-bottom: 12px;
        background: white;
    }
    .gap-card.critical { border-left: 4px solid #EF4444; }
    .gap-card.high     { border-left: 4px solid #F97316; }
    .gap-card.medium   { border-left: 4px solid #F59E0B; }
    .gap-card.low      { border-left: 4px solid #22C55E; }
    
    .risk-badge {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        font-size: 0.7rem; font-weight: 600; margin-bottom: 8px;
    }
    .risk-badge.critical { background: #FEE2E2; color: #991B1B; }
    .risk-badge.high     { background: #FFEDD5; color: #9A3412; }
    .risk-badge.medium   { background: #FEF9C3; color: #854D0E; }
    .risk-badge.low      { background: #DCFCE7; color: #166534; }
    
    /* Chat bubbles */
    .chat-bubble {
        padding: 12px 16px; border-radius: 12px; margin-bottom: 8px;
        max-width: 82%; font-size: 0.9rem; line-height: 1.55;
    }
    .chat-user { background: #0A2540; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .chat-bot  { background: #F1F5F9; color: #0F172A; margin-right: auto; border-bottom-left-radius: 2px; }
    .chat-meta { font-size: 0.7rem; color: #94A3B8; margin-bottom: 12px; }
    
    /* Section titles */
    .section-title {
        font-size: 0.75rem; font-weight: 600; color: #64748B;
        text-transform: uppercase; letter-spacing: 0.8px;
        border-bottom: 1px solid #E2E8F0; padding-bottom: 6px;
        margin-bottom: 12px; margin-top: 20px;
    }
    
    /* Streamlit overrides */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 500; font-size: 0.88rem;
    }
    div[data-testid="stExpander"] { border: 1px solid #E2E8F0 !important; border-radius: 8px; }
    .stTextArea textarea { font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem; }
    .stButton > button { font-family: 'IBM Plex Sans', sans-serif; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDED DATA (mirrors what Databricks pipeline produces)
# No live Spark session required for the demo
# ─────────────────────────────────────────────────────────────────────────────

INTERNAL_POLICIES = {
    "POL-DIG-001": {
        "policy_id": "POL-DIG-001", "domain": "Digital_Payments", "section": "Section 3.1",
        "title": "UPI Transaction Cooling Period",
        "text": (
            "New UPI beneficiaries added via mobile banking are subject to a mandatory cooling "
            "period of 12 hours before the first outward transaction can be processed. No outward "
            "UPI payments to newly added beneficiaries shall be permitted during this period. "
            "The branch manager may override for corporate accounts exceeding INR 10 crore turnover."
        ),
        "effective_date": "2022-04-01", "last_reviewed": "2023-01-15",
    },
    "POL-DIG-002": {
        "policy_id": "POL-DIG-002", "domain": "Digital_Payments", "section": "Section 3.2",
        "title": "UPI Daily Transaction Limit",
        "text": (
            "Maximum daily aggregate UPI limit per customer is INR 1,00,000 across all handles. "
            "P2P UPI capped at INR 25,000 per transaction. Enhancement up to INR 2,00,000 requires "
            "Form UPI-LE with CIBIL score above 700."
        ),
        "effective_date": "2022-04-01", "last_reviewed": "2023-06-01",
    },
    "POL-DIG-003": {
        "policy_id": "POL-DIG-003", "domain": "Digital_Payments", "section": "Section 3.5",
        "title": "Failed UPI Transaction Reversal Timeline",
        "text": (
            "Failed UPI transaction where account debited must be auto-reversed within T+3 business days. "
            "Escalation to NPCI after T+5 days. Customer compensation of INR 100 per day for delays beyond T+5."
        ),
        "effective_date": "2021-07-01", "last_reviewed": "2022-11-01",
    },
    "POL-KYC-001": {
        "policy_id": "POL-KYC-001", "domain": "KYC_AML", "section": "Section 5.1",
        "title": "Video KYC Re-verification Frequency",
        "text": (
            "Customers onboarded via V-CIP must undergo re-verification every 36 months. "
            "Non-completion triggers Restricted Operations mode. Senior citizens (70+) exempt from video requirement."
        ),
        "effective_date": "2021-01-01", "last_reviewed": "2023-09-01",
    },
    "POL-KYC-002": {
        "policy_id": "POL-KYC-002", "domain": "KYC_AML", "section": "Section 5.4",
        "title": "Risk Categorisation of Customers (AML)",
        "text": (
            "Customers classified Low/Medium/High at onboarding via AML scoring model. "
            "High-risk: EDD + 12-month review. Medium: 24 months. Low: 36 months. PEPs auto High Risk."
        ),
        "effective_date": "2020-10-01", "last_reviewed": "2023-03-01",
    },
    "POL-LEN-001": {
        "policy_id": "POL-LEN-001", "domain": "Lending", "section": "Section 7.2",
        "title": "Personal Loan Interest Rate Reset Policy",
        "text": (
            "Floating rate personal loans linked to MCLR with annual reset. Rate changes communicated "
            "7 days prior via SMS and email. Customers may switch to fixed rate at 0.5% conversion fee."
        ),
        "effective_date": "2022-04-01", "last_reviewed": "2024-01-01",
    },
    "POL-LEN-002": {
        "policy_id": "POL-LEN-002", "domain": "Lending", "section": "Section 7.8",
        "title": "Key Facts Statement (KFS) for Retail Loans",
        "text": (
            "KFS provided to borrowers at branch on the day of loan execution. Customers have 3 days "
            "to review before final disbursement. Follows IBA Model template 2019. Signature required same day."
        ),
        "effective_date": "2021-06-01", "last_reviewed": "2023-08-15",
    },
    "POL-GRV-001": {
        "policy_id": "POL-GRV-001", "domain": "Customer_Grievance", "section": "Section 9.1",
        "title": "Customer Complaint Resolution TAT",
        "text": (
            "Complaints acknowledged within 24 hours. Unauthorised transactions resolved in 7 working days. "
            "General complaints in 15 working days. Governed by RBI Integrated Ombudsman Scheme 2021."
        ),
        "effective_date": "2021-11-01", "last_reviewed": "2023-10-01",
    },
    "POL-CYB-001": {
        "policy_id": "POL-CYB-001", "domain": "Cybersecurity", "section": "Section 11.3",
        "title": "Cyber Incident Reporting to RBI",
        "text": (
            "Critical cyber incidents must be reported to RBI within 6 hours of detection. Major incidents "
            "within 24 hours. All reports via CSITE portal. Full RCA within 21 days."
        ),
        "effective_date": "2022-06-01", "last_reviewed": "2024-02-01",
    },
    "POL-LIQ-001": {
        "policy_id": "POL-LIQ-001", "domain": "Liquidity_Treasury", "section": "Section 14.1",
        "title": "Liquidity Coverage Ratio (LCR) Reporting",
        "text": (
            "Minimum LCR of 100% maintained at all times per Basel III. Daily monitoring by 10 AM. "
            "Monthly reports to RBI by 7th of following month. ALCO reviews weekly."
        ),
        "effective_date": "2019-01-01", "last_reviewed": "2024-03-01",
    },
}

RBI_CIRCULARS = {
    "RBI-CIR-2024-001": {
        "circular_id": "RBI-CIR-2024-001",
        "circular_ref": "RBI/2024-25/47 DPSS.CO.RPPD.No.S-471/04.03.006/2024-25",
        "subject": "Enhancement of Security Measures for UPI Transactions — Mandatory Cooling Period Revision",
        "issued_date": "2024-04-15", "effective_date": "2024-07-01",
        "compliance_deadline": "2024-07-01", "category": "Digital_Payments",
        "text": (
            "The minimum cooling period for any new beneficiary registered on a mobile banking "
            "application or internet banking portal shall be 24 HOURS. This supersedes any internal "
            "bank policy prescribing a shorter cooling period. No exceptions for corporate accounts or HNIs. "
            "Banks implementing a shorter cooling period (e.g., 12 hours) must update their systems "
            "and internal policies by June 30, 2024. Compliance confirmation required by July 15, 2024."
        ),
    },
    "RBI-CIR-2024-002": {
        "circular_id": "RBI-CIR-2024-002",
        "circular_ref": "RBI/2024-25/52 DPSS.CO.RPPD.No.S-520/04.03.006/2024-25",
        "subject": "Revision of UPI Transaction Limits for Specific Categories",
        "issued_date": "2024-05-10", "effective_date": "2024-08-01",
        "compliance_deadline": "2024-08-01", "category": "Digital_Payments",
        "text": (
            "Tax payment transactions via UPI enhanced to INR 5,00,000. IPO applications via UPI: "
            "INR 5,00,000. Hospital/medical emergencies: INR 2,00,000. Educational fees: INR 2,00,000. "
            "Banks must implement category-specific limits and update transaction monitoring rules."
        ),
    },
    "RBI-CIR-2024-003": {
        "circular_id": "RBI-CIR-2024-003",
        "circular_ref": "RBI/2024-25/29 DOR.MCS.REC.No.37/01.01.003/2024-25",
        "subject": "Key Facts Statement (KFS) for Loans — Mandatory Enhanced Disclosure and Review Period",
        "issued_date": "2024-03-22", "effective_date": "2024-10-01",
        "compliance_deadline": "2024-10-01", "category": "Lending",
        "text": (
            "KFS must be provided to the borrower at least 15 DAYS before the date of loan disbursement. "
            "Written consent acknowledging receipt of KFS required at least 72 hours before disbursement. "
            "KFS must be provided in borrower's preferred regional language in addition to English. "
            "Existing policies prescribing any shorter review period (such as 3 days) must be amended."
        ),
    },
    "RBI-CIR-2024-004": {
        "circular_id": "RBI-CIR-2024-004",
        "circular_ref": "RBI/2024-25/61 DoS.CO.CSITE.SEC.No.1/31.01.015/2024-25",
        "subject": "Revised Timeline for Cyber Incident Reporting to RBI",
        "issued_date": "2024-06-01", "effective_date": "2024-09-01",
        "compliance_deadline": "2024-09-01", "category": "Cybersecurity",
        "text": (
            "Critical cyber incidents must be reported to RBI within 2 HOURS of initial detection "
            "(supersedes earlier 6-hour timeline). Major incidents: 6 hours. Significant incidents: 24 hours. "
            "All reports via CSITE 2.0 portal. Banks must update Cybersecurity Incident Response Plans."
        ),
    },
    "RBI-CIR-2024-005": {
        "circular_id": "RBI-CIR-2024-005",
        "circular_ref": "RBI/2024-25/71 DOR.MRG.REC.No.88/00-00-010/2024-25",
        "subject": "Strengthening Liquidity Risk Management — LCR Enhancement",
        "issued_date": "2024-07-15", "effective_date": "2025-01-01",
        "compliance_deadline": "2025-01-01", "category": "Liquidity_Treasury",
        "text": (
            "Minimum LCR enhanced to 110% from January 1, 2025. Phased: 105% by October 1, 2024, "
            "110% by January 1, 2025. Digital deposit run-off rate revised to 7.5% from 5%. "
            "Intraday LCR monitoring for banks with balance sheet over INR 1 lakh crore by March 2025."
        ),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# TF-IDF RETRIEVAL (pure Python, no Spark needed for Streamlit)
# ─────────────────────────────────────────────────────────────────────────────

def tokenize(text: str) -> list:
    """Simple whitespace + punctuation tokenizer."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()
    stopwords = {
        "the","a","an","and","or","but","in","on","at","to","for","of","with","by",
        "is","are","was","were","be","been","being","have","has","had","do","does",
        "did","will","would","shall","should","may","might","must","can","could",
        "this","that","these","those","it","its","from","as","all","any","each",
        "bank","banks","rbi","reserve","india","shall","must","effective","following",
    }
    return [t for t in tokens if len(t) > 2 and t not in stopwords]

def build_tfidf_index(documents: dict) -> dict:
    """Builds a TF-IDF index from a dict of {id: text}."""
    N = len(documents)
    tf = {}
    df = defaultdict(int)
    for doc_id, text in documents.items():
        tokens = tokenize(text)
        n = len(tokens)
        freq = defaultdict(int)
        for t in tokens:
            freq[t] += 1
        tf[doc_id] = {t: c/n for t, c in freq.items()}
        for t in freq:
            df[t] += 1
    idf = {t: math.log(N / cnt) for t, cnt in df.items()}
    tfidf = {}
    for doc_id, tfs in tf.items():
        tfidf[doc_id] = {t: tfs[t] * idf.get(t, 0) for t in tfs}
    return tfidf

def cosine_sim(a: dict, b: dict) -> float:
    """Cosine similarity between two TF-IDF dicts."""
    dot = sum(a.get(t, 0) * b.get(t, 0) for t in a)
    na  = math.sqrt(sum(v*v for v in a.values()))
    nb  = math.sqrt(sum(v*v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0

def retrieve_policies(query: str, tfidf_index: dict, top_k: int = 4) -> list:
    """Retrieves top-k policies matching the query."""
    q_tokens = tokenize(query)
    q_vec    = defaultdict(float)
    for t in q_tokens:
        q_vec[t] += 1.0
    q_norm = max(len(q_tokens), 1)
    q_vec  = {t: c/q_norm for t, c in q_vec.items()}
    scores = [(pid, cosine_sim(q_vec, pvec)) for pid, pvec in tfidf_index.items()]
    scores.sort(key=lambda x: x[1], reverse=True)
    return [(INTERNAL_POLICIES[pid], sc) for pid, sc in scores[:top_k] if pid in INTERNAL_POLICIES]

@st.cache_resource
def get_policy_index():
    """Cached TF-IDF index — built once, reused across sessions."""
    texts = {pid: p["text"] for pid, p in INTERNAL_POLICIES.items()}
    return build_tfidf_index(texts)

# ─────────────────────────────────────────────────────────────────────────────
# LLM API LAYER
# ─────────────────────────────────────────────────────────────────────────────

def call_groq(prompt: str, api_key: str, model: str = "llama-3.3-70b-versatile") -> str:
    """Calls Groq API. Free key at console.groq.com"""
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1, "max_tokens": 2000},
        timeout=40,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_gemini(prompt: str, api_key: str) -> str:
    """Calls Google Gemini 1.5 Flash."""
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000}},
        timeout=40,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def call_mock_gap(circular: dict, policies: list) -> str:
    """Deterministic mock for demo without API key."""
    cid = circular["circular_id"]
    gaps = {
        "RBI-CIR-2024-001": """**EXECUTIVE SUMMARY**
This circular mandates a 24-hour UPI beneficiary cooling period, directly conflicting with the bank's current 12-hour policy (POL-DIG-001). This is a CRITICAL gap requiring immediate system and policy updates before July 1, 2024.

**GAP FINDINGS**
Gap 1:
- Internal Policy : POL-DIG-001 — Section 3.1 — UPI Transaction Cooling Period
- RBI Requirement : "The minimum cooling period shall be 24 HOURS. No exceptions for corporate accounts."
- Current Status  : Bank policy prescribes 12 hours; grants override for corporate accounts >INR 10 crore
- Gap Description : Two-fold gap: (1) Duration is 50% below the RBI mandate; (2) Exception for corporate accounts is explicitly prohibited
- Risk Level      : CRITICAL

**MANDATORY ACTION PLAN**
Action 1:
- Owner           : Digital Banking Head + Head of Compliance
- Policy to Update: POL-DIG-001 — Section 3.1
- Specific Change : Change "12 hours" to "24 hours" AND remove the corporate account override provision entirely
- Deadline        : 2024-06-30 (1 day before effective date)
- Validation Step : UAT sign-off on mobile banking app; compliance officer test transaction

**COMPLIANCE TIMELINE**
1. IMMEDIATE (by May 15): IT ticket raised, policy draft circulated for approval
2. SYSTEM CHANGE (by Jun 20): Mobile banking backend updated and tested
3. BOARD REPORTING (Jul 5): Compliance confirmation submitted to RBI via DAKSH portal""",

        "RBI-CIR-2024-003": """**EXECUTIVE SUMMARY**
This circular mandates a 15-day KFS pre-disbursement window, directly conflicting with the bank's current same-day/3-day practice (POL-LEN-002). Impacts loan origination processes across all retail lending channels.

**GAP FINDINGS**
Gap 1:
- Internal Policy : POL-LEN-002 — Section 7.8 — Key Facts Statement (KFS) for Retail Loans
- RBI Requirement : "KFS must be provided at least 15 DAYS before disbursement; written consent 72 hours before"
- Current Status  : KFS provided on the day of loan execution; 3-day review period; same-day signature
- Gap Description : Review period is 5x shorter than mandated; consent timeline does not meet 72-hour requirement; regional language requirement not implemented
- Risk Level      : HIGH

**MANDATORY ACTION PLAN**
Action 1:
- Owner           : Head of Retail Lending + IT (Loan Origination System)
- Policy to Update: POL-LEN-002 — Section 7.8
- Specific Change : Update "3 days" to "15 days" and add 72-hour written consent workflow; add regional language generation to LOS
- Deadline        : 2024-10-01
- Validation Step : Sample 50 loan files post-implementation to verify 15-day gap between KFS issuance and disbursement

**COMPLIANCE TIMELINE**
1. IMMEDIATE: Freeze all same-day KFS practices; issue interim operating instruction to branches
2. SYSTEM CHANGE: Loan Origination System (LOS) to enforce 15-day calendar block
3. BOARD REPORTING: Policy amendment presented to Board Credit Committee by August 2024""",

        "RBI-CIR-2024-004": """**EXECUTIVE SUMMARY**
RBI has reduced the critical incident reporting window from 6 hours to 2 hours, a 67% reduction. This requires immediate updates to the CIRP, BCP, and CISO escalation matrix. Failure to report within 2 hours risks regulatory penalty.

**GAP FINDINGS**
Gap 1:
- Internal Policy : POL-CYB-001 — Section 11.3 — Cyber Incident Reporting to RBI
- RBI Requirement : "Critical incidents reported to RBI within 2 HOURS of initial detection"
- Current Status  : Policy states 6 hours for critical incidents
- Gap Description : Response timeline is 3x slower than the new RBI mandate; CSITE 1.0 must be upgraded to CSITE 2.0
- Risk Level      : CRITICAL

**MANDATORY ACTION PLAN**
Action 1:
- Owner           : CISO + Head of IT Security
- Policy to Update: POL-CYB-001 — Section 11.3
- Specific Change : Change "6 hours" to "2 hours" for critical incidents; add new categories (major: 6hrs, significant: 24hrs)
- Deadline        : 2024-09-01
- Validation Step : Tabletop exercise simulating a critical incident to test 2-hour reporting capability

**COMPLIANCE TIMELINE**
1. IMMEDIATE: CISO issues emergency operating procedure with 2-hour target
2. SYSTEM CHANGE: CSITE 2.0 portal access provisioned; automated alerting configured
3. BOARD REPORTING: Updated CIRP presented to Board Risk Committee by August 2024""",
    }
    return gaps.get(cid, """**EXECUTIVE SUMMARY**
Analysis complete. The retrieved internal policies have been cross-referenced with this circular.

**GAP FINDINGS**
Gap 1:
- The circular introduces updated requirements that need review against current internal policies.
- Risk Level: MEDIUM

**MANDATORY ACTION PLAN**
Action 1:
- Owner: Compliance Team
- Specific Change: Review and update relevant internal policies to align with new circular requirements
- Deadline: Per circular compliance deadline

**COMPLIANCE TIMELINE**
1. IMMEDIATE: Compliance team review
2. SYSTEM CHANGE: Policy updates as required
3. BOARD REPORTING: Updates to Risk Committee""")


def call_mock_chat(question: str, context: str) -> str:
    """Mock Q&A responses for common policy questions."""
    q = question.lower()
    if "cooling" in q or "upi" in q and "wait" in q:
        return ("Per POL-DIG-001 (Section 3.1), the current internal policy mandates a 12-hour "
                "cooling period for newly added UPI beneficiaries. **Note: RBI circular "
                "RBI/2024-25/47 mandates this be updated to 24 hours by July 1, 2024.** "
                "Please check with your compliance team for the latest operative policy.")
    if "kyc" in q or "re-verify" in q or "re-kyc" in q:
        return ("Per POL-KYC-001 (Section 5.1), Video KYC customers must undergo re-verification "
                "every 36 months. Non-completion triggers Restricted Operations mode (inward credits only). "
                "Senior citizens (age 70+) can use a single document at branch without the video requirement.")
    if "kfs" in q or "key facts" in q or "loan document" in q:
        return ("Per POL-LEN-002 (Section 7.8), the KFS is currently provided on the day of loan execution "
                "with a 3-day review window. **Important: RBI circular RBI/2024-25/29 mandates this change "
                "to 15 days before disbursement, effective October 1, 2024.** Coordinate with your Lending Head.")
    if "cyber" in q or "incident" in q or "breach" in q or "hack" in q:
        return ("Per POL-CYB-001 (Section 11.3), critical cyber incidents must currently be reported to "
                "RBI within 6 hours via the CSITE portal. **Alert: RBI/2024-25/61 reduces this to 2 hours "
                "effective September 1, 2024.** Full RCA must still be submitted within 21 days.")
    if "lcr" in q or "liquidity" in q:
        return ("Per POL-LIQ-001 (Section 14.1), the bank maintains a minimum LCR of 100% per Basel III. "
                "**Note: RBI/2024-25/71 raises this to 105% by October 2024 and 110% by January 2025.** "
                "ALCO should be briefed on the phased transition immediately.")
    if "complaint" in q or "grievance" in q or "resolve" in q:
        return ("Per POL-GRV-001 (Section 9.1): Complaints acknowledged within 24 hours. Unauthorised "
                "transactions resolved within 7 working days. General complaints within 15 working days. "
                "Escalation to Banking Ombudsman per RBI Integrated Ombudsman Scheme 2021.")
    return (f"Based on the bank's policy framework, your query about '{question[:60]}' relates to "
            "our internal policy documentation. Please consult the relevant section in the Master Policy "
            "Manual or contact the Compliance Help Desk (ext. 4422) for authoritative guidance.")


def build_gap_prompt(circular: dict, matched_policies: list) -> str:
    policy_block = ""
    for p, score in matched_policies:
        policy_block += f"\n[{p['policy_id']} | {p['section']} | Score: {score:.4f}]\n{p['text']}\n"
    return f"""You are a Senior Compliance Officer at an Indian Scheduled Commercial Bank.
Perform a REGULATORY GAP ANALYSIS between this RBI Circular and internal bank policies.

RBI CIRCULAR
Reference : {circular['circular_ref']}
Subject   : {circular['subject']}
Deadline  : {circular['compliance_deadline']}
Text      : {circular['text']}

MATCHED INTERNAL POLICIES
{policy_block}

Respond with:
**EXECUTIVE SUMMARY** (2-3 sentences)

**GAP FINDINGS** — for each conflict:
- Internal Policy / RBI Requirement / Current Status / Gap Description / Risk Level [CRITICAL/HIGH/MEDIUM/LOW]

**MANDATORY ACTION PLAN** — ordered by risk:
- Owner / Policy to Update / Specific Change (exact wording) / Deadline / Validation Step

**COMPLIANCE TIMELINE** (3 steps: immediate → system change → board reporting)

Be precise. Cite specific numbers and timelines. Do not hedge."""


def build_chat_prompt(question: str, policy_context: str, language: str = "English") -> str:
    lang_instruction = ""
    if language == "Hindi":
        lang_instruction = "\n\nIMPORTANT: Provide your response in Hindi (Devanagari script). Start with the Hindi response, then provide an English summary below it."
    elif language == "Marathi":
        lang_instruction = "\n\nIMPORTANT: Provide your response in Marathi (Devanagari script). Start with the Marathi response, then provide an English summary below it."
    
    return f"""You are a Bank Compliance Assistant helping employees understand internal policies and RBI regulations.

RELEVANT POLICY CONTEXT:
{policy_context}

EMPLOYEE QUESTION: {question}

Provide a clear, accurate answer citing the specific policy section. Flag any recent RBI changes that affect this policy.{lang_instruction}"""

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    provider = st.selectbox(
        "LLM Provider",
        ["Mock (No Key Needed)", "Groq (Free — Recommended)", "Gemini"],
        help="Get a free Groq key at console.groq.com in 60 seconds",
    )
    
    api_key = ""
    if provider != "Mock (No Key Needed)":
        api_key = st.text_input(
            "API Key", type="password",
            placeholder="gsk_... (Groq) or AIza... (Gemini)"
        )
    
    st.markdown("---")
    st.markdown("### 📊 System Status")
    
    n_policies = len(INTERNAL_POLICIES)
    n_circulars = len(RBI_CIRCULARS)
    n_gaps = 4  # known conflicts seeded in data
    
    col1, col2 = st.columns(2)
    col1.metric("Policies", n_policies)
    col2.metric("Circulars", n_circulars)
    st.metric("Open Gaps", n_gaps, delta="Need attention", delta_color="inverse")
    
    st.markdown("---")
    st.markdown("### 📋 Known Gap Matrix")
    gap_matrix = {
        "UPI Cooling Period": ("POL-DIG-001", "12hr→24hr", "🔴 CRITICAL"),
        "KFS Review Window": ("POL-LEN-002", "3d→15d", "🟠 HIGH"),
        "Cyber Reporting": ("POL-CYB-001", "6hr→2hr", "🔴 CRITICAL"),
        "LCR Minimum": ("POL-LIQ-001", "100%→110%", "🟠 HIGH"),
    }
    for gap, (pol, change, risk) in gap_matrix.items():
        st.caption(f"{risk} **{gap}**  \n`{pol}` — {change}")
    
    st.markdown("---")
    st.caption("🔒 Data stays within your environment. LLM API calls are stateless.")

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="app-header">
    <div>
        <h1>🏦 AI Financial Regulatory Advisor</h1>
        <div class="subtitle">Powered by Databricks Medallion Architecture · TF-IDF Retrieval · LLM Gap Analysis</div>
    </div>
    <div>
        <span class="rbi-badge">4 Open Gaps</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────

tab_gap, tab_chat = st.tabs(["🔍  Gap Analysis Engine", "💬  Chat & Translate"])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — GAP ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════

with tab_gap:
    st.markdown('<div class="section-title">Select RBI Circular for Analysis</div>', unsafe_allow_html=True)
    
    col_left, col_right = st.columns([1, 1], gap="large")
    
    with col_left:
        circular_options = {
            f"{c['circular_id']} — {c['subject'][:55]}...": cid
            for cid, c in RBI_CIRCULARS.items()
        }
        
        selected_label = st.selectbox(
            "Choose a circular or paste custom text below:",
            list(circular_options.keys()),
            label_visibility="collapsed",
        )
        selected_cid = circular_options[selected_label]
        circular = RBI_CIRCULARS[selected_cid]
        
        # Show circular details
        with st.expander(f"📄 {circular['circular_ref']}", expanded=True):
            st.markdown(f"**Subject:** {circular['subject']}")
            col_a, col_b = st.columns(2)
            col_a.markdown(f"**Issued:** {circular['issued_date']}")
            col_b.markdown(f"**Deadline:** `{circular['compliance_deadline']}`")
            st.markdown("**Directive Text:**")
            st.markdown(f"> {circular['text'][:400]}...")
        
        # Custom circular input
        custom_text = st.text_area(
            "Or paste a custom RBI circular text:",
            height=120,
            placeholder="Paste any new RBI circular text here to analyse it against internal policies...",
        )
        
        run_btn = st.button("🔍 Run Gap Analysis", type="primary", use_container_width=True)
    
    with col_right:
        st.markdown('<div class="section-title">Top Matched Internal Policies</div>', unsafe_allow_html=True)
        
        # Show retrieval results
        policy_index = get_policy_index()
        query_text   = custom_text if custom_text.strip() else circular["text"]
        matches      = retrieve_policies(query_text, policy_index, top_k=5)
        
        for p, score in matches:
            bar_pct = int(score * 100 / max(matches[0][1], 0.001))
            risk_indicator = "🔴" if score > 0.3 else "🟡" if score > 0.1 else "⚪"
            st.markdown(f"""
            <div class="gap-card">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-weight:600;font-size:0.88rem">{risk_indicator} {p['policy_id']} — {p['section']}</span>
                    <span style="font-size:0.75rem;color:#64748B">Score: {score:.4f}</span>
                </div>
                <div style="font-size:0.8rem;color:#475569;margin:4px 0 8px">{p['title']}</div>
                <div style="background:#E2E8F0;height:4px;border-radius:2px">
                    <div style="background:#0A2540;height:4px;border-radius:2px;width:{bar_pct}%"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Gap Analysis Results ──────────────────────────────────────────────────
    if run_btn:
        with st.spinner("🔍 Retrieving matched policies and running LLM gap analysis..."):
            t_start = time.time()
            
            matched_for_prompt = [(p, sc) for p, sc in matches[:4]]
            
            try:
                if "Mock" in provider:
                    result = call_mock_gap(circular, matched_for_prompt)
                elif "Groq" in provider:
                    if not api_key:
                        st.warning("⚠️ No API key provided. Using mock response. Add your Groq key in the sidebar.")
                        result = call_mock_gap(circular, matched_for_prompt)
                    else:
                        prompt = build_gap_prompt(circular, matched_for_prompt)
                        result = call_groq(prompt, api_key)
                else:  # Gemini
                    prompt = build_gap_prompt(circular, matched_for_prompt)
                    result = call_gemini(prompt, api_key)
                
                latency = round(time.time() - t_start, 2)
                
            except Exception as e:
                st.error(f"LLM call failed: {e}. Using mock response.")
                result = call_mock_gap(circular, matched_for_prompt)
                latency = round(time.time() - t_start, 2)
        
        st.markdown("---")
        
        # Metrics row
        st.markdown(f"""
        <div class="metric-row">
            <div class="metric-card"><div class="label">Policies Scanned</div><div class="value">{len(INTERNAL_POLICIES)}</div></div>
            <div class="metric-card"><div class="label">Matches Retrieved</div><div class="value">{len(matches)}</div></div>
            <div class="metric-card"><div class="label">Analysis Time</div><div class="value">{latency}s</div></div>
            <div class="metric-card"><div class="label">LLM Provider</div><div class="value" style="font-size:1rem">{provider.split(' ')[0]}</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="section-title">Gap Analysis Report</div>', unsafe_allow_html=True)
        
        # Render with risk-level colour coding
        sections = result.split("\n\n")
        for section in sections:
            if "CRITICAL" in section.upper() and "Gap" in section:
                st.markdown(f'<div class="gap-card critical">{section.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
            elif "HIGH" in section.upper() and "Gap" in section:
                st.markdown(f'<div class="gap-card high">{section.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
            else:
                if section.strip():
                    st.markdown(section)
        
        # Export
        st.download_button(
            "⬇️ Download Full Gap Report",
            data=f"GAP ANALYSIS REPORT\n{'='*60}\nCircular: {circular['circular_ref']}\n\n{result}",
            file_name=f"gap_analysis_{circular['circular_id']}_{time.strftime('%Y%m%d')}.txt",
            mime="text/plain",
        )

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — CHAT & TRANSLATE
# ═════════════════════════════════════════════════════════════════════════════

with tab_chat:
    col_chat, col_config = st.columns([2, 1], gap="large")
    
    with col_config:
        st.markdown('<div class="section-title">Settings</div>', unsafe_allow_html=True)
        
        language = st.selectbox(
            "Response Language",
            ["English", "Hindi", "Marathi"],
            help="Select the language for the assistant's response. Powered by the LLM's multilingual capability."
        )
        
        domain_filter = st.multiselect(
            "Focus Domains",
            ["Digital_Payments", "KYC_AML", "Lending", "Customer_Grievance", "Cybersecurity", "Liquidity_Treasury"],
            default=[],
            help="Optionally filter context to specific policy domains",
        )
        
        st.markdown("---")
        st.markdown('<div class="section-title">Suggested Questions</div>', unsafe_allow_html=True)
        
        suggestions = [
            "What is the UPI cooling period for new beneficiaries?",
            "How long does a customer have to review the KFS before loan disbursement?",
            "What are our cyber incident reporting timelines?",
            "How are High Risk customers reviewed under AML policy?",
            "What is the minimum LCR we must maintain?",
        ]
        
        for q in suggestions:
            if st.button(q, key=f"sug_{q[:20]}", use_container_width=True):
                st.session_state["chat_prefill"] = q
    
    with col_chat:
        st.markdown('<div class="section-title">Policy Q&A Assistant</div>', unsafe_allow_html=True)
        
        # Initialise chat history
        if "messages" not in st.session_state:
            st.session_state["messages"] = [
                {
                    "role": "assistant",
                    "content": (
                        "Hello! I'm your AI Compliance Assistant. I can answer questions about "
                        "the bank's internal policies and highlight any recent RBI circular updates "
                        "that affect them. Ask me anything — and I can respond in **English, Hindi, or Marathi**."
                    ),
                    "lang": "English",
                }
            ]
        
        # Render chat history
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state["messages"]:
                if msg["role"] == "user":
                    st.markdown(
                        f'<div style="display:flex;justify-content:flex-end;margin-bottom:4px">'
                        f'<div class="chat-bubble chat-user">{msg["content"]}</div></div>',
                        unsafe_allow_html=True
                    )
                else:
                    lang_tag = f' <span style="font-size:0.7rem;opacity:0.6">[{msg.get("lang","EN")}]</span>' if msg.get("lang") != "English" else ""
                    st.markdown(
                        f'<div style="display:flex;justify-content:flex-start;margin-bottom:4px">'
                        f'<div class="chat-bubble chat-bot">{msg["content"]}{lang_tag}</div></div>',
                        unsafe_allow_html=True
                    )
        
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        
        # Input area
        prefill = st.session_state.pop("chat_prefill", "")
        user_input = st.text_input(
            "Ask a compliance question:",
            value=prefill,
            placeholder="e.g. What is the KYC re-verification frequency for V-CIP customers?",
            label_visibility="collapsed",
            key="chat_input",
        )
        
        col_send, col_clear = st.columns([3, 1])
        send_btn  = col_send.button("Send ↗", type="primary", use_container_width=True)
        clear_btn = col_clear.button("Clear", use_container_width=True)
        
        if clear_btn:
            st.session_state["messages"] = st.session_state["messages"][:1]
            st.rerun()
        
        if send_btn and user_input.strip():
            # Add user message
            st.session_state["messages"].append({"role": "user", "content": user_input, "lang": language})
            
            with st.spinner("Searching policies and generating response..."):
                # Retrieve relevant context
                query_for_retrieval = user_input
                if domain_filter:
                    filtered = {pid: p for pid, p in INTERNAL_POLICIES.items() if p["domain"] in domain_filter}
                    idx = build_tfidf_index({pid: p["text"] for pid, p in filtered.items()})
                    ctxt_matches = [(filtered[pid], sc) for pid, sc in
                                    sorted([(pid, cosine_sim(
                                        {t:1.0 for t in tokenize(user_input)}, vec
                                    )) for pid, vec in idx.items()], key=lambda x: x[1], reverse=True)[:3]
                                    if pid in filtered]
                else:
                    ctxt_matches = retrieve_policies(query_for_retrieval, policy_index, top_k=3)
                
                context = "\n".join([f"[{p['policy_id']} | {p['section']}] {p['text']}" for p, _ in ctxt_matches])
                
                try:
                    if "Mock" in provider:
                        response = call_mock_chat(user_input, context)
                        if language == "Hindi":
                            response = f"**[हिंदी अनुवाद — Demo Mode]**\nकृपया ध्यान दें: पूर्ण हिंदी अनुवाद के लिए कृपया Groq या Gemini API कनेक्ट करें।\n\n**English:** " + response
                        elif language == "Marathi":
                            response = f"**[मराठी भाषांतर — Demo Mode]**\nपूर्ण मराठी भाषांतरासाठी कृपया Groq किंवा Gemini API जोडा.\n\n**English:** " + response
                    elif "Groq" in provider and api_key:
                        prompt = build_chat_prompt(user_input, context, language)
                        response = call_groq(prompt, api_key)
                    elif "Gemini" in provider and api_key:
                        prompt = build_chat_prompt(user_input, context, language)
                        response = call_gemini(prompt, api_key)
                    else:
                        response = call_mock_chat(user_input, context)
                        
                except Exception as e:
                    response = f"⚠️ LLM error: {e}. " + call_mock_chat(user_input, context)
            
            st.session_state["messages"].append({"role": "assistant", "content": response, "lang": language})
            st.rerun()
        
        # Sources panel
        if len(st.session_state["messages"]) > 1:
            with st.expander("📚 Policy Sources Used (Last Query)", expanded=False):
                if user_input or send_btn:
                    for p, sc in ctxt_matches if 'ctxt_matches' in dir() else []:
                        st.markdown(
                            f"**{p['policy_id']}** — {p['section']} — *{p['title']}*  \n"
                            f"Relevance: `{sc:.4f}` | Domain: `{p['domain']}` | Last Reviewed: {p['last_reviewed']}"
                        )

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "🏦 AI Financial Regulatory Advisor · Built on Databricks Medallion Architecture (Bronze→Silver→Gold) · "
    "TF-IDF Retrieval · Groq llama-3.3-70b / Gemini 1.5 Flash · Hackathon Demo"
)
