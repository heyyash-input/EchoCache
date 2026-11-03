from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.config import ROOT, Settings
from app.llm import ProviderError
from app.models import ChatRequest, ChatResponse
from app.service import ChatService
from app.cache import CacheUnavailable


def create_app(settings=None, service=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.chat = service or ChatService(settings or Settings.from_env())
        try:
            app.state.chat.context()
            yield
        finally:
            app.state.chat.close()

    application = FastAPI(title="EchoCache", version="1.0.0", lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @application.exception_handler(CacheUnavailable)
    async def cache_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @application.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    @application.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    @application.get("/health")
    def health(request: Request):
        config = request.app.state.chat.settings
        return {"status": "ok", "configured": bool(config.groq_api_key), "model": config.groq_model, "database": request.app.state.chat.cache.health()}

    @application.get("/api/policies")
    def policies(request: Request):
        text, _, sections = request.app.state.chat.context()
        return {"document": text, "sections": sections}

    @application.get("/api/stats")
    def stats(request: Request):
        return request.app.state.chat.stats()

    @application.delete("/api/cache")
    def clear_cache(request: Request):
        request.app.state.chat.cache.clear()
        return {"cleared": True}

    @application.post("/api/chat", response_model=ChatResponse)
    def chat(body: ChatRequest, request: Request):
        return request.app.state.chat.chat(body)

    return application


app = create_app()
