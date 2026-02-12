from quality_agent.checker import QualityChecker
from quality_agent.config import AgentConfig, ElasticsearchConfig, MilvusConfig, S3Config


def test_quality_scoring_and_flags():
    cfg = AgentConfig(
        elasticsearch=ElasticsearchConfig(host="http://localhost:9200", index="idx"),
        s3=S3Config(bucket="b", key="k.json"),
        milvus=MilvusConfig(uri="http://localhost:19530", token=None, collection="c"),
        required_fields=["companyId", "linkedinKey", "city"],
        key_fields=["linkedinKey", "city"],
        identity_group_fields=["linkedinKey"],
    )

    checker = QualityChecker(cfg)

    es = {
        "1": {"companyId": "1", "linkedinKey": "abc", "city": "SF"},
        "2": {"companyId": "2", "linkedinKey": "dup", "city": "NY"},
        "3": {"companyId": "3", "linkedinKey": "dup", "city": "LA"},
    }
    s3 = {
        "1": {"companyId": "1", "linkedinKey": "abc", "city": "SF"},
        "2": {"companyId": "2", "linkedinKey": "dup", "city": "Chicago"},
    }
    milvus = {
        "1": {"companyId": "1", "linkedinKey": "abc", "city": "SF"},
        "3": {"companyId": "3", "linkedinKey": "dup", "city": "LA"},
    }

    results, summary = checker.run(es, s3, milvus)

    assert len(results) == 3
    by_id = {r.company_id: r for r in results}
    assert by_id["1"].quality_score == 1.0
    assert any("missing_in_one_or_more_sources" in f for f in by_id["2"].flags)
    assert summary["counts"]["union"] == 3
    assert summary["duplicate_identity_groups"]
