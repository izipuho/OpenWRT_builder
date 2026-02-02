from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1")

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/profiles")
def get_profiles(req: Request):
    return req.app.state.registry.list_profiles()

@router.post("/profile", status_code=201)
def post_profile(req: Request, body: dict):
    reg = req.app.state.registry
    try:
        return reg.create_profile(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_request")
    except FileExistsError:
        raise HTTPException(status_code=409, detail="conflict")

@router.get("lists")
def get_lists(req: Request):
    return req.app.state.registry.list_lists()

@router.get("/debug")
def debug(req: Request):
    return req.app.state.registry.debug()

@router.get("/debug/env")
def debug_env():
    import os
    return os.environ.items()