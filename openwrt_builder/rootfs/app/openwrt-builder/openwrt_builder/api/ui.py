from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ui_router = APIRouter(tags=["ui"])


ui_router.mount("/static", StaticFiles(directory="/ingress"), name="static")

@ui_router.get("/")
def index():
    return FileResponse("/ingress/index.html")
