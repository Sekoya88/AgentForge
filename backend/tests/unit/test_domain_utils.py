"""Unit tests for domain utilities: message_content, skill_source_validation."""

from __future__ import annotations

from app.domain.message_content import coerce_message_content_to_str
from app.domain.skill_source_validation import validate_skill_source

# ---------------------------------------------------------------------------
# coerce_message_content_to_str
# ---------------------------------------------------------------------------


class TestCoerceMessageContentToStr:
    def test_none_returns_empty(self):
        assert coerce_message_content_to_str(None) == ""

    def test_string_passthrough(self):
        assert coerce_message_content_to_str("hello") == "hello"

    def test_empty_string(self):
        assert coerce_message_content_to_str("") == ""

    def test_list_of_strings(self):
        assert coerce_message_content_to_str(["hello", " ", "world"]) == "hello world"

    def test_list_of_text_dicts(self):
        blocks = [{"text": "Hello"}, {"text": " world"}]
        assert coerce_message_content_to_str(blocks) == "Hello world"

    def test_list_with_content_key(self):
        blocks = [{"content": "fallback text"}]
        assert coerce_message_content_to_str(blocks) == "fallback text"

    def test_list_with_no_usable_key(self):
        blocks = [{"other": "ignored"}, {"text": "kept"}]
        result = coerce_message_content_to_str(blocks)
        assert "kept" in result

    def test_integer_coerced(self):
        assert coerce_message_content_to_str(42) == "42"

    def test_list_non_string_non_dict(self):
        result = coerce_message_content_to_str([99])
        assert result == "99"

    def test_empty_list(self):
        assert coerce_message_content_to_str([]) == ""


# ---------------------------------------------------------------------------
# validate_skill_source
# ---------------------------------------------------------------------------

VALID_SKILL = """
def run(input_text: str) -> str:
    return input_text.upper()
"""

VALID_SKILL_WITH_IMPORT = """
import json

def run(data: str) -> dict:
    return json.loads(data)
"""

VALID_ASYNC_SKILL = """
async def run(query: str) -> str:
    return "result: " + query
"""


class TestValidateSkillSource:
    def test_valid_simple_skill(self):
        ok, msg = validate_skill_source(VALID_SKILL)
        assert ok is True

    def test_valid_skill_with_allowed_import(self):
        ok, msg = validate_skill_source(VALID_SKILL_WITH_IMPORT)
        assert ok is True

    def test_valid_async_run(self):
        ok, msg = validate_skill_source(VALID_ASYNC_SKILL)
        assert ok is True

    def test_valid_httpx_import(self):
        code = "import httpx\ndef run(): return str(httpx)\n"
        ok, _ = validate_skill_source(code)
        assert ok is True

    def test_missing_run_function(self):
        code = "def compute(): pass\n"
        ok, msg = validate_skill_source(code)
        assert ok is False
        assert "run" in msg

    def test_empty_source(self):
        ok, msg = validate_skill_source("")
        assert ok is False
        assert "empty" in msg.lower()

    def test_whitespace_only(self):
        ok, msg = validate_skill_source("   \n\t\n")
        assert ok is False

    def test_syntax_error(self):
        bad_code = "def run(\n    pass\n"
        ok, msg = validate_skill_source(bad_code)
        assert ok is False
        assert "syntax" in msg.lower()

    def test_forbidden_os_import(self):
        code = "import os\ndef run(): return os.listdir('.')\n"
        ok, msg = validate_skill_source(code)
        assert ok is False
        assert "os" in msg

    def test_forbidden_subprocess(self):
        code = "import subprocess\ndef run(): pass\n"
        ok, _ = validate_skill_source(code)
        assert ok is False

    def test_relative_import_forbidden(self):
        code = "from . import utils\ndef run(): pass\n"
        ok, msg = validate_skill_source(code)
        assert ok is False
        assert "relative" in msg.lower()

    def test_forbidden_from_import(self):
        code = "from sys import argv\ndef run(): pass\n"
        ok, msg = validate_skill_source(code)
        assert ok is False
        assert "sys" in msg

    def test_eval_forbidden(self):
        code = "def run(x): return eval(x)\n"
        ok, msg = validate_skill_source(code)
        assert ok is False
        assert "eval" in msg

    def test_open_forbidden(self):
        code = "def run(): return open('/etc/passwd').read()\n"
        ok, msg = validate_skill_source(code)
        assert ok is False
        assert "open" in msg
