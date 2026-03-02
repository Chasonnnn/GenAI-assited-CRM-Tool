"""Ensure routes declare explicit response contracts."""

from __future__ import annotations

import ast
from pathlib import Path

ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "options", "head", "api_route"}


RESPONSE_TYPES_ALLOW_NO_MODEL = {
    "Response",
    "JSONResponse",
    "RedirectResponse",
    "StreamingResponse",
    "FileResponse",
    "PlainTextResponse",
    "HTMLResponse",
}


def _iter_router_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    return sorted((root / "app" / "routers").rglob("*.py")) + [root / "app" / "main.py"]


def _is_route_fn(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr in ROUTE_DECORATORS:
            return True
    return False


def _route_has_response_model(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[bool, str | None]:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        target = decorator.func
        if not (isinstance(target, ast.Attribute) and target.attr in ROUTE_DECORATORS):
            continue
        for kw in decorator.keywords:
            if kw.arg == "response_model":
                return True, ast.unparse(kw.value)
    return False, None


def _is_response_annotation(annotation: ast.expr | None) -> bool:
    if annotation is None:
        return False
    text = ast.unparse(annotation)
    return any(name in text for name in RESPONSE_TYPES_ALLOW_NO_MODEL)


def test_routes_have_response_model_or_return_annotation() -> None:
    offenders: list[str] = []

    for path in _iter_router_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not _is_route_fn(node):
                continue
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))

            has_model, _ = _route_has_response_model(node)
            if not has_model and node.returns is None:
                offenders.append(f"{path}:{node.lineno}:{node.name}")

    assert not offenders, "Found routes without response contract:\n" + "\n".join(offenders)


def test_routes_do_not_use_response_model_dict() -> None:
    offenders: list[str] = []

    for path in _iter_router_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not _is_route_fn(node):
                continue
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))

            _, model = _route_has_response_model(node)
            if model == "dict":
                offenders.append(f"{path}:{node.lineno}:{node.name}")

    assert not offenders, "Found response_model=dict:\n" + "\n".join(offenders)


def test_routes_do_not_return_any_or_dict_any_for_json_contracts() -> None:
    offenders: list[str] = []

    for path in _iter_router_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not _is_route_fn(node):
                continue
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))

            has_model, _ = _route_has_response_model(node)
            if has_model:
                continue
            if _is_response_annotation(node.returns):
                continue
            if node.returns is None:
                continue

            ret = ast.unparse(node.returns)
            if ret == "Any" or ret == "dict[str, Any]":
                offenders.append(f"{path}:{node.lineno}:{node.name}:{ret}")

    assert not offenders, "Found weak JSON return annotations:\n" + "\n".join(offenders)
