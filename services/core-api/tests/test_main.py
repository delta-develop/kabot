from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app.main import app


def test_expected_routes_are_registered():
    expected_routes = {
        ("POST", "/debug/migrate-memory"),
        ("GET", "/author"),
    }
    registered_routes = {
        (method, route.path)
        for route in iter_route_contexts(app.routes)
        for method in route.methods or ()
    }

    assert expected_routes <= registered_routes


def test_lifespan_creates_the_relational_schema(mocker):
    # Driven through the real ASGI lifespan protocol (not by calling the
    # `lifespan` function directly) so this fails if `app` is ever built
    # without `lifespan=lifespan` attached.
    setup = mocker.patch(
        "app.main.RelationalStorage.setup",
        new_callable=mocker.AsyncMock,
    )

    with TestClient(app):
        pass

    setup.assert_awaited_once()
