import asyncio

from app.main import health


def test_health_reports_the_service_name():
    assert asyncio.run(health()) == {"status": "ok", "service": "memory"}
