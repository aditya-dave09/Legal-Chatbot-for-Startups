# Databricks notebook source
# MAGIC %md
# MAGIC # 🥇 03 | Retrieval Engine → Gold Layer
# MAGIC This notebook converts our cleaned text chunks into TF-IDF vectors for semantic search.

from pyspark.ml.feature import RegexTokenizer, StopWordsRemover, HashingTF, IDF
from pyspark.ml import Pipeline

# Custom stopwords to filter out legal banking jargon so the AI focuses on the actual rules
BANKING_STOPWORDS = [
    "shall", "may", "herein", "thereof", "pursuant", "aforesaid", "said", 
    "such", "also", "further", "circular", "notification", "dated", "refer", 
    "para", "clause", "sub", "ibid", "viz", "etc", "bank", "banks", "rbi", 
    "reserve", "india", "effective", "following", "hereinafter", "thereto", 
    "provided", "however", "notwithstanding", "accordance", "respect"
]

def build_tfidf_pipeline(num_features: int = 8192) -> Pipeline:
    tokenizer = RegexTokenizer(inputCol="chunk_text", outputCol="tokens_raw", pattern="\\W", minTokenLength=3, toLowercase=True)
    remover = StopWordsRemover(inputCol="tokens_raw", outputCol="tokens", stopWords=StopWordsRemover.loadDefaultStopWords("english") + BANKING_STOPWORDS)
    hashing_tf = HashingTF(inputCol="tokens", outputCol="raw_features", numFeatures=num_features)
    idf = IDF(inputCol="raw_features", outputCol="tfidf_features", minDocFreq=1)
    
    return Pipeline(stages=[tokenizer, remover, hashing_tf, idf])

# 1. Load Silver Tables from the DEFAULT database
silver_policy = spark.table("default.silver_policies")
silver_rbi    = spark.table("default.silver_rbi")

print("🔧 Fitting TF-IDF Machine Learning pipelines...")
policy_model = build_tfidf_pipeline().fit(silver_policy)
rbi_model    = build_tfidf_pipeline().fit(silver_rbi)

# 2. Transform text into Gold Vectors
POLICY_COLS = ["chunk_id", "policy_id", "domain", "section", "title", "source_type", "chunk_text", "tfidf_features"]
RBI_COLS = ["chunk_id", "circular_id", "circular_ref", "subject", "category", "source_type", "chunk_text", "tfidf_features"]

gold_policy_df = policy_model.transform(silver_policy).select(*POLICY_COLS)
gold_rbi_df    = rbi_model.transform(silver_rbi).select(*RBI_COLS)

# Display the vectors for the judges to see!
print("\n🥇 Gold Layer: Internal Policy Vectors")
display(gold_policy_df.select("policy_id", "chunk_text", "tfidf_features"))

print("\n🥇 Gold Layer: RBI Circular Vectors")
display(gold_rbi_df.select("circular_id", "chunk_text", "tfidf_features"))

# 3. Save to Managed Tables in DEFAULT database
gold_policy_df.write.format("delta").mode("overwrite").saveAsTable("default.gold_policies")
gold_rbi_df.write.format("delta").mode("overwrite").saveAsTable("default.gold_rbi")

print("\n✅ Gold | Policy vectors securely saved to default.gold_policies")
print("✅ Gold | RBI vectors securely saved to default.gold_rbi")
print("🎉 BACKEND PIPELINE 100% COMPLETE!")