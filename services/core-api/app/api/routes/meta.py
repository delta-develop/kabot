from fastapi import APIRouter

router = APIRouter()


# Author information endpoint
@router.get("/author")
async def get_author():
    """
    Returns author metadata for the project.

    Returns:
        dict: Author information.
    """
    return {
        "name": "Leonardo HG",
        "location": "Ciudad de México",
        "role": "Backend Developer",
        "project": "Tech Challenge - Kabot",
    }
