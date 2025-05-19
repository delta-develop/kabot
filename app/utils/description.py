from app.models.vehicle import Vehicle
def build_vehicle_description(vehicle: Vehicle) -> str:
    return (
        f"{vehicle.make} {vehicle.model} {vehicle.year}, versión {vehicle.version}, "
        f"{vehicle.km} km, ${vehicle.price} MXN, "
        f"{'con Bluetooth' if vehicle.bluetooth else 'sin Bluetooth'}, "
        f"{'compatible con CarPlay' if vehicle.car_play else 'no compatible con CarPlay'}."
    )