from fastapi import APIRouter

router = APIRouter()


@router.get("/customer-files")
def customer_files_placeholder(customer_id: int | None = None):
    return {"success": True, "data": [], "message": "Dosya API — sonraki adım"}
