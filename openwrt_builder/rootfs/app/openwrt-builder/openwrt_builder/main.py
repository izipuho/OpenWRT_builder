import os
from pathlib import Path

from fastapi import FastAPI
import uvicorn
from openwrt_builder.api.v1.profiles import router
from openwrt_builder.service.registry import Registry

app = FastAPI(title="OpenWRT Builder", version="v1")
app.state.profiles = Profiles(Path(os.environ["OPENWRT_BUILDER_PROFILES_DIR"]))
app.state.lists = Lists(Path(os.environ["OPENWRT_BUILDER_LISTS_DIR"]))
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
