"""Proveedores con API compatible con OpenAI (OpenRouter, NVIDIA NIM) con cadena de modelos de respaldo."""

import base64
import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import settings
from app.worker.gemini import (
    EXTRACTION_PROMPT,
    EXTRACTION_SYSTEM,
    TOPIC_SYSTEM,
    PageExtraction,
    ProviderExhausted,
    ProviderNotConfigured,
    TopicGrouping,
    _redis,
    acquire_rate_slot,
)

logger = logging.getLogger(__name__)


class _Retryable(Exception):
    """Error transitorio (límite por minuto, 5xx, JSON inválido): reintentar el mismo modelo."""


class _ModelUnavailable(Exception):
    """El modelo no está disponible ahora (saturado, retirado, no existe…): probar el siguiente."""


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    reset = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    return max(60, int((reset - now).total_seconds()))


def _extract_json(text: str) -> str:
    s = (text or "").strip()
    if "</think>" in s:  # modelos de razonamiento que devuelven su pensamiento
        s = s.rsplit("</think>", 1)[1]
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        s = s.rsplit("```", 1)[0]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise _Retryable("La respuesta no contiene JSON")
    return s[start : end + 1]


def _schema_instructions(schema: type[BaseModel]) -> str:
    return (
        "\n\nResponde ÚNICAMENTE con un objeto JSON válido (sin texto adicional ni bloques de código) "
        "que cumpla exactamente este JSON Schema. En las cadenas JSON, escapa cada barra invertida "
        "de LaTeX como \\\\ (ej. \"\\\\frac{a}{b}\").\n"
        + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    )


class OpenAICompatClient:
    """Base para APIs /chat/completions compatibles con OpenAI."""

    name = "openai-compat"
    label = "API"
    api_url = ""
    # "json_object" | "json_schema" (salida guiada por el esquema) | "" (solo instrucciones en el prompt)
    json_mode = "json_object"
    extra_body: dict = {}  # parámetros adicionales específicos del proveedor

    def __init__(self, api_key: str, models: list[str], rpm: int) -> None:
        if not api_key:
            raise ProviderNotConfigured(f"{self.label}: falta la clave de API")
        if not models:
            raise ProviderNotConfigured(f"{self.label}: no hay modelos configurados")
        self.models = models
        self.rpm = rpm
        self._key_id = hashlib.sha256(api_key.encode()).hexdigest()[:12]
        self._http = httpx.Client(
            timeout=httpx.Timeout(300.0, connect=20.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                **self.extra_headers(),
            },
        )
        self._cooldown: dict[str, float] = {}
        self._lock = threading.Lock()

    # ─── Hooks por proveedor ─────────────────────────────────────────────
    def extra_headers(self) -> dict[str, str]:
        return {}

    def is_daily_limit(self, status: int, text_lower: str) -> bool:
        return False

    def quota_reset_seconds(self) -> int:
        return _seconds_until_utc_midnight()

    # ─── Cuota ───────────────────────────────────────────────────────────
    @property
    def _flag(self) -> str:
        return f"bancopreu:{self.name}:exhausted:{self._key_id}"

    def has_capacity(self) -> bool:
        return not _redis().exists(self._flag)

    def _mark_exhausted(self, reason: str, ttl: int | None = None) -> None:
        _redis().set(self._flag, "1", ex=ttl or self.quota_reset_seconds())
        logger.warning("%s sin servicio (%s); se usará otro proveedor", self.label, reason)

    # ─── Llamada a un modelo concreto ────────────────────────────────────
    @retry(
        retry=retry_if_exception_type(_Retryable),
        wait=wait_exponential_jitter(initial=3, max=60),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call_model(self, model: str, messages: list, schema: type[BaseModel]) -> BaseModel:
        acquire_rate_slot(f"{self.name}:{self._key_id}", self.rpm)
        body: dict = {"model": model, "messages": messages, "max_tokens": 16000, "temperature": 0.1}
        if self.json_mode == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            }
        elif self.json_mode == "json_object":
            body["response_format"] = {"type": "json_object"}
        body.update(self.extra_body)
        try:
            r = self._http.post(self.api_url, json=body)
        except httpx.HTTPError as exc:
            raise _Retryable(f"Error de red: {exc}") from exc

        text = r.text
        lower = text.lower()
        if r.status_code == 429:
            if self.is_daily_limit(429, lower):
                self._mark_exhausted("límite diario")
                raise ProviderExhausted(f"{self.label} agotó su cupo diario")
            if "upstream" in lower:
                raise _ModelUnavailable(f"{model} saturado aguas arriba")
            raise _Retryable(f"429 límite por minuto ({model})")
        if r.status_code == 402 or self.is_daily_limit(r.status_code, lower):
            self._mark_exhausted("sin créditos o cupo")
            raise ProviderExhausted(f"{self.label}: sin créditos")
        if r.status_code in (401, 403):
            self._mark_exhausted(f"clave rechazada ({r.status_code}: {text[:120]})", ttl=3600)
            raise ProviderExhausted(f"{self.label} rechazó la clave ({r.status_code})")
        if r.status_code in (400, 404, 410, 422):
            raise _ModelUnavailable(f"{model}: {r.status_code} {text[:200]}")
        if r.status_code >= 500:
            raise _Retryable(f"{r.status_code} en {model}")

        try:
            data = r.json()
        except ValueError as exc:
            raise _Retryable(f"Respuesta no JSON de {self.label}") from exc
        if "error" in data and not data.get("choices"):
            err = json.dumps(data["error"], ensure_ascii=False)
            if "upstream" in err.lower() or "rate" in err.lower():
                raise _ModelUnavailable(f"{model}: {err[:200]}")
            raise _Retryable(f"{model}: {err[:200]}")
        try:
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise _Retryable("Respuesta sin contenido") from exc
        if choice.get("finish_reason") == "length":
            raise _Retryable(f"{model}: respuesta truncada")
        try:
            return schema.model_validate_json(_extract_json(content))
        except _Retryable:
            raise
        except Exception as exc:  # JSON inválido o que no cumple el esquema
            raise _Retryable(f"{model}: JSON inválido ({exc.__class__.__name__})") from exc

    def _complete(self, messages: list, schema: type[BaseModel]) -> BaseModel:
        if not self.has_capacity():
            raise ProviderExhausted(f"{self.label} sin cuota")
        last_error: Exception | None = None
        for model in self.models:
            with self._lock:
                if self._cooldown.get(model, 0) > time.time():
                    continue
            try:
                return self._call_model(model, messages, schema)
            except _ModelUnavailable as exc:
                logger.warning("%s: %s; probando el siguiente modelo", self.label, exc)
                with self._lock:
                    self._cooldown[model] = time.time() + 90
                last_error = exc
            except _Retryable as exc:
                logger.warning("%s: %s tras varios intentos; siguiente modelo", self.label, exc)
                last_error = exc
        raise RuntimeError(f"Ningún modelo de {self.label} respondió: {last_error}")

    # ─── API pública (misma interfaz que GeminiClient) ───────────────────
    def extract_page(self, image_bytes: bytes, page_number: int) -> PageExtraction:
        img = base64.b64encode(image_bytes).decode()
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM + _schema_instructions(PageExtraction)},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT.format(page=page_number)},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                ],
            },
        ]
        return self._complete(messages, PageExtraction)  # type: ignore[return-value]

    def solve_question(self, images: list[bytes], prompt: str, patient: bool = False):
        from app.worker.solver import SOLVE_SYSTEM, QuestionSolution

        content: list = [{"type": "text", "text": prompt}]
        for raw in images:
            img = base64.b64encode(raw).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
        messages = [
            {"role": "system", "content": SOLVE_SYSTEM + _schema_instructions(QuestionSolution)},
            {"role": "user", "content": content},
        ]
        return self._complete(messages, QuestionSolution)

    def group_topics(self, subject: str, topics: list[str], existing: list[str]) -> dict[str, str]:
        payload = {"temas_canonicos_existentes": existing, "temas_a_normalizar": topics}
        messages = [
            {"role": "system", "content": TOPIC_SYSTEM.format(subject=subject) + _schema_instructions(TopicGrouping)},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        result: TopicGrouping = self._complete(messages, TopicGrouping)  # type: ignore[assignment]
        valid = set(topics)
        return {
            m.original: m.canonical.strip()
            for m in result.mappings
            if m.original in valid and m.canonical.strip()
        }


class OpenRouterClient(OpenAICompatClient):
    """OpenRouter: 50 solicitudes/día gratis con modelos :free (1000/día con ≥10 USD de crédito)."""

    name = "openrouter"
    label = "OpenRouter"
    api_url = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self) -> None:
        super().__init__(settings.openrouter_api_key, settings.openrouter_model_list, settings.openrouter_rpm)

    def extra_headers(self) -> dict[str, str]:
        return {"X-Title": "BancoPreu"}

    def is_daily_limit(self, status: int, text_lower: str) -> bool:
        return status == 429 and ("per-day" in text_lower or "per day" in text_lower)


class NvidiaClient(OpenAICompatClient):
    """NVIDIA NIM (build.nvidia.com): créditos gratuitos y ~40 solicitudes/min."""

    name = "nvidia"
    label = "NVIDIA"
    api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    # Salida guiada por JSON Schema: evita JSON mal formado (claves omitidas) del modelo.
    json_mode = "json_schema"
    # Nemotron razona por defecto: desactivarlo es más rápido y gasta menos créditos.
    extra_body = {"chat_template_kwargs": {"enable_thinking": False}}

    def __init__(self) -> None:
        super().__init__(settings.nvidia_api_key, settings.nvidia_model_list, settings.nvidia_rpm)

    def is_daily_limit(self, status: int, text_lower: str) -> bool:
        return "credit" in text_lower and status in (402, 403, 429)
