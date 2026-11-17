import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import async_engine
from app.routers import documents, questions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

# En producción el volumen de almacenamiento es de solo lectura: no intentar crear carpetas.
for _dir in (settings.pdf_dir, settings.pages_dir):
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

# En producción (solo lectura) no se publica la documentación interactiva de la API.
_docs = {} if settings.allow_uploads else {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="BancoPreu API",
    version="1.0.0",
    description="Extracción y búsqueda de preguntas de bancos universitarios en PDF.",
    **_docs,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(questions.router)


@app.get("/api/health", tags=["system"])
async def health() -> dict:
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "gemini_configured": bool(settings.api_keys),
        "gemini_keys": len(settings.api_keys),
        "openrouter_configured": bool(settings.openrouter_api_key),
        "nvidia_configured": bool(settings.nvidia_api_key),
        "allow_uploads": settings.allow_uploads,
        "expose_pdf": settings.expose_pdf,
    }


if settings.expose_pdf:
    # PDFs originales y PNG de cada página: /storage/pdfs/..., /storage/pages/{doc_id}/page_{n}.png
    app.mount("/storage", StaticFiles(directory=settings.storage_dir), name="storage")
else:
    # Producción: solo las imágenes de las páginas; /storage/pdfs/... responde 404.
    app.mount("/storage/pages", StaticFiles(directory=settings.pages_dir, check_dir=False), name="pages")
