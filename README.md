

# KABOT

Kabot is a data ingestion and indexing system that allows uploading CSV files, parsing them, and storing the data both in PostgreSQL and OpenSearch. It is designed with a modular and asynchronous architecture using FastAPI, SQLModel, and Docker.

## Features

- Upload and process CSV files via HTTP endpoint
- Store records in PostgreSQL and OpenSearch simultaneously
- Chunked and asynchronous processing for performance
- Uses OpenSearch to allow indexing and searching
- Uses PostgreSQL for relational data storage

## Getting Started

### Requirements

- Docker and Docker Compose
- Make

### Running the Project

To start the application:

```bash
make start
```

This will build and run all required containers (API, PostgreSQL, OpenSearch, etc.).

### Initial Setup

After running the containers, you **must** initialize the databases by running:

```bash
make setup
```

This command will:

- Create the required tables in PostgreSQL
- Create the index in OpenSearch

Skipping this step will cause the application to fail when trying to interact with the databases.

### Useful Makefile Commands

- `make rebuild-app` - Rebuilds the Docker containers and runs the application
- `make setup` - Initializes database schemas (PostgreSQL + OpenSearch)
- `make enter-app` - Enters the running app container
- `make activate-venv` - Activates the virtual environment inside the container
- `make rebuild-python` - Rebuilds only the Python-related containers without resetting databases
- `make logs` - Follows the logs of all Docker containers

### API Endpoint

- `POST /upload` - Upload a CSV file to ingest data into the system

## Notes

- The system uses chunked ingestion (100 records per chunk) to avoid memory issues
- Boolean fields are interpreted from strings like "Sí", "Yes", "True", etc.
- Duplicate records are avoided in OpenSearch by using `stock_id` as the document ID

---

Built with 💻 and lots of coffee ☕️ by Leonardo and ChatGPT.