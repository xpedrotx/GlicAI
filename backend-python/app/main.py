from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes import web_api, web_auth, webhook
from app.scheduler import iniciar_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = iniciar_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="GlicAI backend", lifespan=lifespan)

app.include_router(webhook.router)
app.include_router(web_auth.router)
app.include_router(web_api.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
