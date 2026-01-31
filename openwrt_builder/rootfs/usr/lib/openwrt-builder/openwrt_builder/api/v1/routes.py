from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1")

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/profiles")
def get_profiles(req: Request):
    return req.app.state.registry.list_profiles()

@router.get("lists")
def get_lists(req: Request):
    return req.app.state.registry.list_lists()

@router.get("/debug")
def debug(req: Request):
    return req.app.state.registry.debug()