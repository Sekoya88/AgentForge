#!/usr/bin/env python3
"""
Rebuild `.understand-anything/knowledge-graph.json` from intermediate/scan-result.json
when Understand-Anything file-analyzer batches did not complete (no batch-*.json).

Run from repo root:
  python3 scripts/ua_build_knowledge_graph.py
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / ".understand-anything/intermediate/scan-result.json"
OUT_GRAPH = ROOT / ".understand-anything/knowledge-graph.json"
OUT_META = ROOT / ".understand-anything/meta.json"


def git_hash() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def layer_for_path(rel: str) -> str:
    if rel.startswith("backend/app/api/"):
        return "layer-api"
    if rel.startswith("backend/app/domain/"):
        return "layer-domain"
    if rel.startswith("backend/app/application/"):
        return "layer-application"
    if rel.startswith("backend/app/infrastructure/"):
        return "layer-infrastructure"
    if rel.startswith("backend/tests/"):
        return "layer-tests"
    if rel.startswith("frontend/src/"):
        return "layer-frontend"
    if rel.startswith("backend/migrations/") or rel.startswith("backend/migrations"):
        return "layer-migrations"
    return "layer-other"


def complexity_for(non_empty: int, fn: int, cls: int) -> str:
    if non_empty < 50 and fn <= 2 and cls <= 1:
        return "simple"
    if non_empty > 200 or fn > 15 or cls > 8:
        return "complex"
    return "moderate"


def tags_for_path(rel: str, lang: str) -> list[str]:
    t = ["source-code"]
    if "test" in rel or "/tests/" in rel:
        t.extend(["test", "quality"])
    elif rel.endswith("main.py") and "backend/app" in rel:
        t.extend(["entry-point", "fastapi"])
    elif "/api/v1/" in rel or rel.endswith("router.py"):
        t.extend(["api-handler", "rest"])
    elif "/schemas/" in rel:
        t.extend(["validation", "serialization"])
    elif "/middleware/" in rel:
        t.extend(["middleware", "http"])
    elif "/domain/entities/" in rel:
        t.extend(["data-model", "domain"])
    elif "/domain/ports/" in rel:
        t.extend(["port", "domain"])
    elif "/application/services/" in rel:
        t.extend(["service", "use-case"])
    elif "/infrastructure/" in rel:
        t.extend(["adapter", "infrastructure"])
    elif rel.endswith("page.tsx") or rel.endswith("layout.tsx"):
        t.extend(["component", "nextjs"])
    elif lang == "typescript":
        t.extend(["typescript", "frontend"])
    elif lang == "python":
        t.extend(["python", "backend"])
    return list(dict.fromkeys(t))[:5]


def summary_for(rel: str, lang: str, fn_names: list[str], cls_names: list[str]) -> str:
    base = Path(rel).name
    if rel.endswith("main.py"):
        return "FastAPI application entry: creates app, mounts routers, lifespan hooks."
    if "/api/v1/router.py" in rel or rel.endswith("/router.py") and "api" in rel:
        return "Aggregates versioned API routers for the HTTP surface."
    if "/dependencies.py" in rel:
        return "FastAPI dependency injection wiring for services, repos, and auth."
    if "/domain/ports/" in rel:
        return f"Domain port (abstract interface) for {base.replace('.py', '')}."
    if "/domain/entities/" in rel:
        return f"Domain entity {base}: core business object for persistence and APIs."
    if "/application/services/" in rel:
        return f"Application service orchestrating use cases ({', '.join(cls_names[:2]) or 'helpers'})."
    if "/infrastructure/persistence/postgres/" in rel:
        return "Postgres/SQLAlchemy adapter implementing domain repositories."
    if "/infrastructure/orchestration/" in rel:
        return "LangGraph-based agent orchestration adapter."
    if fn_names and cls_names:
        return f"{lang} module {base}: classes {', '.join(cls_names[:3])}, functions {', '.join(fn_names[:3])}."
    if cls_names:
        return f"{lang} module defining {', '.join(cls_names)}."
    if fn_names:
        return f"{lang} module with functions {', '.join(fn_names[:5])}."
    return f"{lang} source file {rel}."


def analyze_python(path: Path, rel: str, all_files: set[str]) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    non_empty = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    tree = ast.parse(text, filename=rel)
    fn_names: list[str] = []
    cls_names: list[str] = []
    imports: list[tuple[str, str | None]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            fn_names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            cls_names.append(node.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module
                if mod.startswith("app."):
                    target = "backend/" + mod.replace(".", "/") + ".py"
                    if target not in all_files:
                        init = "backend/" + mod.replace(".", "/") + "/__init__.py"
                        target = init if init in all_files else None
                    if target:
                        imports.append((rel, target))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    mod = alias.name
                    target = "backend/" + mod.replace(".", "/") + ".py"
                    if target not in all_files:
                        init = "backend/" + mod.replace(".", "/") + "/__init__.py"
                        target = init if init in all_files else None
                    if target:
                        imports.append((rel, target))

    return {
        "non_empty": non_empty,
        "functions": fn_names,
        "classes": cls_names,
        "imports": imports,
        "total_lines": len(lines),
    }


TS_IMPORT = re.compile(
    r"""^(?:import\s+[^'"]+\s+from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"])""",
    re.MULTILINE,
)


def analyze_typescript(path: Path, rel: str, all_files: set[str]) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    non_empty = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("//"))
    fn_names: list[str] = []
    for m in re.finditer(
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(",
        text,
    ):
        fn_names.append(next(g for g in m.groups() if g))
    cls_names = re.findall(r"(?:export\s+)?(?:default\s+)?(?:function|class)\s+(\w+)", text)
    cls_names = [c for c in cls_names if c not in fn_names][:20]
    imports: list[tuple[str, str | None]] = []
    for m in TS_IMPORT.finditer(text):
        src = m.group(1) or m.group(2)
        if not src or src.startswith("@/"):
            continue
        if src.startswith("."):
            base = Path(rel).parent
            cand = (base / src).resolve()
            try:
                rel_cand = cand.relative_to(ROOT)
                s = str(rel_cand).replace("\\", "/")
                for ext in ("", ".ts", ".tsx"):
                    t = s + ext if ext else s
                    if t in all_files:
                        imports.append((rel, t))
                        break
                    if (Path(t).suffix == "" and (Path(t).with_suffix(".tsx")).as_posix() in all_files):
                        imports.append((rel, (Path(t).with_suffix(".tsx")).as_posix()))
                        break
            except ValueError:
                pass
    return {
        "non_empty": non_empty,
        "functions": list(dict.fromkeys(fn_names))[:40],
        "classes": list(dict.fromkeys(cls_names))[:20],
        "imports": imports,
        "total_lines": len(lines),
    }


def main() -> int:
    if not SCAN.is_file():
        print(f"Missing {SCAN}", file=sys.stderr)
        return 1
    data = json.loads(SCAN.read_text())
    files = data["files"]
    all_files = {f["path"] for f in files}
    nodes: list[dict] = []
    edges: list[dict] = []
    file_ids: dict[str, str] = {}

    for f in files:
        rel = f["path"]
        lang = f.get("language", "")
        path = ROOT / rel
        fid = f"file:{rel}"
        file_ids[rel] = fid
        if not path.is_file():
            nodes.append(
                {
                    "id": fid,
                    "type": "file",
                    "name": Path(rel).name,
                    "filePath": rel,
                    "summary": f"Listed in scan but missing on disk: {rel}.",
                    "tags": ["missing", "scan-only", "stale"],
                    "complexity": "simple",
                }
            )
            continue

        try:
            if lang == "python":
                info = analyze_python(path, rel, all_files)
            elif lang == "typescript":
                info = analyze_typescript(path, rel, all_files)
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
                lines = text.splitlines()
                info = {
                    "non_empty": sum(1 for ln in lines if ln.strip()),
                    "functions": [],
                    "classes": [],
                    "imports": [],
                    "total_lines": len(lines),
                }
        except SyntaxError:
            info = {
                "non_empty": 0,
                "functions": [],
                "classes": [],
                "imports": [],
                "total_lines": 0,
            }

        comp = complexity_for(
            info["non_empty"],
            len(info["functions"]),
            len(info["classes"]),
        )
        nodes.append(
            {
                "id": fid,
                "type": "file",
                "name": Path(rel).name,
                "filePath": rel,
                "summary": summary_for(rel, lang, info["functions"], info["classes"]),
                "tags": tags_for_path(rel, lang),
                "complexity": comp,
            }
        )

        for _src_rel, tgt in info["imports"]:
            if tgt and tgt in all_files:
                tid = f"file:{tgt}"
                if tid != fid:
                    edges.append(
                        {
                            "source": fid,
                            "target": tid,
                            "type": "imports",
                            "direction": "forward",
                            "weight": 0.7,
                        }
                    )

    # Dedupe edges; drop dangling references
    seen_e = set()
    deduped: list[dict] = []
    for e in edges:
        k = (e["source"], e["target"], e["type"])
        if k not in seen_e:
            seen_e.add(k)
            deduped.append(e)
    edges = deduped
    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]

    layer_defs = [
        ("layer-api", "API layer", "FastAPI routes, schemas, middleware.", "backend/app/api/"),
        ("layer-domain", "Domain", "Entities, ports, value objects.", "backend/app/domain/"),
        ("layer-application", "Application", "Services and use cases.", "backend/app/application/"),
        ("layer-infrastructure", "Infrastructure", "Postgres, Redis, LangGraph, sandbox.", "backend/app/infrastructure/"),
        ("layer-frontend", "Frontend", "Next.js App Router pages and components.", "frontend/src/"),
        ("layer-tests", "Tests", "Pytest integration and unit tests.", "backend/tests/"),
        ("layer-migrations", "Migrations", "Alembic schema migrations.", "backend/migrations/"),
    ]
    layers: list[dict] = []
    for lid, name, desc, prefix in layer_defs:
        nids = [f"file:{p}" for p in sorted(all_files) if p.startswith(prefix)]
        if nids:
            layers.append({"id": lid, "name": name, "description": desc, "nodeIds": nids})

    other_files = [
        f"file:{p}"
        for p in sorted(all_files)
        if not any(p.startswith(prefix) for _, _, _, prefix in layer_defs)
    ]
    if other_files:
        layers.append(
            {
                "id": "layer-other",
                "name": "Other",
                "description": "Config, scripts, docs, compose, modal stubs.",
                "nodeIds": other_files,
            }
        )

    tour_candidates = [
        ("backend/app/main.py", "API bootstrap", "FastAPI app creation and router mount."),
        ("backend/app/api/v1/router.py", "HTTP surface", "All v1 API routers."),
        ("backend/app/dependencies.py", "DI wiring", "Services and auth dependencies."),
        ("backend/app/infrastructure/orchestration/langgraph_orchestrator.py", "Orchestration", "LangGraph agent runs."),
        ("frontend/src/app/layout.tsx", "UI shell", "Root layout and global styles."),
    ]
    tour = []
    order = 0
    for p, title, desc in tour_candidates:
        if p in all_files:
            order += 1
            tour.append(
                {
                    "order": order,
                    "title": title,
                    "description": desc,
                    "nodeIds": [f"file:{p}"],
                }
            )

    graph = {
        "version": "1.0.0",
        "project": {
            "name": data.get("name", "AgentForge"),
            "languages": data.get("languages", []),
            "frameworks": data.get("frameworks", []) or ["FastAPI", "Next.js"],
            "description": data.get("description", "AgentForge monorepo"),
            "analyzedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "gitCommitHash": git_hash(),
        },
        "nodes": nodes,
        "edges": edges,
        "layers": layers,
        "tour": tour,
    }

    OUT_GRAPH.parent.mkdir(parents=True, exist_ok=True)
    OUT_GRAPH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    OUT_META.write_text(
        json.dumps(
            {
                "lastAnalyzedAt": graph["project"]["analyzedAt"],
                "gitCommitHash": graph["project"]["gitCommitHash"],
                "version": "1.0.0",
                "analyzedFiles": len(files),
                "generator": "scripts/ua_build_knowledge_graph.py (deterministic fallback)",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    n_file = sum(1 for n in nodes if n["type"] == "file")
    print(
        f"Wrote {OUT_GRAPH} — {n_file} file nodes, {len(edges)} import edges, "
        f"{len(layers)} layers, {len(tour)} tour steps."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
