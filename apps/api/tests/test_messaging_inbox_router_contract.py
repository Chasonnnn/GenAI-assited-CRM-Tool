from fastapi.routing import APIRoute

from app.core.deps import require_csrf_header
from app.core.permissions import PermissionKey as P
from app.db.enums import Role
from app.routers.messaging_inbox import router


def _closure_values(callable_object) -> list[object]:
    closure = getattr(callable_object, "__closure__", None) or ()
    return [cell.cell_contents for cell in closure]


def test_inbox_router_is_admin_developer_only_and_has_no_composer_route() -> None:
    assert router.prefix == "/messaging"
    role_dependency = router.dependencies[0].dependency
    allowed_roles = next(
        value for value in _closure_values(role_dependency) if isinstance(value, list)
    )
    assert set(allowed_roles) == {Role.ADMIN, Role.DEVELOPER}

    paths = {route.path for route in router.routes if isinstance(route, APIRoute)}
    assert paths == {
        "/messaging/conversations",
        "/messaging/candidates/{surrogate_id}/conversations",
        "/messaging/conversations/{conversation_id}",
        "/messaging/conversations/{conversation_id}/read",
        "/messaging/conversations/{conversation_id}/link",
        "/messaging/reconciliation/{case_id}",
    }
    assert not any("send" in path or "reply" in path for path in paths)

    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        dependency_values = [
            value
            for dependency in route.dependant.dependencies
            for value in _closure_values(dependency.call)
        ]
        assert P.INTEGRATIONS_MANAGE in dependency_values, route.path


def test_every_inbox_mutation_requires_csrf() -> None:
    mutation_routes = [
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.methods.intersection({"POST", "PATCH", "DELETE"})
    ]
    assert mutation_routes
    for route in mutation_routes:
        dependencies = {dependency.dependency for dependency in route.dependencies}
        assert require_csrf_header in dependencies, route.path
