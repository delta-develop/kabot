import pytest
from app.utils.description import build_vehicle_description
from app.models.vehicle import Vehicle

def test_build_vehicle_description():
    vehicle = Vehicle(
        stock_id=12345,
        km=50000,
        price=250000.0,
        make="Mazda",
        model="3",
        year=2020,
        version="i Touring",
        bluetooth=True,
        largo=4460.0,
        ancho=1795.0,
        altura=1450.0,
        car_play=True
    )

    expected_description = (
        "Mazda 3 2020, versión i Touring, 50000 km, $250000.0 MXN, "
        "con Bluetooth, compatible con CarPlay."
    )

    assert build_vehicle_description(vehicle) == expected_description