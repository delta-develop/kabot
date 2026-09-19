from fastapi import FastAPI

app = FastAPI(title="agent")


@app.get("/health")
async def health() -> dict[str, str]:
    """Report that the service is up.

    Returns:
        dict: Service status and name.
    """
    return {"status": "ok", "service": "agent"}
