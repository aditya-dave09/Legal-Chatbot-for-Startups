# Legal-Chatbot-for-Startups
# 🏦 AI Financial Regulatory Advisor

> **An AI-powered compliance engine that automates Gap Analysis between internal bank policies and live RBI circulars.**

## 🚀 The Problem
When the Reserve Bank of India (RBI) issues new regulatory circulars, banks spend weeks manually cross-referencing these updates against thousands of internal policy documents. This delay risks massive compliance fines. 

## 💡 Our Solution
We built an automated pipeline that ingests regulatory text, processes it using a Medallion Architecture, and leverages LLMs to instantly identify compliance gaps and generate action plans.

## ⚙️ Architecture

### 1. The Data Engine (Databricks / PySpark)
* **Bronze Layer:** Ingests raw Internal Bank Policies (Stream A) and live RBI Circulars (Stream B).
* **Silver Layer:** Cleans text, normalizes currency, and chunks documents intelligently (sentence-pairs for policies, directive-blocks for circulars).
* **Gold Layer:** Utilizes PySpark MLlib (`RegexTokenizer`, `StopWordsRemover`, `HashingTF`, `IDF`) to convert English text into mathematical vectors for instant semantic search.

### 2. The AI Frontend (Streamlit + Llama 3)
* **Local Search:** Calculates Cosine Similarity between TF-IDF vectors to match conflicting documents.
* **LLM Gap Analysis:** Feeds the matched documents into an LLM (Groq API / Llama 3) to generate a plain-English compliance action plan.
* **Chatbot:** Allows compliance officers to query internal policies conversationally.

## 🛠️ How to Run Locally

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/FinReg-AI-Advisor.git](https://github.com/YOUR_USERNAME/FinReg-AI-Advisor.git)
   cd FinReg-AI-Advisor/frontend_app
