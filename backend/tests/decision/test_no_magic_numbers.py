import ast
from pathlib import Path


def test_no_magic_numbers():
    root = Path(__file__).resolve().parents[2] / "app" / "decision"
    violations = []
    for path in sorted(root.glob("*.py")):
        if path.name == "config.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and type(node.value) in (int, float)
                and node.value not in {0, 1, 2, 12, 100, 1200}
            ):
                violations.append(f"{path.name}:{node.lineno}: {node.value}")
    assert not violations, "\n".join(violations)


def test_engine_has_only_local_or_standard_library_imports():
    import sys

    root = Path(__file__).resolve().parents[2] / "app" / "decision"
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules = [node.module.split(".")[0]]
            else:
                continue
            assert set(modules) <= sys.stdlib_module_names, (path.name, modules)
