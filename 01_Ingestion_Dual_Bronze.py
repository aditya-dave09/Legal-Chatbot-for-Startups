# Databricks notebook source
# MAGIC %md
# MAGIC # 🏦 01 | Dual-Source Ingestion → Bronze Layer

from pyspark.sql import Row
from pyspark.sql.types import StructType, StructField, StringType
from datetime import datetime

print("✅ Using built-in 'default' database.")

NOW = datetime.utcnow().isoformat()

# ── Stream A: Internal Policies ──
INTERNAL_POLICY_SCHEMA = StructType([
    StructField("policy_id",        StringType(), True),
    StructField("domain",           StringType(), True),
    StructField("section",          StringType(), True),
    StructField("title",            StringType(), True),
    StructField("policy_text",      StringType(), True),
    StructField("effective_date",   StringType(), True),
    StructField("last_reviewed",    StringType(), True),
    StructField("status",           StringType(), True),
    StructField("ingested_at",      StringType(), True),
])

INTERNAL_POLICIES = [
    Row("POL-DIG-001", "Digital_Payments", "Section 3.1", "UPI Transaction Cooling Period", "New UPI beneficiaries added via mobile banking are subject to a mandatory cooling period of 12 hours before the first outward transaction can be processed. No outward UPI payments to newly added beneficiaries shall be permitted during this period. The branch manager may override for corporate accounts exceeding INR 10 crore turnover.", "2022-04-01", "2023-01-15", "ACTIVE", NOW),
    Row("POL-DIG-002", "Digital_Payments", "Section 3.2", "UPI Daily Transaction Limit", "Maximum daily aggregate UPI limit per customer is INR 1,00,000 across all handles. P2P UPI capped at INR 25,000 per transaction. Enhancement up to INR 2,00,000 requires Form UPI-LE with CIBIL score above 700.", "2022-04-01", "2023-06-01", "ACTIVE", NOW),
    Row("POL-LEN-002", "Lending", "Section 7.8", "Key Facts Statement (KFS) for Retail Loans", "KFS provided to borrowers at branch on the day of loan execution. Customers have 3 days to review before final disbursement. Follows IBA Model template 2019. Signature required same day.", "2021-06-01", "2023-08-15", "ACTIVE", NOW),
    Row("POL-CYB-001", "Cybersecurity", "Section 11.3", "Cyber Incident Reporting to RBI", "Critical cyber incidents must be reported to RBI within 6 hours of detection. Major incidents within 24 hours. All reports via CSITE portal. Full RCA within 21 days.", "2022-06-01", "2024-02-01", "ACTIVE", NOW),
]

policy_df = spark.createDataFrame(INTERNAL_POLICIES, schema=INTERNAL_POLICY_SCHEMA)
print(f"📋 Internal Policies created: {policy_df.count()}")
display(policy_df)

# ── Stream B: RBI Circulars ──
RBI_SCHEMA = StructType([
    StructField("circular_id",      StringType(), True),
    StructField("circular_ref",     StringType(), True),
    StructField("subject",          StringType(), True),
    StructField("issued_by",        StringType(), True),
    StructField("issued_date",      StringType(), True),
    StructField("effective_date",   StringType(), True),
    StructField("circular_text",    StringType(), True),
    StructField("category",         StringType(), True),
    StructField("compliance_deadline", StringType(), True),
    StructField("ingested_at",      StringType(), True),
])

RBI_CIRCULARS = [
    Row("RBI-CIR-2024-001", "RBI/2024-25/47", "Enhancement of Security Measures for UPI Transactions", "DPSS, RBI", "2024-04-15", "2024-07-01", "The minimum cooling period for any new beneficiary registered on a mobile banking application or internet banking portal shall be 24 HOURS. This supersedes any internal bank policy prescribing a shorter cooling period. No exceptions for corporate accounts or HNIs. Banks implementing a shorter cooling period (e.g., 12 hours) must update their systems and internal policies by June 30, 2024.", "Digital_Payments", "2024-07-01", NOW),
    Row("RBI-CIR-2024-003", "RBI/2024-25/29", "Key Facts Statement (KFS) for Loans", "DoR, RBI", "2024-03-22", "2024-10-01", "KFS must be provided to the borrower at least 15 DAYS before the date of loan disbursement. Written consent acknowledging receipt of KFS required at least 72 hours before disbursement. Existing policies prescribing any shorter review period (such as 3 days) must be amended.", "Lending", "2024-10-01", NOW),
]

rbi_df = spark.createDataFrame(RBI_CIRCULARS, schema=RBI_SCHEMA)
print(f"📡 RBI Circulars created: {rbi_df.count()}")
display(rbi_df)

# ── Save as Managed Tables in the DEFAULT database ──
policy_df.write.format("delta").mode("overwrite").saveAsTable("default.bronze_policies")
rbi_df.write.format("delta").mode("overwrite").saveAsTable("default.bronze_rbi")

print("✅ Bronze Layer Complete. Move to 02.")