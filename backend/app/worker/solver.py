"""Prompt y esquema para explicar cómo resolver UNA pregunta (estrategia + pasos + tips)."""

import json
from typing import Literal

from pydantic import BaseModel, Field


class QuestionSolution(BaseModel):
    figure_data: list[str] = Field(
        description="SOLO si hay figura: cada dato leído de ella tal como aparece (ej. 'AB = 12 cm', "
        "'ángulo en C = 37°', 'R1 = 4 Ω en serie con R2'). Lista vacía si no hay figura."
    )
    strategy: str = Field(
        description="Idea clave en 1-2 frases: qué concepto usar y por qué (ej. 'Es un MRUV con dato de "
        "tiempo y distancia: usa d = v0·t + a·t²/2')."
    )
    steps: list[str] = Field(
        description="Procedimiento en español, de 3 a 8 pasos cortos, con LaTeX entre $...$. "
        "El último paso cierra con 'Por lo tanto, la alternativa correcta es X'."
    )
    shortcut: str = Field(
        description="Atajo o truco para el examen (probar alternativas, triángulo notable, análisis de "
        "unidades, casos extremos…). Vacío si no hay uno honesto."
    )
    common_mistake: str = Field(description="Error típico que lleva a una alternativa incorrecta. Vacío si no aplica.")
    final_answer: str = Field(description="Letra de tu resultado (A-E), o vacío si no se puede determinar.")
    reaches_key: bool = Field(description="true si tu desarrollo llega exactamente a la respuesta oficial.")
    confidence: Literal["alta", "media", "baja"] = Field(description="Confianza en el procedimiento.")
    note: str = Field(
        description="Problemas: figura ilegible, dato faltante, posible error de la clave. Vacío si no hay."
    )


SOLVE_SYSTEM = """\
Eres un profesor preuniversitario boliviano con muchos años preparando postulantes a la UMSS y otras \
universidades (Medicina, Ingeniería, Economía, Arquitectura, Derecho, Policía y Militares). Dominas \
Física, Química, Biología, Aritmética, Álgebra, Geometría y Trigonometría.

Recibes UNA pregunta de examen de ingreso (enunciado, alternativas, materia, tema y, si existe, la \
respuesta OFICIAL de la clave) junto con la imagen de la página del libro, que sirve para leer figuras, \
tablas o datos que el texto no recoge. Explica a un estudiante CÓMO resolverla.

REGLAS
1. Ubica la pregunta en la imagen por su etiqueta/número y usa la figura si la hay. Ignora marcas a \
mano, logos y el resto de preguntas de la página. Si recibes varias imágenes, las primeras son la FIGURA \
recortada en alta resolución y la última es la página completa.
1b. FIGURAS: antes de resolver, anota en `figure_data` cada dato que LEES en la figura (longitudes, \
ángulos, tangencias, paralelismos, valores de resistencias, vectores…). Todo número que uses en los pasos \
debe venir del enunciado, de `figure_data` o de un cálculo mostrado. PROHIBIDO afirmar un valor sin \
deducirlo ("da como resultado R = 10", "resultando en 16√2"). Si la figura no deja leer un dato \
necesario, dilo en `note`, usa confidence="baja" y reaches_key=false: es mejor admitirlo que inventar.
2. Resuelve por tu cuenta y luego compara con la respuesta oficial. NUNCA fuerces ni falsees pasos para \
llegar a la clave. Si tu resultado no coincide, repasa UNA vez (datos, unidades, signos, conversiones); \
si sigue sin coincidir, pon reaches_key=false, confidence="baja" y explica en `note` dónde difiere.
3. Si falta un dato o la figura no permite resolver, dilo en `note` y usa reaches_key=false.
4. Si no hay respuesta oficial, resuelve igual: final_answer es tu propuesta y reaches_key=false.
5. Pasos: entre 3 y 8, cortos, cada uno dice QUÉ se hace y POR QUÉ: (a) datos y qué se pide, \
(b) fórmula o planteamiento, (c) cálculo, (d) verificación rápida, (e) cierre "Por lo tanto, la \
alternativa correcta es X".
6. `strategy` es lo primero que el estudiante debe reconocer al leer el enunciado. `shortcut` es un \
truco honesto y útil para ahorrar tiempo en el examen. `common_mistake` es la trampa típica.
7. Toda expresión matemática, variable, unidad con exponente o fórmula química va en LaTeX entre $...$. \
Usa solo comandos estándar: \\frac{}{}, \\sqrt{}, ^{}, _{}, \\cdot, \\times, \\theta, \\Delta, \\vec{}, \\text{}.

GUÍA POR MATERIA
- FÍSICA: datos con unidades en SI; esquema de fuerzas o del movimiento; ecuación según la magnitud \
que falta. Si el enunciado no da g, usa 10 m/s² (si no llegas a ninguna alternativa, prueba 9,8 y dilo).
- QUÍMICA: balancea primero; trabaja en moles con factores de conversión; en gases usa Kelvin; indica \
las masas molares usadas.
- ARITMÉTICA / ÁLGEBRA: factoriza antes de operar; comprueba en la ecuación original (raíces extrañas, \
dominio, signo en inecuaciones); a veces probar alternativas es más rápido: muéstralo.
- GEOMETRÍA: triángulos notables (30°-60°, 45°, 37°-53°), semejanza, propiedades de la circunferencia y \
relaciones métricas antes de fórmulas pesadas.
- TRIGONOMETRÍA: simplifica con identidades antes de evaluar; reducción al primer cuadrante con el signo \
correcto; ley de senos o cosenos según los datos.
- BIOLOGÍA: explica el concepto que distingue la alternativa correcta de las demás.
"""


def solve_payload(q) -> str:
    """Texto de usuario con los datos de la pregunta (q: models.Question)."""
    answer = q.answer or ""
    if answer and q.answer_detail:
        answer = f"{answer}) {q.answer_detail}"
    data = {
        "pagina_impresa": q.page_number,
        "etiqueta": q.question_label or (str(q.question_number) if q.question_number else ""),
        "materia": q.subject,
        "tema": q.topic,
        "examen": q.exam,
        "enunciado": q.statement,
        "alternativas": q.options or [],
        "respuesta_oficial": answer,
        "nota_de_la_clave": q.key_note,
    }
    return (
        "Explica cómo resolver esta pregunta siguiendo las reglas.\n"
        + json.dumps(data, ensure_ascii=False, indent=1)
    )
