"""Architecture boundaries for router/service decoupling."""

from __future__ import annotations

import ast
from pathlib import Path


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            if node.end_lineno is None:
                break
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])

    raise AssertionError(f"Function {function_name!r} not found in {path}")


def test_tasks_router_list_delegates_audit_and_access_logic_to_service() -> None:
    router_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "tasks.py"
    fn_source = _function_source(router_path, "list_tasks")

    assert "task_service.list_tasks_for_session(" in fn_source
    assert "audit_service.log_phi_access" not in fn_source
    assert "check_surrogate_access" not in fn_source
    assert "q_type =" not in fn_source
    assert "db.commit(" not in fn_source


def test_intended_parents_router_list_delegates_audit_logic_to_service() -> None:
    router_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "intended_parents.py"
    fn_source = _function_source(router_path, "list_intended_parents")

    assert "ip_service.list_intended_parents_for_session(" in fn_source
    assert "audit_service.log_phi_access" not in fn_source
    assert "q_type =" not in fn_source
    assert "db.commit(" not in fn_source


def test_search_router_delegates_normalization_permissions_and_audit_to_service() -> None:
    router_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "search.py"
    fn_source = _function_source(router_path, "global_search")

    assert "search_service.global_search_for_session(" in fn_source
    assert "permission_service.get_effective_permissions" not in fn_source
    assert "audit_service.log_phi_access" not in fn_source
    assert "q_type =" not in fn_source
    assert "db.commit(" not in fn_source
