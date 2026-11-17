from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_NVIDIA_MODELS = "nvidia/nemotron-3.5-super-vl-120b-a12b,google/gemma-4-31b-it"

DEFAULT_OPENROUTER_MODELS = (
    "nvidia/nemotron-3.5-super-vl:free,google/gemma-4-31b-it:free,"
    "google/gemma-4-26b-a4b-it:free,openrouter/free"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "bancopreu"
    postgres_password: str = "bancopreu"
    postgres_db: str = "bancopreu"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_url: str = "redis://localhost:6379/0"

    storage_dir: str = "/storage"

    gemini_api_key: str = ""
    # Claves adicionales separadas por comas (de proyectos distintos); se rotan al agotar la cuota.
    gemini_api_keys: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_concurrency: int = 4
    gemini_thinking_budget: int = 0  # solo modelos 2.5
    gemini_thinking_level: str = "low"  # modelos 3+: minimal | low | medium | high ("" = por defecto)
    gemini_max_retries: int = 8
    # Límite de solicitudes por minuto a Gemini (plan gratuito = 5). 0 = sin límite.
    gemini_rpm: int = 0

    # OpenRouter (API compatible con OpenAI). Modelos en orden de preferencia; los :free son gratis.
    openrouter_api_key: str = ""
    openrouter_models: str = DEFAULT_OPENROUTER_MODELS
    openrouter_rpm: int = 16  # el plan gratuito permite 20/min
    # NVIDIA NIM (build.nvidia.com)
    nvidia_api_key: str = ""
    nvidia_models: str = DEFAULT_NVIDIA_MODELS
    nvidia_rpm: int = 30  # el plan gratuito permite ~40/min
    # Proveedores que se reparten las páginas (solo se usan los que tengan clave)
    llm_providers: str = "gemini,openrouter,nvidia"

    render_dpi: int = 150
    max_upload_mb: int = 300
    cors_origins: str = "*"
    # false en producción: solo búsqueda; se bloquea subir/reprocesar/eliminar documentos.
    allow_uploads: bool = True
    # false en producción: el PDF original no se sirve (solo las imágenes de cada página).
    expose_pdf: bool = True

    @property
    def api_keys(self) -> list[str]:
        keys = [self.gemini_api_key, *self.gemini_api_keys.split(",")]
        return list(dict.fromkeys(k.strip() for k in keys if k and k.strip()))

    @property
    def openrouter_model_list(self) -> list[str]:
        models = [m.strip() for m in self.openrouter_models.split(",") if m.strip()]
        return models or [m.strip() for m in DEFAULT_OPENROUTER_MODELS.split(",")]

    @property
    def nvidia_model_list(self) -> list[str]:
        models = [m.strip() for m in self.nvidia_models.split(",") if m.strip()]
        return models or [m.strip() for m in DEFAULT_NVIDIA_MODELS.split(",")]

    @property
    def llm_provider_list(self) -> list[str]:
        return [p.strip().lower() for p in self.llm_providers.split(",") if p.strip()]

    @property
    def _db_path(self) -> str:
        return (
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        return f"postgresql+asyncpg://{self._db_path}"

    @property
    def sync_database_url(self) -> str:
        return f"postgresql+psycopg://{self._db_path}"

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir)

    @property
    def pdf_dir(self) -> Path:
        return self.storage_path / "pdfs"

    @property
    def pages_dir(self) -> Path:
        return self.storage_path / "pages"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
