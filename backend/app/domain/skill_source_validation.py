"""Static checks for user-submitted skill Python source (no execution)."""

from __future__ import annotations

import ast
from typing import Final

# Third-party / stdlib modules we allow skills to import. Expand deliberately.
_ALLOWED_IMPORT_ROOTS: Final[frozenset[str]] = frozenset(
    {
        "__future__",
        "typing",
        "json",
        "re",
        "math",
        "decimal",
        "datetime",
        "collections",
        "itertools",
        "functools",
        "operator",
        "string",
        "enum",
        "uuid",
        "random",
        "hashlib",
        "base64",
        "html",
        "textwrap",
        "pprint",
        "statistics",
        "copy",
        "dataclasses",
    }
)

_FORBIDDEN_CALL_NAMES: Final[frozenset[str]] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "input",
        "breakpoint",
    }
)


def _import_root(module: str | None) -> str | None:
    if not module:
        return None
    return module.split(".", 1)[0]


def _check_imports(tree: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _import_root(alias.name)
                if root and root not in _ALLOWED_IMPORT_ROOTS:
                    return f"Import not allowed: {alias.name!r} (not on allowlist)"
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                return "Relative imports are not allowed in skills"
            root = _import_root(node.module)
            if root and root not in _ALLOWED_IMPORT_ROOTS:
                return f"Import not allowed: {node.module!r} (not on allowlist)"
    return None


def _check_dangerous_calls(tree: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_CALL_NAMES:
                return f"Call to {node.func.id!r} is not allowed"
    return None


def _has_top_level_run(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run":
            return True
    return False


def validate_skill_source(source_code: str) -> tuple[bool, str]:
    """
    Returns (valid, message). Does not execute code.
    """
    if not source_code or not source_code.strip():
        return False, "Skill source_code is empty"

    try:
        tree = ast.parse(source_code, mode="exec")
    except SyntaxError as e:
        return False, f"Syntax error: {e.msg} (line {e.lineno or '?'})"

    assert isinstance(tree, ast.Module)

    if not _has_top_level_run(tree):
        return False, "Skill must define a top-level function named `run`"

    if err := _check_imports(tree):
        return False, err

    if err := _check_dangerous_calls(tree):
        return False, err

    return True, "Source passes static validation (import allowlist, syntax, top-level run)"
