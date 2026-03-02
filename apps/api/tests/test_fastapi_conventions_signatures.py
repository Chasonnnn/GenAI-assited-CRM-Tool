"""FastAPI signature convention checks.

These checks enforce modern FastAPI parameter and dependency declaration patterns.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "options", "head", "api_route"}
PARAM_CALLS = {"Depends", "Query", "Path", "Header", "Form", "File", "Body", "Cookie"}


def _iter_target_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    routers = sorted((root / "app" / "routers").rglob("*.py"))
    deps_file = root / "app" / "core" / "deps.py"
    return routers + [deps_file]


def _is_route_fn(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr in ROUTE_DECORATORS:
            return True
    return False


def _is_annotated(annotation: ast.expr | None) -> bool:
    return (
        isinstance(annotation, ast.Subscript)
        and isinstance(annotation.value, ast.Name)
        and annotation.value.id == "Annotated"
    )


def _call_name(node: ast.AST | None) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def test_route_params_use_annotated_for_fastapi_param_calls() -> None:
    offenders: list[str] = []

    for path in _iter_target_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not _is_route_fn(node):
                continue
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))

            args = node.args.args + node.args.kwonlyargs
            defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)

            for arg, default in zip(args, defaults):
                call = _call_name(default)
                if call in PARAM_CALLS and not _is_annotated(arg.annotation):
                    offenders.append(f"{path}:{arg.lineno}:{node.name}:{arg.arg}:{call}")

    assert not offenders, "Found non-Annotated FastAPI params:\n" + "\n".join(offenders)


def test_route_depends_params_are_typed_and_not_dict_session() -> None:
    offenders: list[str] = []

    for path in _iter_target_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not _is_route_fn(node):
                continue
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))

            args = node.args.args + node.args.kwonlyargs
            defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)

            for arg, default in zip(args, defaults):
                if _call_name(default) != "Depends":
                    continue

                if arg.annotation is None:
                    offenders.append(f"{path}:{arg.lineno}:{node.name}:{arg.arg}:untyped")
                    continue

                ann = ast.unparse(arg.annotation)
                if ann == "dict":
                    offenders.append(f"{path}:{arg.lineno}:{node.name}:{arg.arg}:dict")

    assert not offenders, "Found invalid Depends param typing:\n" + "\n".join(offenders)


def test_csrf_dependency_is_decorator_level_not_parameter_style() -> None:
    offenders: list[str] = []

    for path in _iter_target_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not _is_route_fn(node):
                continue
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))

            args = node.args.args + node.args.kwonlyargs
            defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)

            for arg, default in zip(args, defaults):
                if _call_name(default) != "Depends":
                    continue
                if not isinstance(default, ast.Call) or not default.args:
                    continue
                dep = default.args[0]
                dep_name = ast.unparse(dep)
                if dep_name == "require_csrf_header":
                    offenders.append(f"{path}:{arg.lineno}:{node.name}:{arg.arg}")

    assert not offenders, "Found parameter-style CSRF Depends:\n" + "\n".join(offenders)
