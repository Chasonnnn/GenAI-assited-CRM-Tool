"""Guardrails for async route handlers that run sync DB code."""

from __future__ import annotations

import ast
from pathlib import Path

ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "options", "head", "api_route"}


STREAMING_ALLOWLIST = {
    "chat_stream",
    "generate_email_template_stream",
    "summarize_surrogate_stream",
    "draft_email_stream",
    "analyze_dashboard_stream",
    "summarize_interview_stream",
    "summarize_all_interviews_stream",
    "generate_workflow_stream",
    "parse_schedule_stream",
    "get_ai_mapping_suggestions_stream",
}


def _iter_router_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    return sorted((root / "app" / "routers").rglob("*.py"))


def _is_route_fn(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr in ROUTE_DECORATORS:
            return True
    return False


def _has_sync_session_param(node: ast.AsyncFunctionDef) -> bool:
    for arg in node.args.args + node.args.kwonlyargs:
        if arg.annotation is None:
            continue
        ann = ast.unparse(arg.annotation)
        if "Session" in ann:
            return True
    return False


def _await_count(node: ast.AsyncFunctionDef) -> int:
    return sum(isinstance(n, ast.Await) for n in ast.walk(node))


def test_async_routes_with_sync_session_must_await_or_be_allowlisted_streams() -> None:
    offenders: list[str] = []

    for path in _iter_router_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            if not _is_route_fn(node):
                continue
            if not _has_sync_session_param(node):
                continue

            if _await_count(node) > 0:
                continue
            if node.name in STREAMING_ALLOWLIST:
                continue

            offenders.append(f"{path}:{node.lineno}:{node.name}")

    assert not offenders, "Found async sync-DB routes with no await:\n" + "\n".join(offenders)
