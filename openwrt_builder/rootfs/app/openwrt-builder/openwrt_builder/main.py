"""FastAPI app entrypoint for OpenWRT Builder."""
import os
from pathlib import Path

from fastapi import FastAPI
import uvicorn
from openwrt_builder.api.v1.builds import router as builds_router
from openwrt_builder.api.v1.profiles import router as profiles_router
from openwrt_builder.service.builds_registry import BuildsRegistry
from openwrt_builder.service.build_queue import BuildQueue
from openwrt_builder.service.profiles_registry import ListsRegistry, ProfilesRegistry

BUILDS_DIR = os.environ["OPENWRT_BUILDER_BUILDS_DIR"]

app = FastAPI(title="OpenWRT Builder", version="v1")

profiles = ProfilesRegistry()
build_queue = BuildQueue(Path(BUILDS_DIR) / "queue.json")

app.state.profiles_registry = profiles
app.state.lists_registry = ListsRegistry()
app.state.builds_registry = BuildsRegistry(Path(BUILDS_DIR), profiles, build_queue)
app.state.build_queue = build_queue
app.include_router(profiles_router)
app.include_router(builds_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
