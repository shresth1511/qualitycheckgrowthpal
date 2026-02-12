from __future__ import annotations

import argparse
import json

from .checker import QualityChecker
from .config import load_config
from .connectors import ElasticsearchConnector, MilvusConnector, S3Connector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross-source company data quality agent")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    es_records = ElasticsearchConnector(cfg.elasticsearch).fetch_records()
    s3_records = S3Connector(cfg.s3).fetch_records()
    milvus_records = MilvusConnector(cfg.milvus).fetch_records()

    checker = QualityChecker(cfg)
    _, summary = checker.run(es_records, s3_records, milvus_records)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
