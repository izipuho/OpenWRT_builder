from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])
INDEX_HTML_PATH = Path("/ingress/index.html")

@router.get("/")
def index(request: Request):
    html = INDEX_HTML_PATH.read_text(encoding="utf-8")
    ingress_path = (request.headers.get("X-Ingress-Path") or "").strip()

    if ingress_path and not ingress_path.endswith("/"):
        ingress_path = f"{ingress_path}/"

    if ingress_path:
        base_tag = f'    <base href="{ingress_path}" />'
        if "<head>" in html:
            html = html.replace("<head>", f"<head>\n{base_tag}", 1)

    return HTMLResponse(html)
