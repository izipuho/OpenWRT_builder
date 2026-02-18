"""FastAPI app entrypoint for OpenWRT Builder."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from openwrt_builder.api.v1.builds import router as builds_router
from openwrt_builder.api.errors import register_exception_handlers
from openwrt_builder.env import env_path
from openwrt_builder.api.v1.profiles import router as profiles_router
from openwrt_builder.api.v1.files import router as files_router
from openwrt_builder.service.builds_registry import BuildsRegistry
from openwrt_builder.service.build_queue import BuildQueue
from openwrt_builder.service.profiles_registry import ListsRegistry, ProfilesRegistry
from openwrt_builder.api.ui import router as ui_router


builds_dir = env_path("OPENWRT_BUILDER_BUILDS_DIR")
app = FastAPI(title="OpenWRT Builder", version="v1")

profiles = ProfilesRegistry()
build_queue = BuildQueue(builds_dir / "queue.json")

app.state.profiles_registry = profiles
app.state.lists_registry = ListsRegistry()
app.state.builds_registry = BuildsRegistry(builds_dir, profiles, build_queue)
app.state.build_queue = build_queue
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="/ingress/static"), name="static")
app.mount("/examples", StaticFiles(directory="/usr/share/openwrt-builder/examples"), name="examples")
app.include_router(profiles_router)
app.include_router(files_router)
app.include_router(builds_router)
app.include_router(ui_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
