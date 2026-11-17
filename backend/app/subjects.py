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

    return wrap_bare_math(_MATH_RE.sub(fix_math, text)).strip()


# ─── LaTeX sin delimitar: "a) \frac{R}{9}" -> "a) $\frac{R}{9}$" ─────────────
_DELIMITED_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\(.*?\\\)|\\\[.*?\\\])", re.S)
_MATHY_RE = re.compile(r"\\[a-zA-Z]+|[\^_][{A-Za-z0-9]|[{}]")
_GLUE_RE = re.compile(r"^(?:[0-9.,]+|[A-Za-z]|[=+\-*/·×<>≤≥≈()\[\]|]+|[0-9]*[A-Za-z][0-9]*)$")
_EDGE_PUNCT = "\"'“”«».,;:¿?¡!"


def _is_mathy(tok: str) -> bool:
    return bool(_MATHY_RE.search(tok))


def _is_glue(tok: str) -> bool:
    # "a)" / "b)" son letras de alternativa, no matemática
    if re.fullmatch(r"[A-Ea-e]\)", tok):
        return False
    return bool(_GLUE_RE.match(tok))


def _wrap_plain(text: str) -> str:
    parts = re.split(r"(\s+)", text)
    words = parts[0::2]
    if not any(_is_mathy(w) for w in words):
        return text
    n = len(words)
    in_math = [False] * n
    for i, w in enumerate(words):
        if not _is_mathy(w) or in_math[i]:
            continue
        lo = hi = i
        while lo > 0 and words[lo - 1] and (_is_mathy(words[lo - 1]) or _is_glue(words[lo - 1])):
            lo -= 1
        while hi < n - 1 and words[hi + 1] and (_is_mathy(words[hi + 1]) or _is_glue(words[hi + 1])):
            hi += 1
        # Los operadores sueltos en los bordes quedan fuera ("Área = 360\pi" -> "Área = $360\pi$")
        while lo < i and re.fullmatch(r"[=+\-*/·×<>≤≥≈]+", words[lo]):
            lo += 1
        while hi > i and re.fullmatch(r"[=+\-*/·×<>≤≥≈]+", words[hi]):
            hi -= 1
        for k in range(lo, hi + 1):
            in_math[k] = True

    out: list[str] = []
    k = 0
    while k < n:
        if not in_math[k]:
            out.append(words[k])
            if k < n - 1:
                out.append(parts[2 * k + 1])
            k += 1
            continue
        start = k
        while k + 1 < n and in_math[k + 1]:
            k += 1
        chunk = "".join(parts[2 * start : 2 * k + 1])
        lead = len(chunk) - len(chunk.lstrip(_EDGE_PUNCT))
        trail = len(chunk) - len(chunk.rstrip(_EDGE_PUNCT))
        core = chunk[lead : len(chunk) - trail if trail else None]
        out.append(f"{chunk[:lead]}${core}${chunk[len(chunk) - trail:] if trail else ''}" if core else chunk)
        if k < n - 1:
            out.append(parts[2 * k + 1])
        k += 1
    return "".join(out)


def wrap_bare_math(text: str) -> str:
    """Envuelve en $...$ las fórmulas LaTeX que la IA dejó sin delimitar (fuera de $, \\( \\) o \\[ \\])."""
    if not text or "\\" not in text and "^" not in text and "_" not in text:
        return text
    pieces = _DELIMITED_RE.split(text)
    return "".join(p if i % 2 else _wrap_plain(p) for i, p in enumerate(pieces))
