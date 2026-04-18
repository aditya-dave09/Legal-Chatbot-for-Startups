# Databricks notebook source
# MAGIC %md
# MAGIC # 🥈 02 | Processing → Silver Layer

import re
# 1. Imported 'concat' here properly!
from pyspark.sql.functions import udf, col, posexplode, lit, concat
from pyspark.sql.types import StringType, ArrayType

# Load from Managed Tables in DEFAULT database
policy_df = spark.table("default.bronze_policies")
rbi_df    = spark.table("default.bronze_rbi")

# 2. Removed Python type hints to stop the Databricks UserWarning
def clean_regulatory_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

clean_udf = udf(clean_regulatory_text, StringType())

def chunk_by_sentence_pair(text):
    if not text: return [""]
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    return sentences if sentences else [text]

chunk_udf = udf(chunk_by_sentence_pair, ArrayType(StringType()))

# Process Internal Policies
cleaned_policy = policy_df.withColumn("cleaned_text", clean_udf(col("policy_text")))
silver_policy = (
    cleaned_policy
    .withColumn("chunks", chunk_udf(col("cleaned_text")))
    .select(
        col("policy_id"), col("domain"), col("section"), col("title"),
        posexplode(col("chunks")).alias("chunk_index", "chunk_text")
    )
    # 3. Fixed the concat() bug! Now using the proper PySpark function format
    .withColumn("chunk_id", concat(col("policy_id").cast("string"), lit("_"), col("chunk_index").cast("string")))
    .withColumn("source_type", lit("internal_policy"))
)

display(silver_policy.select("policy_id","chunk_text"))

# Process RBI Circulars
cleaned_rbi = rbi_df.withColumn("cleaned_text", clean_udf(col("circular_text")))
silver_rbi = (
    cleaned_rbi
    .withColumn("chunks", chunk_udf(col("cleaned_text")))
    .select(
        col("circular_id"), col("circular_ref"), col("subject"), col("category"),
        posexplode(col("chunks")).alias("chunk_index", "chunk_text")
    )
    # 3. Fixed the concat() bug!
    .withColumn("chunk_id", concat(col("circular_id").cast("string"), lit("_"), col("chunk_index").cast("string")))
    .withColumn("source_type", lit("rbi_circular"))
)

display(silver_rbi.select("circular_id","chunk_text"))

# Save to Managed Tables in DEFAULT database
silver_policy.write.format("delta").mode("overwrite").saveAsTable("default.silver_policies")
silver_rbi.write.format("delta").mode("overwrite").saveAsTable("default.silver_rbi")

print("✅ Silver Layer Complete. Move to 03.")