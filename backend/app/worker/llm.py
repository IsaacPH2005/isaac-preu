"""Multiplexor de proveedores de IA: reparte las páginas entre Gemini y OpenRouter.

Cada solicitud va al siguiente proveedor con cuota (round-robin). Cuando uno agota su
cuota diaria se marca en Redis y el resto sigue trabajando. Solo si TODOS se quedan
sin cuota se pausa el documento (y se puede reanudar después).
"""

import itertools
import logging
import threading
from typing import Protocol

from app.config import settings
from app.worker.gemini import (
    GeminiClient,
    PageExtraction,
    ProviderExhausted,
    ProviderNotConfigured,
    fatal_error_message,
)
from app.worker.openrouter import NvidiaClient, OpenRouterClient

logger = logging.getLogger(__name__)

PROVIDER_LABELS = {"gemini": "Gemini", "openrouter": "OpenRouter", "nvidia": "NVIDIA"}


class Provider(Protocol):
    name: str

    def has_capacity(self) -> bool: ...
    def extract_page(self, image_bytes: bytes, page_number: int) -> PageExtraction: ...
    def group_topics(self, subject: str, topics: list[str], existing: list[str]) -> dict[str, str]: ...
    def solve_question(self, images: list[bytes], prompt: str, patient: bool = False): ...


class AllProvidersExhausted(ProviderExhausted):
    pass


_FACTORIES = {"gemini": GeminiClient, "openrouter": OpenRouterClient, "nvidia": NvidiaClient}


class ExtractionClient:
    def __init__(self) -> None:
        self.providers: list[Provider] = []
        for name in settings.llm_provider_list:
            factory = _FACTORIES.get(name)
            if factory is None:
                logger.warning("Proveedor desconocido en LLM_PROVIDERS: %s", name)
                continue
            try:
                self.providers.append(factory())
            except ProviderNotConfigured:
                continue
        if not self.providers:
            raise ProviderNotConfigured(
                "No hay ningún proveedor de IA configurado: añade GEMINI_API_KEY u "
                "OPENROUTER_API_KEY al archivo .env y reinicia el worker."
            )
        self._rr = itertools.count()
        self._lock = threading.Lock()
        logger.info("Proveedores de IA activos: %s", ", ".join(p.name for p in self.providers))

    def _labels(self) -> str:
        return ", ".join(PROVIDER_LABELS.get(p.name, p.name) for p in self.providers)

    def _pick(self) -> Provider:
        with self._lock:
            available = [p for p in self.providers if p.has_capacity()]
            if not available:
                raise AllProvidersExhausted(
                    f"Se agotó la cuota diaria gratuita de todos los proveedores ({self._labels()}). "
                    "Las páginas ya procesadas se conservan: pulsa «Reanudar» cuando se renueve la "
                    "cuota (Gemini a medianoche hora del Pacífico; OpenRouter a las 00:00 UTC; si NVIDIA rechaza la clave se reintenta en 1 hora)."
                )
            return available[next(self._rr) % len(available)]

    def _dispatch(self, method: str, *args):
        while True:
            provider = self._pick()
            try:
                return getattr(provider, method)(*args)
            except ProviderExhausted:
                continue  # el proveedor ya se marcó como agotado; probar otro
            except Exception as exc:
                # Error permanente de un proveedor (modelo inexistente, clave inválida):
                # si hay otros, se descarta este y se sigue.
                fatal = fatal_error_message(exc) if provider.name == "gemini" else None
                if fatal and len(self.providers) > 1:
                    logger.error("Se desactiva %s: %s", provider.name, fatal)
                    with self._lock:
                        if provider in self.providers:
                            self.providers.remove(provider)
                    continue
                raise

    def extract_page(self, image_bytes: bytes, page_number: int) -> PageExtraction:
        return self._dispatch("extract_page", image_bytes, page_number)

    def group_topics(self, subject: str, topics: list[str], existing: list[str]) -> dict[str, str]:
        return self._dispatch("group_topics", subject, topics, existing)

    def solve_question(self, images: list[bytes], prompt: str, needs_vision: bool = False):
        """
        Interactivo: si un proveedor falla o está saturado, se prueba enseguida el siguiente.
        needs_vision=True (pregunta con figura): solo Gemini, que lee figuras con fiabilidad; los modelos
        gratuitos de respaldo tienden a inventar medidas.
        """
        by_name = {p.name: p for p in self.providers}
        if needs_vision:
            providers = [by_name[n] for n in settings.solver_vision_provider_list if n in by_name]
            if not providers:
                raise ProviderNotConfigured(
                    "Ningún proveedor de SOLVER_VISION_PROVIDERS está configurado para preguntas con figura"
                )
        elif settings.solver_provider_list:
            providers = [by_name[n] for n in settings.solver_provider_list if n in by_name] or list(self.providers)
        else:
            with self._lock:
                start = next(self._rr) % len(self.providers)
            providers = self.providers[start:] + self.providers[:start]
        last: Exception | None = None
        for i, provider in enumerate(providers):
            if not provider.has_capacity():
                continue
            try:
                # El último proveedor disponible insiste más (nadie más puede responder)
                return provider.solve_question(images, prompt, patient=i == len(providers) - 1)
            except Exception as exc:
                logger.warning("%s no pudo resolver la pregunta (%s); se prueba otro proveedor", provider.name, exc)
                last = exc
        if last is None:
            raise AllProvidersExhausted(f"Sin cuota disponible en ningún proveedor ({self._labels()})")
        raise last
