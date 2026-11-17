"""Normalización de nombres de materias y utilidades de texto."""

import re
import unicodedata

SUBJECT_ALIASES: dict[str, str] = {
    "FISICA": "FISICA",
    "QUIMICA": "QUIMICA",
    "BIOLOGIA": "BIOLOGIA",
    "ARITMETICA": "ARITMETICA",
    "ALGEBRA": "ALGEBRA",
    "GEOMETRIA": "GEOMETRIA",
    "TRIGONOMETRIA": "TRIGONOMETRIA",
    "RAZ_MATEMATICO": "RAZONAMIENTO_MATEMATICO",
    "RM": "RAZONAMIENTO_MATEMATICO",
    "RAZONAMIENTO_MATEMATICO": "RAZONAMIENTO_MATEMATICO",
    "RAZ_VERBAL": "RAZONAMIENTO_VERBAL",
    "RV": "RAZONAMIENTO_VERBAL",
    "RAZONAMIENTO_VERBAL": "RAZONAMIENTO_VERBAL",
    "LENGUAJE": "LENGUAJE",
    "LENGUA": "LENGUAJE",
    "LITERATURA": "LITERATURA",
    "HISTORIA": "HISTORIA",
    "HISTORIA_DEL_PERU": "HISTORIA",
    "HISTORIA_UNIVERSAL": "HISTORIA",
    "GEOGRAFIA": "GEOGRAFIA",
    "ECONOMIA": "ECONOMIA",
    "FILOSOFIA": "FILOSOFIA",
    "PSICOLOGIA": "PSICOLOGIA",
    "EDUCACION_CIVICA": "EDUCACION_CIVICA",
    "CIVICA": "EDUCACION_CIVICA",
    "ANATOMIA": "ANATOMIA",
    "INGLES": "INGLES",
}

UNCLASSIFIED = "SIN_CLASIFICAR"


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def normalize_subject(raw: str | None) -> str | None:
    """'Física' / 'FÍSICA I' / 'física' -> 'FISICA'. Devuelve None si está vacío."""
    if not raw:
        return None
    key = strip_accents(raw).upper()
    key = re.sub(r"[^A-Z0-9]+", "_", key).strip("_")
    # Quita prefijos de encabezado tipo "ÁREA DE ÁLGEBRA", "CURSO: FÍSICA"
    key = re.sub(r"^(?:AREA|CURSO|ASIGNATURA|MATERIA)_(?:(?:DE|DEL|DE_LA)_)?", "", key)
    # Quita sufijos de numeración tipo "FISICA_I", "ALGEBRA_2"
    key = re.sub(r"_(?:[IVX]+|\d+)$", "", key)
    if not key:
        return None
    if key in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[key]
    for alias, canonical in SUBJECT_ALIASES.items():
        if key.startswith(alias + "_"):
            return canonical
    return key[:64]


def clean_topic(raw: str | None) -> str:
    topic = re.sub(r"\s+", " ", (raw or "").strip()).strip(" .:-")
    if not topic:
        return "General"
    return (topic[0].upper() + topic[1:])[:255]


# Secuencias que suelen aparecer cuando el modelo no escapa bien las barras
# invertidas de LaTeX dentro del JSON: "\frac" -> "\x0c" + "rac", etc.
_CONTROL_FIXES = {"\x0c": "\\f", "\x08": "\\b", "\x07": "\\a", "\x0b": "\\v"}
_MATH_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$)", re.S)


def repair_latex(text: str | None) -> str:
    if not text:
        return ""
    for bad, good in _CONTROL_FIXES.items():
        text = text.replace(bad, good)

    def fix_math(match: re.Match[str]) -> str:
        seg = match.group(0)
        seg = re.sub(r"\t(?=[a-zA-Z])", r"\\t", seg)  # \times, \theta, \tan
        seg = re.sub(r"\r(?=[a-zA-Z])", r"\\r", seg)  # \rho, \right
        seg = re.sub(r"\n(?=(?:eq|abla|eg|otin|ewline|u\b|i\b|e\b))", r"\\n", seg)  # \neq, \nabla, \nu
        return seg

    return _MATH_RE.sub(fix_math, text).strip()
