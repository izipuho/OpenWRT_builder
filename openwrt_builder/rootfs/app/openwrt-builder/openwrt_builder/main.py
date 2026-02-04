from fastapi import FastAPI
from openwrt_builder.api.v1.profiles import router
from openwrt_builder.service.registry import Registry

app = FastAPI(title="OpenWRT Builder", version="v1")
app.state.registry = Registry()
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)