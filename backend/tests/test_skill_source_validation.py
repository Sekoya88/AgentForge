from app.domain.skill_source_validation import validate_skill_source


def test_validate_empty_source() -> None:
    ok, msg = validate_skill_source("")
    assert ok is False
    assert "empty" in msg.lower()


def test_validate_syntax_error() -> None:
    ok, msg = validate_skill_source("def run(:")
    assert ok is False
    assert "syntax" in msg.lower()


def test_validate_missing_run() -> None:
    ok, msg = validate_skill_source("def other():\n    pass\n")
    assert ok is False
    assert "run" in msg.lower()


def test_validate_blocks_os_import() -> None:
    ok, msg = validate_skill_source("import os\ndef run(x: str) -> str:\n    return x\n")
    assert ok is False
    assert "not allowed" in msg.lower()


def test_validate_allows_json_and_run() -> None:
    src = "import json\n\ndef run(x: str) -> str:\n    return json.dumps({'ok': True})\n"
    ok, msg = validate_skill_source(src)
    assert ok is True
    assert "passes" in msg.lower() or "ok" in msg.lower()


def test_validate_blocks_dunder_import_call() -> None:
    src = "def run(x: str) -> str:\n    m = __import__('json')\n    return m.dumps({})\n"
    ok, msg = validate_skill_source(src)
    assert ok is False
    assert "__import__" in msg.lower() or "not allowed" in msg.lower()
