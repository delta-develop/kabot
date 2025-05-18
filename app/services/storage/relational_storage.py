from typing import Any, Dict, List
from sqlmodel import Session, select, create_engine
from app.services.storage.base import Storage
from app.models.vehicle import Vehicle
from sqlalchemy.engine import Engine, create_engine


DATABASE_URL = "postgresql+psycopg2://kabot:password@postgres:5432/kabot"
engine = create_engine(DATABASE_URL, echo=True)

class RelationalStorage(Storage):
    """Relational storage implementation using SQLModel and PostgreSQL.

    This class provides methods to interact with a PostgreSQL database
    using SQLModel for ORM capabilities.
    """

    def __init__(self) -> None:
        """Initialize the relational storage with a SQLAlchemy engine.

        Args:
            None
        """
        self.engine = RelationalStorage.get_postgres_engine()

    def setup(self) -> None:
        """Create necessary tables in the relational database."""
        Vehicle.metadata.create_all(self.engine)

    def save(self, data: Dict[str, Any]) -> None:
        """Save a single vehicle record to the database.

        Args:
            data (Dict[str, Any]): Dictionary containing vehicle data.
        """
        with Session(self.engine) as session:
            vehicle = Vehicle(**data)
            session.add(vehicle)
            session.commit()

    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query vehicle records using filter criteria.

        Args:
            filters (Dict[str, Any]): Filter criteria as key-value pairs.

        Returns:
            List[Dict[str, Any]]: List of matching vehicle records.
        """
        with Session(self.engine) as session:
            statement = select(Vehicle)
            for key, value in filters.items():
                statement = statement.where(getattr(Vehicle, key) == value)
            results = session.exec(statement).all()
            return [vehicle.model_dump() for vehicle in results]

    def bulk_load(self, data: Dict) -> List[Dict[str, Any]]:
        """Bulk load multiple vehicle records into the database.

        Args:
            data (Dict): Dictionary with key 'records' containing a list of vehicle records.

        Returns:
            List[Dict[str, Any]]: List of successfully loaded vehicle records.
        """
        vehicles_data = data.get("records", [])
        vehicles = [Vehicle(**record) for record in vehicles_data]

        with Session(self.engine) as session:
            session.add_all(vehicles)
            session.commit()
            return [vehicle.model_dump() for vehicle in vehicles]
        
    @staticmethod
    def get_postgres_engine() -> Engine:
        """Create a SQLAlchemy engine for PostgreSQL.

        Returns:
            Engine: The SQLAlchemy engine instance.
        """
        postgres_url = "postgresql://kabot:kabot123@postgres:5432/kavak"
        return create_engine(postgres_url)
