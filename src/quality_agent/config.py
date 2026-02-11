from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any



DEFAULT_ES_FIELDS = [
    "companyId",
    "linkedinKey",
    "city",
    "country",
    "region",
    "state",
    "empCount",
    "predictedRevenueRange.min",
    "predictedRevenueRange.max",
    "isAcquired",
    "websiteStatus.isActive",
    "websiteStatus.scrapeStatus",
    "websiteStatus.statusCode",
    "children.isDuplicate",
    "parent.isDuplicate",
]


@dataclass
class ElasticsearchConfig:
    host: str
    index: str
    username: str | None = None
    password: str | None = None
    verify_certs: bool = True
    page_size: int = 2000
    fields: list[str] = field(default_factory=lambda: DEFAULT_ES_FIELDS.copy())


@dataclass
class S3Config:
    bucket: str
    key: str
    region: str | None = None


@dataclass
class MilvusConfig:
    uri: str
    token: str | None
    collection: str
    output_fields: list[str] = field(
        default_factory=lambda: [
            "companyId",
            "linkedinKey",
            "city",
            "country",
            "empCount",
            "isAcquired",
            "sourceUpdatedAt",
        ]
    )
    consistency_level: str = "Bounded"


@dataclass
class ScoreWeights:
    completeness: float = 0.4
    consistency: float = 0.35
    accuracy: float = 0.25


@dataclass
class AgentConfig:
    elasticsearch: ElasticsearchConfig
    s3: S3Config
    milvus: MilvusConfig
    output_dir: str = "output"
    primary_key: str = "companyId"
    key_fields: list[str] = field(
        default_factory=lambda: [
            "linkedinKey",
            "city",
            "country",
            "empCount",
            "isAcquired",
        ]
    )
    required_fields: list[str] = field(default_factory=lambda: DEFAULT_ES_FIELDS.copy())
    identity_group_fields: list[str] = field(default_factory=lambda: ["linkedinKey", "website"])
    weights: ScoreWeights = field(default_factory=ScoreWeights)



def _read_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)



def load_config(path: str) -> AgentConfig:
    data = _read_yaml(Path(path))
    return AgentConfig(
        elasticsearch=ElasticsearchConfig(**data["elasticsearch"]),
        s3=S3Config(**data["s3"]),
        milvus=MilvusConfig(**data["milvus"]),
        output_dir=data.get("output_dir", "output"),
        primary_key=data.get("primary_key", "companyId"),
        key_fields=data.get("key_fields", ["linkedinKey", "city", "country", "empCount", "isAcquired"]),
        required_fields=data.get("required_fields", DEFAULT_ES_FIELDS.copy()),
        identity_group_fields=data.get("identity_group_fields", ["linkedinKey", "website"]),
        weights=ScoreWeights(**data.get("weights", {})),
    )
