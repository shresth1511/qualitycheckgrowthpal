# Company Data Quality Agent (Elasticsearch + S3 + Milvus)

This repository contains an agent that audits company data quality across Elasticsearch, S3, and Milvus.

## What it checks

1. **Record coverage**
   - Number of companies present in each source.
   - Missing companies by source.
2. **Completeness (empty field detection)**
   - Checks required fields in Elasticsearch.
   - Flags companies where important fields are empty.
3. **Cross-source consistency**
   - Compares values for the same company across Elasticsearch/S3/Milvus.
   - Flags mismatches in configurable key fields.
4. **Accuracy proxy**
   - Treats Elasticsearch as the target record and validates whether key values agree with S3/Milvus.
5. **Identity duplication checks**
   - Finds groups where identity keys (for example `linkedinKey + website`) map to multiple company IDs.

## Quality score model

Each company receives:

- `completeness_score` (0-1)
- `consistency_score` (0-1)
- `accuracy_score` (0-1)
- `quality_score` = weighted score (default: 40% completeness, 35% consistency, 25% accuracy)

The model weights are configurable in `config.example.yaml`.

## Where to put Elasticsearch, S3, and Milvus credentials

Use **environment variables** and reference them from `config.yaml` (same pattern as `config.example.yaml`).

1. Copy and edit config:

```bash
cp config.example.yaml config.yaml
```

2. Export credentials and connection links in your shell (or CI/CD secrets):

```bash
export ELASTIC_HOST="https://your-elastic-host:9200"
export ELASTIC_USERNAME="elastic"
export ELASTIC_PASSWORD="your-password"

export AWS_REGION="us-east-1"
export S3_BUCKET="company-master-data"
export S3_KEY="exports/companies.jsonl"

export MILVUS_URI="http://milvus-host:19530"
export MILVUS_TOKEN=""
export MILVUS_COLLECTION="company_embeddings"
```

3. Run the agent; placeholders like `${ELASTIC_HOST}` are auto-resolved from env variables.

> Do not commit real credentials in `config.yaml`.


## Read-only guarantee

The agent is intentionally **read-only** against Elasticsearch, S3, and Milvus:

- Elasticsearch: `search`, `scroll`, `clear_scroll` only
- S3: `get_object` only
- Milvus: `load` and `query` only

No insert/update/delete/upsert/bulk operations are implemented in this codebase.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run

```bash
python -m quality_agent.cli --config config.yaml
```

## Output artifacts

Generated in `output/`:

- `company_quality_scores.csv` (one line per company + flags)
- `quality_summary.json` (source counts, average quality, flag totals, duplicate identity groups)

## Recommended Kibana checks for your task

Use these while validating the pipeline:

1. **Total companies by source**
   - ES: `value_count(companyId)`
   - S3/Milvus: run equivalent count queries and compare.
2. **Empty critical fields**
   - Build terms/missing aggregations for:
     - `linkedinKey`, `city`, `country`, `empCount`, `websiteStatus.isActive`
3. **Duplicate identity groups**
   - Composite aggregation on `linkedinKey` and `website`; flag buckets with `cardinality(companyId) > 1`.
4. **DWH/parent mapping check**
   - Validate `dwhId == parent.id` (if field available in all stores).
5. **Consumption test checks**
   - Confirm flagged companies are consumed in downstream BE service before deletion.

## Notes

- Adjust key fields to exactly match your schema in all three systems.
- If Milvus contains only vectors and metadata subset, evaluate consistency only on available fields.
- For production, schedule this as a daily job and push output to BI/Slack.
