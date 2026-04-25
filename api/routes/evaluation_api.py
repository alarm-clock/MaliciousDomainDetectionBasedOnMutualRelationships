from fastapi import APIRouter


router = APIRouter()

@router.get("/evaluate/")
async def evaluate():
    pass


@router.post("/evaluate-multiple")
async def evaluate_multiple():
    pass