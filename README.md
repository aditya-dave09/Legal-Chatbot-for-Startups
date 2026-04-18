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
2. **Install dependencies:**
   '''bash
pip install -r requirements.txt

Launch the application:

Bash
streamlit run app.py
☁️ Databricks Deployment
The files in the backend_databricks folder are designed to be run sequentially on a Databricks cluster to generate the underlying Medallion tables in a default or secure catalog database.


*(Note: Don't forget to change `YOUR_USERNAME` in the clone link to your actual GitHub username once you create the repo!)*

---

### 🚀 Step 4: Push to GitHub

1. Go to [GitHub.com](https://github.com/) and click the **+** icon in the top right to create a **New Repository**.
2. Name it `FinReg-AI-Advisor`. **Do not** check the boxes to add a README or .gitignore (you already made them). Click **Create repository**.
3. Open your computer's Terminal (or Command Prompt) and navigate to your master folder:
   ```bash
   cd Desktop/FinReg-AI-Advisor
Run these exact commands one by one to push your code:

Bash
git init
git add .
git commit -m "Initial commit: Databricks backend and Streamlit frontend"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/FinReg-AI-Advisor.git
git push -u origin main
