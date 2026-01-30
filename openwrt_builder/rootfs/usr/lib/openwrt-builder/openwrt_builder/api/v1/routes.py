from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

_PROFILES = [
    {
        "profile_id": "simple-ap",
        "name": "Simple AP",
        "schema_version": 1,
        "updated_at": "2026-01-30T09:00:00Z",
    }
]


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/profiles")
def get_profiles():
    return _PROFILES