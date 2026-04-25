import ast
import json
import sys
import os

def parse_python_file(path, project_root):
    full_path = os.path.join(project_root, path)
    result = {
        "path": path,
        "language": "python",
        "totalLines": 0,
        "nonEmptyLines": 0,
        "functions": [],
        "classes": [],
        "imports": [],
        "exports": [],
        "metrics": {
            "importCount": 0,
            "exportCount": 0,
            "functionCount": 0,
            "classCount": 0
        }
    }

    if not os.path.exists(full_path):
        return None

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
        result["totalLines"] = len(lines)
        result["nonEmptyLines"] = len([l for l in lines if l.strip() and not l.strip().startswith('#')])

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return result

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            result["functions"].append({
                "name": node.name,
                "startLine": node.lineno,
                "endLine": node.end_lineno,
                "params": [arg.arg for arg in node.args.args]
            })
            result["metrics"]["functionCount"] += 1
            # Python doesn't have explicit exports, but everything not starting with _ is arguably exported.
            if not node.name.startswith('_'):
                result["exports"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "isDefault": False
                })
                result["metrics"]["exportCount"] += 1

        elif isinstance(node, ast.ClassDef):
            methods = []
            properties = []
            for child in node.body:
                if isinstance(child, ast.FunctionDef) or isinstance(child, ast.AsyncFunctionDef):
                    methods.append(child.name)
                elif isinstance(child, ast.AnnAssign):
                    if isinstance(child.target, ast.Name):
                        properties.append(child.target.id)

            result["classes"].append({
                "name": node.name,
                "startLine": node.lineno,
                "endLine": node.end_lineno,
                "methods": methods,
                "properties": properties
            })
            result["metrics"]["classCount"] += 1
            if not node.name.startswith('_'):
                result["exports"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "isDefault": False
                })
                result["metrics"]["exportCount"] += 1

        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append({
                    "source": alias.name,
                    "resolvedPath": None,
                    "specifiers": [alias.name],
                    "line": node.lineno,
                    "isExternal": True # Assume true for absolute imports without resolving
                })
            result["metrics"]["importCount"] += 1

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result["imports"].append({
                    "source": node.module,
                    "resolvedPath": None,
                    "specifiers": [alias.name for alias in node.names],
                    "line": node.lineno,
                    "isExternal": node.level == 0
                })
                result["metrics"]["importCount"] += 1

    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)

    in_file = sys.argv[1]
    out_file = sys.argv[2]

    with open(in_file, 'r') as f:
        data = json.load(f)

    project_root = data.get("projectRoot", "")
    batch_files = data.get("batchFiles", [])

    output = {
        "scriptCompleted": True,
        "filesAnalyzed": 0,
        "filesSkipped": [],
        "results": []
    }

    for f in batch_files:
        path = f["path"]
        res = parse_python_file(path, project_root)
        if res is not None:
            output["results"].append(res)
            output["filesAnalyzed"] += 1
        else:
            output["filesSkipped"].append(path)

    with open(out_file, 'w') as f:
        json.dump(output, f, indent=2)
