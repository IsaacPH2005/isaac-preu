"""Cliente de Gemini Vision con Structured Outputs para extraer preguntas."""

import hashlib
import itertools
import json
import logging
import random
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import redis
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import settings

logger = logging.getLogger(__name__)


# ─── Esquemas de salida (JSON Schema estricto para Gemini) ──────────────────


class ExtractedQuestion(BaseModel):
    label: str = Field(
        description=(
            "Etiqueta impresa de la pregunta tal cual, sin el punto ni el guion final "
            "(ej. '5', 'A1', 'G3', 'F12', 'Q-13', 'B2'). Cadena vacía si no tiene."
        )
    )
    number: int = Field(
        description=(
            "Número impreso en la etiqueta ('G3' -> 3, 'Q-13' -> 13, '5' -> 5). NO renumeres: si las "
            "etiquetas reinician por materia (A1, A2, G1, G2…), respeta ese número. 0 si no tiene."
        )
    )
    subject: str = Field(
        description=(
            "Encabezado de materia que aparece EN ESTA PÁGINA por encima de la pregunta "
            "(ej. FÍSICA, QUÍMICA, ÁLGEBRA). Cadena vacía si en esta página no hay ningún "
            "encabezado de materia antes de la pregunta."
        )
    )
    exam_header: str = Field(
        description=(
            "Título del EXAMEN que aparece EN ESTA PÁGINA por encima de la pregunta, completo y tal cual "
            "(ej. 'SEGUNDO EXAMEN DE INGRESO 1-2012', 'EXAMEN DE INGRESO 2-2020 (ÚNICA OPCIÓN) VIRTUAL - "
            "MODELO 1', 'PRIMER PARCIAL 1-2024 (PRE-U)'). Cadena vacía si en esta página no hay un "
            "título de examen antes de la pregunta."
        )
    )
    topic: str = Field(
        description=(
            "Tema específico en español, normalizado, en forma de sustantivo y con mayúscula "
            "inicial (ej. 'División de polinomios', 'Plano inclinado', 'Estequiometría')."
        )
    )
    statement: str = Field(
        description="Enunciado completo. Toda expresión matemática en LaTeX entre $...$ (en línea) o $$...$$ (bloque)."
    )
    options: list[str] = Field(
        description="Alternativas en orden, cada una con su letra: 'a) ...', 'b) ...'. Lista vacía si no tiene."
    )
    has_diagram: bool = Field(
        description="true si la pregunta incluye o depende de una figura, gráfico, diagrama, tabla dibujada o esquema."
    )
    figure_box: list[int] = Field(
        description=(
            "Si has_diagram es true: caja de la figura de ESTA pregunta en la imagen como "
            "[ymin, xmin, ymax, xmax] normalizada de 0 a 1000 (incluye rótulos y medidas de la figura, "
            "no el enunciado ni las alternativas). Lista vacía si no hay figura."
        )
    )


class PageExtraction(BaseModel):
    continuation_text: str = Field(
        description=(
            "Si la página EMPIEZA con el final de una pregunta iniciada en la página anterior "
            "(texto u opciones sin número propio), ese texto. Cadena vacía si no."
        )
    )
    continuation_options: list[str] = Field(
        description="Opciones que pertenecen a esa pregunta de la página anterior. Lista vacía si no hay."
    )
    continuation_has_diagram: bool = Field(
        description="true si el fragmento de continuación contiene una figura o diagrama."
    )
    questions: list[ExtractedQuestion] = Field(
        description="Preguntas que COMIENZAN en esta página, en orden de lectura."
    )


class TopicMapping(BaseModel):
    original: str
    canonical: str


class TopicGrouping(BaseModel):
    mappings: list[TopicMapping]


# ─── Prompts ────────────────────────────────────────────────────────────────

EXTRACTION_SYSTEM = """\
Eres un experto en digitalizar bancos de preguntas preuniversitarios peruanos/latinoamericanos \
(Física, Química, Biología, Aritmética, Álgebra, Geometría, Trigonometría, Razonamiento \
Matemático, Lenguaje, etc.). Recibes la imagen de UNA página y devuelves JSON estructurado.

Reglas:
1. Extrae CADA pregunta individual que comienza en esta página, en orden de lectura (si la \
página tiene dos columnas, primero la izquierda completa y luego la derecha).
2. `subject`: solo el encabezado de materia visible en esta página antes de la pregunta \
(títulos como "FÍSICA", "QUÍMICA", "ÁLGEBRA"). Si no hay encabezado visible, cadena vacía; \
el sistema heredará la materia de la página anterior. No inventes la materia a partir del contenido. \
EXCEPCIÓN: si el encabezado agrupa dos materias ("ARITMÉTICA – ÁLGEBRA", "GEOMETRÍA – TRIGONOMETRÍA"), \
devuelve en CADA pregunta de esa sección la materia concreta según su contenido (ARITMÉTICA o ÁLGEBRA; \
GEOMETRÍA o TRIGONOMETRÍA), nunca el encabezado combinado.
2b. `exam_header`: si en la página hay un título de examen (universidad/facultad a un lado y \
"EXAMEN DE INGRESO…", "PRIMER PARCIAL…", "SEGUNDO EXAMEN…", gestión "1-2012", "(ÚNICA OPCIÓN)", \
"MODELO 1"…), ponlo completo en la PRIMERA pregunta que aparece debajo de él, uniendo sus partes en \
una sola línea (ej. "EXAMEN DE INGRESO 2-2020 (ÚNICA OPCIÓN) VIRTUAL - MODELO 1"). No incluyas el \
nombre de la universidad ni la fecha. En las demás preguntas, cadena vacía; el sistema lo hereda.
3. `topic`: clasifica el tema específico en español, conciso (2-5 palabras), con mayúscula \
inicial y usando la denominación más estándar del curso (ej. "Ecuaciones cuadráticas", \
"Cinemática", "MRUV", "Leyes de Newton", "Estequiometría", "Genética mendeliana").
4. `statement`: transcribe fielmente el enunciado SIN el número de pregunta y SIN las \
alternativas. Toda fórmula, variable, fracción, potencia, raíz, unidad con exponente o \
símbolo matemático va en LaTeX válido entre $...$ (o $$...$$ para ecuaciones destacadas). \
Usa comandos estándar: \\frac{}{}, \\sqrt{}, ^{}, _{}, \\cdot, \\times, \\alpha, \\theta, \\Delta, \\vec{}, \\text{}.
5. `options`: cada alternativa como "a) ...", "b) ..." con LaTeX entre $...$ cuando aplique.
6. `has_diagram`: true si hay figura, gráfico, diagrama, plano cartesiano, circuito, \
estructura química dibujada o tabla gráfica asociada a la pregunta.
7. Si la página empieza con el final de una pregunta de la página anterior (texto sin número, \
o una fila de alternativas a), b), c)… sueltas antes de la primera pregunta numerada), ponlo en \
`continuation_text` / `continuation_options` y NO lo incluyas en `questions`. Toda entrada de \
`questions` debe tener un enunciado real.
8. Ignora encabezados de página, pies de página, logos, números de página, claves de \
respuestas y solucionarios. Si la página no contiene preguntas (portada, índice, \
solucionario), devuelve `questions` vacío.
"""

EXTRACTION_PROMPT = "Página {page} del documento. Extrae las preguntas siguiendo las reglas."

TOPIC_SYSTEM = """\
Eres un docente preuniversitario que organiza el catálogo de temas de la materia {subject} \
para que los estudiantes puedan filtrar preguntas por tema.
Recibirás una lista de nombres de temas (muchos son subtemas o variantes). Asigna a CADA uno \
un tema canónico a nivel de UNIDAD del sílabo preuniversitario:
- Une sinónimos y variantes de redacción, singular/plural y abreviaturas \
(ej. "Herencia mendeliana", "Cruces genéticos" y "Alelos recesivos" → "Genética mendeliana"; \
"Tiro oblicuo" y "Tiro parabólico" → "Movimiento parabólico"; "Adn" y "Bases nitrogenadas del arn" \
→ "Ácidos nucleicos").
- Integra los subtemas muy específicos en su unidad (ej. "Caída libre en semiesfera" → "Caída libre").
- El catálogo final debe tener aproximadamente entre 15 y 40 temas para la materia; evita temas \
que agrupen una sola pregunta salvo que no encajen en ninguna unidad.
- No fusiones unidades que en el curso se estudian por separado (ej. "MRU" y "MRUV", \
"Estática" y "Dinámica", "Mitosis" y "Meiosis").
- Nombres en español, concisos (1-4 palabras), con mayúscula inicial y acentos correctos.
- Si en "temas_canonicos_existentes" hay uno equivalente, úsalo exactamente.
- Devuelve una entrada en `mappings` por CADA tema original recibido (aunque no cambie).
"""


# ─── Cliente ────────────────────────────────────────────────────────────────


class ProviderNotConfigured(RuntimeError):
    """El proveedor de IA no tiene credenciales configuradas."""


# Compatibilidad con el nombre anterior
GeminiNotConfigured = ProviderNotConfigured


class ProviderExhausted(RuntimeError):
    """El proveedor agotó su cuota diaria; el multiplexor pasa al siguiente."""


FATAL_HINTS = {
    400: "Solicitud rechazada por Gemini (revisa GEMINI_MODEL y la configuración)",
    401: "GEMINI_API_KEY inválida",
    403: "GEMINI_API_KEY sin permisos o con la API deshabilitada",
    404: "El modelo configurado en GEMINI_MODEL no está disponible para tu clave",
}


class AllKeysExhausted(ProviderExhausted):
    """Todas las claves configuradas agotaron su cuota diaria."""


def _is_daily_quota(exc: BaseException) -> bool:
    return (
        isinstance(exc, genai_errors.ClientError)
        and getattr(exc, "code", None) == 429
        and "PerDay" in str(exc)
    )


def fatal_error_message(exc: BaseException) -> str | None:
    """Mensaje legible si el error es permanente (no tiene sentido seguir con otras páginas)."""
    if isinstance(exc, AllKeysExhausted) or _is_daily_quota(exc):
        n = len(settings.api_keys)
        quien = "tu clave" if n == 1 else f"tus {n} claves"
        return (
            f"Se agotó la cuota diaria de Gemini ({settings.gemini_model}) en {quien}. Las páginas ya "
            "procesadas se conservan: pulsa «Reanudar» cuando se renueve la cuota "
            "(o activa la facturación en Google AI Studio para límites mayores)."
        )
    if isinstance(exc, genai_errors.ClientError):
        code = getattr(exc, "code", None)
        if code in FATAL_HINTS:
            detail = getattr(exc, "message", None) or str(exc)
            return f"{FATAL_HINTS[code]} [{settings.gemini_model}]: {detail}"[:1500]
    return None


def _is_retryable(exc: BaseException) -> bool:
    if _is_daily_quota(exc):
        return False  # no se recupera reintentando: se pausa el documento
    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        return code in (408, 429, 500, 502, 503, 504) or code is None
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return True  # salida truncada o JSON inválido: reintentar
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))


_RETRY_DELAY_RE = re.compile(r"retry in ([\d.]+)\s*s|'retryDelay': '([\d.]+)s'", re.I)
_exp_wait = wait_exponential_jitter(initial=2, max=60)


def _wait(retry_state) -> float:
    """En un 429 espera exactamente lo que indica Google; si no, backoff exponencial."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc is not None:
        m = _RETRY_DELAY_RE.search(str(exc))
        if m:
            return min(120.0, float(m.group(1) or m.group(2))) + random.uniform(0.5, 3.0)
    return _exp_wait(retry_state)


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    wait=_wait,
    stop=stop_after_attempt(settings.gemini_max_retries),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# Para peticiones interactivas (alguien espera la respuesta): pocos intentos y se pasa a otro proveedor.
_quick_retry = retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(initial=2, max=8),
    stop=stop_after_attempt(2),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


# ─── Limitador de solicitudes por minuto (compartido vía Redis) ─────────────
# Ventana deslizante de 60 s, atómica con Lua: válida entre hilos, procesos y
# documentos simultáneos. Devuelve 0 si hay hueco o los segundos a esperar.
_RATE_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', key, 0, now - 60)
if redis.call('ZCARD', key) < limit then
  redis.call('ZADD', key, now, ARGV[3])
  redis.call('EXPIRE', key, 120)
  return '0'
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
return tostring(tonumber(oldest[2]) + 60 - now)
"""
_redis_client: redis.Redis | None = None
_rate_script = None


def _redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.redis_url)
    return _redis_client


def acquire_rate_slot(bucket: str, rpm: int) -> None:
    """Bloquea hasta que `bucket` tenga hueco dentro de `rpm` solicitudes por minuto."""
    global _rate_script
    if rpm <= 0:
        return
    if _rate_script is None:
        _rate_script = _redis().register_script(_RATE_LUA)
    key = f"bancopreu:rpm:{bucket}"
    while True:
        wait = float(_rate_script(keys=[key], args=[time.time(), rpm, uuid.uuid4().hex]))
        if wait <= 0:
            return
        time.sleep(wait + random.uniform(0.2, 1.0))


def _acquire_slot(key_id: str) -> None:
    acquire_rate_slot(f"gemini:{settings.gemini_model}:{key_id}", settings.gemini_rpm)


def _key_id(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:12]


def _seconds_until_quota_reset() -> int:
    """La cuota diaria de Gemini se renueva a medianoche, hora del Pacífico."""
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    reset = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    return max(60, int((reset - now).total_seconds()))


class GeminiClient:
    """
    Cliente con rotación de claves: reparte las solicitudes entre todas las claves
    configuradas (GEMINI_API_KEY + GEMINI_API_KEYS) y, cuando una agota su cuota
    diaria, la aparta hasta el reinicio de cuota y sigue con las demás.
    """

    name = "gemini"

    def __init__(self) -> None:
        keys = settings.api_keys
        if not keys:
            raise ProviderNotConfigured(
                "GEMINI_API_KEY no está configurada. Añádela al archivo .env y reinicia el worker."
            )
        self.model = settings.gemini_model
        self._clients = {_key_id(k): genai.Client(api_key=k) for k in keys}
        self._order = list(self._clients)
        self._rr = itertools.count()
        self._lock = threading.Lock()

    # ─── Rotación de claves ──────────────────────────────────────────────
    def _exhausted_flag(self, kid: str) -> str:
        return f"bancopreu:gemini:exhausted:{self.model}:{kid}"

    def has_capacity(self) -> bool:
        return any(not _redis().exists(self._exhausted_flag(k)) for k in self._order)

    def _next_key(self) -> str:
        available = [k for k in self._order if not _redis().exists(self._exhausted_flag(k))]
        if not available:
            raise AllKeysExhausted(
                f"Todas las claves ({len(self._order)}) agotaron su cuota diaria de {self.model}"
            )
        with self._lock:
            return available[next(self._rr) % len(available)]

    def _mark_exhausted(self, kid: str) -> None:
        _redis().set(self._exhausted_flag(kid), "1", ex=_seconds_until_quota_reset())
        logger.warning("Clave ...%s agotó su cuota diaria de %s; se usa la siguiente", kid[-4:], self.model)

    def _run(self, contents, config: types.GenerateContentConfig, schema: type[BaseModel]) -> BaseModel:
        while True:
            kid = self._next_key()
            try:
                return self._call(kid, contents, config, schema)
            except Exception as exc:
                if _is_daily_quota(exc):
                    self._mark_exhausted(kid)
                    continue
                raise

    @_retry
    def _call(self, kid: str, contents, config: types.GenerateContentConfig, schema: type[BaseModel]) -> BaseModel:
        _acquire_slot(kid)
        response = self._clients[kid].models.generate_content(
            model=self.model, contents=contents, config=config
        )
        return self._parse(response, schema)

    # ─── Configuración y parseo ──────────────────────────────────────────
    def _config(self, system: str, schema: type[BaseModel], max_tokens: int) -> types.GenerateContentConfig:
        kwargs: dict = dict(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_tokens,
        )
        if "gemini-2" in self.model:
            kwargs["temperature"] = 0.1
            if "2.5" in self.model:
                kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=settings.gemini_thinking_budget
                )
        elif settings.gemini_thinking_level:
            # Gemini 3+: se controla con thinking_level y Google recomienda la temperatura por defecto.
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=settings.gemini_thinking_level)
        return types.GenerateContentConfig(**kwargs)

    @staticmethod
    def _parse(response: types.GenerateContentResponse, schema: type[BaseModel]) -> BaseModel:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        text = response.text or ""
        if not text.strip():
            raise ValueError("Respuesta vacía de Gemini")
        return schema.model_validate_json(text)

    # ─── API pública ─────────────────────────────────────────────────────
    def extract_page(self, image_bytes: bytes, page_number: int) -> PageExtraction:
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            EXTRACTION_PROMPT.format(page=page_number),
        ]
        config = self._config(EXTRACTION_SYSTEM, PageExtraction, max_tokens=16384)
        return self._run(contents, config, PageExtraction)  # type: ignore[return-value]

    def solve_question(self, images: list[bytes], prompt: str, patient: bool = False):
        from app.worker.solver import SOLVE_SYSTEM, QuestionSolution

        contents: list = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images]
        contents.append(prompt)
        config = self._config(SOLVE_SYSTEM, QuestionSolution, max_tokens=8192)
        if patient:  # pregunta con figura: solo Gemini, así que se insiste más
            return self._run(contents, config, QuestionSolution)
        kid = self._next_key()
        try:
            return self._call_quick(kid, contents, config, QuestionSolution)
        except Exception as exc:
            if _is_daily_quota(exc):
                self._mark_exhausted(kid)
            raise

    @_quick_retry
    def _call_quick(self, kid: str, contents, config: types.GenerateContentConfig, schema: type[BaseModel]) -> BaseModel:
        _acquire_slot(kid)
        response = self._clients[kid].models.generate_content(model=self.model, contents=contents, config=config)
        return self._parse(response, schema)

    def group_topics(self, subject: str, topics: list[str], existing: list[str]) -> dict[str, str]:
        payload = {"temas_canonicos_existentes": existing, "temas_a_normalizar": topics}
        config = self._config(TOPIC_SYSTEM.format(subject=subject), TopicGrouping, max_tokens=16384)
        result: TopicGrouping = self._run(json.dumps(payload, ensure_ascii=False), config, TopicGrouping)  # type: ignore[assignment]
        valid = set(topics)
        return {
            m.original: m.canonical.strip()
            for m in result.mappings
            if m.original in valid and m.canonical.strip()
        }
