"""Normalización de encabezados de examen.

"SEGUNDO EXAMEN DE INGRESO 1-2012"              -> ("Segundo examen de ingreso 1-2012", "Segunda opción", 2012)
"EXAMEN DE INGRESO 2-2020 (ÚNICA OPCIÓN) VIRTUAL" -> ("Examen de ingreso 2-2020 (única opción) virtual", "Única opción", 2020)
"PRIMER PARCIAL 1-2024 (PRE-U)"                 -> ("Primer parcial 1-2024 (Pre-U)", "1er parcial Pre-U", 2024)
"""

import re
from dataclasses import dataclass

from app.subjects import strip_accents

_ORDINALS = {
    "PRIMER": 1, "PRIMERA": 1, "1ER": 1, "1RA": 1, "1RO": 1, "1": 1,
    "SEGUNDO": 2, "SEGUNDA": 2, "2DO": 2, "2DA": 2, "2": 2,
    "TERCER": 3, "TERCERA": 3, "TERCERO": 3, "3ER": 3, "3RA": 3, "3": 3,
    "CUARTO": 4, "CUARTA": 4, "4TO": 4, "4TA": 4, "4": 4,
}
_PARCIAL_ORD = {1: "1er", 2: "2do", 3: "3er", 4: "4to"}
_OPCION = {1: "Primera opción", 2: "Segunda opción", 3: "Tercera opción"}
_ORD_RE = r"(PRIMER[AO]?|SEGUND[AO]|TERCER[AO]?|CUART[AO]|\d(?:ER|RA|RO|DO|DA|TO|TA)?)"


@dataclass(frozen=True)
class ExamInfo:
    label: str
    type: str
    year: int | None


def _pretty(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw).strip(" .:-–")
    if text.isupper() or sum(c.isupper() for c in text) > len(text) * 0.6:
        text = text.lower()
        text = text[0].upper() + text[1:] if text else text
    text = re.sub(r"\bpre-?u\b", "Pre-U", text, flags=re.I)
    text = re.sub(r"\bumss\b", "UMSS", text, flags=re.I)
    text = re.sub(r"\b(i{1,3}|iv)(?=\s*[/-]\s*\d{4})", lambda m: m.group(1).upper(), text)
    return text[:255]


def parse_exam(raw: str | None) -> ExamInfo | None:
    if not raw or not raw.strip():
        return None
    label = _pretty(raw)
    key = strip_accents(raw).upper()

    year = None
    m = re.search(r"\b(?:[1-4]\s*[-/]\s*)?((?:19|20)\d{2})\b", key)
    if m:
        year = int(m.group(1))

    preu = bool(re.search(r"PRE\s*-?\s*U|PREUNIVERSITARIO|PREFACULTATIVO", key))
    if "PARCIAL" in key:
        m = re.search(_ORD_RE + r"\s+PARCIAL", key) or re.search(r"PARCIAL\s+(?:N[°O.]?\s*)?" + _ORD_RE, key)
        n = _ORDINALS.get(m.group(1)) if m else None
        etype = f"{_PARCIAL_ORD[n]} parcial" if n in _PARCIAL_ORD else "Parcial"
        if preu:
            etype += " Pre-U"
    elif "UNICA OPCION" in key:
        etype = "Única opción"
    elif m := re.search(_ORD_RE + r"\s+OPCION", key):
        etype = _OPCION.get(_ORDINALS.get(m.group(1), 0), "Examen de ingreso")
    elif m := re.search(_ORD_RE + r"\s+EXAMEN", key):
        etype = _OPCION.get(_ORDINALS.get(m.group(1), 0), "Examen de ingreso")
    elif "INGRESO" in key or "ADMISION" in key:
        etype = "Examen de ingreso"
    elif "MODELO" in key or "SIMULACRO" in key or "PRACTICA" in key:
        etype = "Modelo / práctica"
    else:
        etype = "Otro"
    return ExamInfo(label=label, type=etype, year=year)
