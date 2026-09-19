from fastapi.routing import iter_route_contexts

from app.main import app


def test_expected_routes_are_registered():
    expected_routes = {
        ("GET", "/search"),
        ("POST", "/upload"),
        ("POST", "/webhook/whatsapp"),
        ("POST", "/debug/migrate-memory"),
        ("GET", "/author"),
    }
    registered_routes = {
        (method, route.path)
        for route in iter_route_contexts(app.routes)
        for method in route.methods or ()
    }

    assert expected_routes <= registered_routes
