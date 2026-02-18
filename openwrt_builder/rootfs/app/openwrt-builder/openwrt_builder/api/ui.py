from fastapi import APIRouter
from fastapi.responses import FileResponse

ui_router = APIRouter(tags=["ui"])

@ui_router.get("/")
def index():
    return FileResponse("/ingress/index.html")
