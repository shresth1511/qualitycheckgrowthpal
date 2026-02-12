from quality_agent.config import _resolve_env


def test_resolve_env_placeholders(monkeypatch):
    monkeypatch.setenv("ELASTIC_HOST", "https://elastic:9200")
    monkeypatch.setenv("ELASTIC_USERNAME", "user")

    data = {
        "elasticsearch": {
            "host": "${ELASTIC_HOST}",
            "username": "${ELASTIC_USERNAME}",
        },
        "list": ["${ELASTIC_HOST}", "fixed"],
    }

    resolved = _resolve_env(data)

    assert resolved["elasticsearch"]["host"] == "https://elastic:9200"
    assert resolved["elasticsearch"]["username"] == "user"
    assert resolved["list"] == ["https://elastic:9200", "fixed"]
