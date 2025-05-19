from sqlmodel import SQLModel, Field


class Vehicle(SQLModel, table=True):
    """Represents a vehicle record in the database.

    Attributes:
        stock_id (int): Unique identifier for the vehicle.
        km (int): Number of kilometers the vehicle has been driven.
        price (float): Price of the vehicle.
        make (str): Manufacturer of the vehicle.
        model (str): Model name of the vehicle.
        year (int): Manufacturing year of the vehicle.
        version (str): Specific version or trim of the vehicle.
        bluetooth (bool): Indicates if the vehicle has Bluetooth support.
        largo (float): Length of the vehicle in millimeters.
        ancho (float): Width of the vehicle in millimeters.
        altura (float): Height of the vehicle in millimeters.
        car_play (bool): Indicates if the vehicle supports Apple CarPlay.
    """

    stock_id: int = Field(primary_key=True)
    km: int
    price: float
    make: str
    model: str
    year: int
    version: str
    bluetooth: bool = Field(default=False)
    largo: float
    ancho: float
    altura: float
    car_play: bool = Field(default=False)
