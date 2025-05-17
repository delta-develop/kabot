from sqlmodel import SQLModel, Field
from typing import Optional


class Vehicle(SQLModel, table=True):
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
