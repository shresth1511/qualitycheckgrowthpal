from __future__ import annotations

import csv
import io
import json
from typing import Any

import boto3
from elasticsearch import Elasticsearch
from pymilvus import Collection, connections

from .config import ElasticsearchConfig, MilvusConfig, S3Config


class ElasticsearchConnector:
    def __init__(self, cfg: ElasticsearchConfig) -> None:
        self.client = Elasticsearch(
            hosts=[cfg.host],
            basic_auth=(cfg.username, cfg.password) if cfg.username and cfg.password else None,
            verify_certs=cfg.verify_certs,
        )
        self.cfg = cfg

    def fetch_records(self) -> dict[str, dict[str, Any]]:
        body = {
            "size": self.cfg.page_size,
            "query": {"match_all": {}},
            "_source": self.cfg.fields,
        }
        response = self.client.search(index=self.cfg.index, body=body, scroll="2m")
        scroll_id = response.get("_scroll_id")
        hits = response["hits"]["hits"]
        out: dict[str, dict[str, Any]] = {}

        while hits:
            for h in hits:
                src = h.get("_source", {})
                company_id = str(src.get("companyId", "")).strip()
                if company_id:
                    out[company_id] = src
            response = self.client.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = response.get("_scroll_id")
            hits = response["hits"]["hits"]

        if scroll_id:
            self.client.clear_scroll(scroll_id=scroll_id)

        return out


class S3Connector:
    def __init__(self, cfg: S3Config) -> None:
        self.client = boto3.client("s3", region_name=cfg.region)
        self.cfg = cfg

    def _read_bytes(self) -> bytes:
        response = self.client.get_object(Bucket=self.cfg.bucket, Key=self.cfg.key)
        return response["Body"].read()

    def fetch_records(self) -> dict[str, dict[str, Any]]:
        payload = self._read_bytes()
        key = self.cfg.key.lower()
        if key.endswith(".json") or key.endswith(".jsonl"):
            return self._parse_jsonish(payload)
        if key.endswith(".csv"):
            return self._parse_csv(payload)
        raise ValueError(f"Unsupported S3 key format: {self.cfg.key}")

    def _parse_jsonish(self, payload: bytes) -> dict[str, dict[str, Any]]:
        text = payload.decode("utf-8")
        if "\n" in text.strip() and text.strip().splitlines()[0].strip().startswith("{"):
            docs = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            loaded = json.loads(text)
            docs = loaded if isinstance(loaded, list) else [loaded]

        out: dict[str, dict[str, Any]] = {}
        for doc in docs:
            company_id = str(doc.get("companyId", "")).strip()
            if company_id:
                out[company_id] = doc
        return out

    def _parse_csv(self, payload: bytes) -> dict[str, dict[str, Any]]:
        text = payload.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        out: dict[str, dict[str, Any]] = {}
        for row in reader:
            company_id = str(row.get("companyId", "")).strip()
            if company_id:
                out[company_id] = row
        return out


class MilvusConnector:
    def __init__(self, cfg: MilvusConfig) -> None:
        connections.connect(uri=cfg.uri, token=cfg.token)
        self.collection = Collection(name=cfg.collection, consistency_level=cfg.consistency_level)
        self.cfg = cfg

    def fetch_records(self) -> dict[str, dict[str, Any]]:
        self.collection.load()
        out: dict[str, dict[str, Any]] = {}
        offset = 0
        batch_size = 16_384

        while True:
            results = self.collection.query(
                expr="companyId > 0",
                output_fields=self.cfg.output_fields,
                offset=offset,
                limit=batch_size,
            )
            if not results:
                break

            for rec in results:
                company_id = str(rec.get("companyId", "")).strip()
                if company_id:
                    out[company_id] = rec

            if len(results) < batch_size:
                break
            offset += batch_size

        return out
