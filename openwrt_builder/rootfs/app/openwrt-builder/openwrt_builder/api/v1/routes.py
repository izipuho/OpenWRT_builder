from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1")

@router.get("/health")
def health():
    return {"status": "ok"}

# Manage Profiles
@router.get("/profiles")
def get_profiles(req: Request):
    return req.app.state.registry.list_profiles()

@router.get("/profile/{profile_id}", status_code=200)
def get_profile(req: Request, profile_id: str):
    reg = req.app.state.registry
    try:
        return reg.get_profile(profile_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "reason": "profile_not_found"},
        )

@router.post("/profile", status_code=201)
def post_profile(req: Request, body: dict):
    reg = req.app.state.registry
    try:
        return reg.create_profile(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid_request", "reason": str(e)})
    except FileExistsError:
        raise HTTPException(status_code=409, detail="conflict")

@router.put("/profile/{profile_id}", status_code=200)
def put_profile(req: Request, profile_id: str, body: dict):
    reg = req.app.state.registry
    try:
        return reg.create_profile(body, profile_id, True)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_request", "reason": str(e)},
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "reason": "profile_not_found"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "reason": str(e)},
        )

@router.delete("/profile/{profile_id}", status_code=200)
def delete_profile(req: Request, profile_id: str):
    reg = req.app.state.registry
    try:
        return reg.delete_profile(profile_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "reason": "profile_not_found"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "reason": str(e)},
        )

# Manage lists
@router.get("/lists")
def get_lists(req: Request):
    return req.app.state.registry.list_lists()

@router.get("/list/{list_id}", status_code=200)
def get_list(req: Request, list_id: str):
    reg = req.app.state.registry
    try:
        return reg.get_list(list_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "reason": "profile_not_found"},
        )

@router.post("/list", status_code=201)
def post_list(req: Request, body: dict):
    reg = req.app.state.registry
    try:
        return reg.create_list(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid_request", "reason": str(e)})
    except FileExistsError:
        raise HTTPException(status_code=409, detail="conflict")

@router.put("/list/{list_id}", status_code=200)
def put_list(req: Request, list_id: str, body: dict):
    reg = req.app.state.registry
    try:
        return reg.create_list(body, list_id, True)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_request", "reason": str(e)},
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "reason": "list_not_found"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "reason": str(e)},
        )

@router.delete("/list/{list_id}", status_code=200)
def delete_list(req: Request, list_id: str):
    reg = req.app.state.registry
    try:
        return reg.delete_list(list_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "reason": "list_not_found"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "reason": str(e)},
        )

# Misc
@router.post("/debug", status_code=201)
def debug(req: Request, body: dict) -> list:
    res: list = []
    if body["command"] == "ls":
        from pathlib import Path
        for path in Path(body["path"]).iterdir():
            res.append(path)
    return res
