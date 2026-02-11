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

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run

1. Copy and edit config:

```bash
cp config.example.yaml config.yaml
```

2. Execute agent:

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
