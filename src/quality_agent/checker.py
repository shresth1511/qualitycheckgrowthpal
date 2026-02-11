from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AgentConfig


@dataclass
class CompanyQualityResult:
    company_id: str
    completeness_score: float
    consistency_score: float
    accuracy_score: float
    quality_score: float
    flags: list[str]


class QualityChecker:
    def __init__(self, config: AgentConfig) -> None:
        self.cfg = config

    def run(
        self,
        es_records: dict[str, dict[str, Any]],
        s3_records: dict[str, dict[str, Any]],
        milvus_records: dict[str, dict[str, Any]],
    ) -> tuple[list[CompanyQualityResult], dict[str, Any]]:
        all_company_ids = set(es_records) | set(s3_records) | set(milvus_records)
        results: list[CompanyQualityResult] = []

        for company_id in sorted(all_company_ids):
            es = es_records.get(company_id, {})
            s3 = s3_records.get(company_id, {})
            milvus = milvus_records.get(company_id, {})

            completeness, missing_fields = self._completeness(es)
            consistency, mismatch_fields = self._consistency(es, s3, milvus)
            accuracy = self._accuracy(es, s3, milvus)

            flags = []
            if company_id not in es_records or company_id not in s3_records or company_id not in milvus_records:
                flags.append("missing_in_one_or_more_sources")
            if missing_fields:
                flags.append(f"empty_required_fields:{','.join(missing_fields)}")
            if mismatch_fields:
                flags.append(f"cross_source_mismatch:{','.join(mismatch_fields)}")

            weighted = (
                completeness * self.cfg.weights.completeness
                + consistency * self.cfg.weights.consistency
                + accuracy * self.cfg.weights.accuracy
            )

            results.append(
                CompanyQualityResult(
                    company_id=company_id,
                    completeness_score=round(completeness, 4),
                    consistency_score=round(consistency, 4),
                    accuracy_score=round(accuracy, 4),
                    quality_score=round(weighted, 4),
                    flags=flags,
                )
            )

        summary = self._summary(results, es_records, s3_records, milvus_records)
        self._write_outputs(results, summary)
        return results, summary

    def _completeness(self, es: dict[str, Any]) -> tuple[float, list[str]]:
        missing = [field for field in self.cfg.required_fields if self._get_nested(es, field) in (None, "", [], {})]
        total = max(1, len(self.cfg.required_fields))
        score = 1 - (len(missing) / total)
        return score, missing

    def _consistency(self, es: dict[str, Any], s3: dict[str, Any], milvus: dict[str, Any]) -> tuple[float, list[str]]:
        mismatches: list[str] = []
        for field in self.cfg.key_fields:
            values = [
                self._normalize(self._get_nested(es, field)),
                self._normalize(self._get_nested(s3, field)),
                self._normalize(self._get_nested(milvus, field)),
            ]
            populated = [v for v in values if v is not None]
            if len(set(populated)) > 1:
                mismatches.append(field)

        total = max(1, len(self.cfg.key_fields))
        score = 1 - (len(mismatches) / total)
        return score, mismatches

    def _accuracy(self, es: dict[str, Any], s3: dict[str, Any], milvus: dict[str, Any]) -> float:
        if not es:
            return 0.0

        total = 0
        matched = 0
        for field in self.cfg.key_fields:
            es_val = self._normalize(self._get_nested(es, field))
            candidates = [
                self._normalize(self._get_nested(s3, field)),
                self._normalize(self._get_nested(milvus, field)),
            ]
            candidates = [x for x in candidates if x is not None]
            if es_val is None or not candidates:
                continue
            total += 1
            if es_val in candidates:
                matched += 1

        return (matched / total) if total else 0.0

    def _summary(
        self,
        results: list[CompanyQualityResult],
        es_records: dict[str, dict[str, Any]],
        s3_records: dict[str, dict[str, Any]],
        milvus_records: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        flag_counts = defaultdict(int)
        for row in results:
            for flag in row.flags:
                flag_counts[flag.split(":")[0]] += 1

        duplicates = self._find_identity_duplicates(es_records)
        return {
            "counts": {
                "elasticsearch": len(es_records),
                "s3": len(s3_records),
                "milvus": len(milvus_records),
                "union": len(set(es_records) | set(s3_records) | set(milvus_records)),
            },
            "avg_quality_score": round(sum(r.quality_score for r in results) / max(1, len(results)), 4),
            "flag_counts": dict(flag_counts),
            "duplicate_identity_groups": duplicates,
        }

    def _find_identity_duplicates(self, es_records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
        for company_id, rec in es_records.items():
            key = tuple(self._normalize(self._get_nested(rec, fld)) for fld in self.cfg.identity_group_fields)
            if any(v is not None for v in key):
                groups[key].append(company_id)

        output = []
        for key, ids in groups.items():
            if len(set(ids)) > 1:
                output.append({"identity_fields": self.cfg.identity_group_fields, "identity_values": key, "company_ids": sorted(set(ids))})
        return output

    def _write_outputs(self, results: list[CompanyQualityResult], summary: dict[str, Any]) -> None:
        out_dir = Path(self.cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        csv_path = out_dir / "company_quality_scores.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "company_id",
                    "completeness_score",
                    "consistency_score",
                    "accuracy_score",
                    "quality_score",
                    "flags",
                ]
            )
            for row in results:
                writer.writerow(
                    [
                        row.company_id,
                        row.completeness_score,
                        row.consistency_score,
                        row.accuracy_score,
                        row.quality_score,
                        ";".join(row.flags),
                    ]
                )

        summary_path = out_dir / "quality_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    @staticmethod
    def _normalize(value: Any) -> Any:
        if value in (None, "", [], {}):
            return None
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @staticmethod
    def _get_nested(record: dict[str, Any], dotted: str) -> Any:
        current: Any = record
        for part in dotted.split("."):
            if not isinstance(current, dict):
                return None
            if part not in current:
                return None
            current = current.get(part)
        return current
