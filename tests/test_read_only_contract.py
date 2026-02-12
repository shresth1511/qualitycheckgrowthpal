import ast
from pathlib import Path


FORBIDDEN_METHODS = {
    # Elasticsearch writes
    "index",
    "update",
    "delete",
    "bulk",
    "update_by_query",
    "delete_by_query",
    # S3 writes
    "put_object",
    "delete_object",
    "copy_object",
    # Milvus writes
    "insert",
    "upsert",
    "delete",
    "flush",
}


def test_connectors_do_not_use_write_calls():
    source = Path("src/quality_agent/connectors.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    called_methods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called_methods.add(node.func.attr)

    assert FORBIDDEN_METHODS.isdisjoint(called_methods)
