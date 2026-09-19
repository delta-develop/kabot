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
        for route in app.routes
        for method in route.methods
    }

    assert expected_routes <= registered_routes
