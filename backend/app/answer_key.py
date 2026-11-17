"""Clave oficial de respuestas: carga (JSON/CSV) y aplicación a las preguntas extraídas.

Cada fila de la clave dice: en la página impresa P, la pregunta N de la materia M tiene la respuesta R.
La página impresa del libro coincide con la página del PDF, y el prefijo de la clave ("G5", "F9",
"Q-13") solo indica la materia, así que el emparejamiento es (página, número, familia de materia).

Uso por consola (dentro del contenedor backend):
    python -m app.answer_key /ruta/claves_preu.json
"""

import csv
import io
import json
import logging
import re
import sys
from collections import defaultdict
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import AnswerKeyRow, Question
from app.subjects import clean_topic, normalize_subject

logger = logging.getLogger(__name__)

# Materias que comparten numeración/encabezado en el libro ("ARITMÉTICA – ÁLGEBRA", etc.)
_FAMILIES = {
    "ARITMETICA": "AA",
    "ALGEBRA": "AA",
    "GEOMETRIA": "GT",
    "TRIGONOMETRIA": "GT",
}


def family(subject: str) -> str:
    return _FAMILIES.get(subject, subject)


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() not in ("false", "0", "no", "")


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def parse_key_file(data: bytes, filename: str = "") -> list[AnswerKeyRow]:
    """Acepta el JSON o CSV generado al digitalizar la clave (columnas en español)."""
    text = data.decode("utf-8-sig")
    if filename.lower().endswith(".json") or text.lstrip().startswith("["):
        raw = json.loads(text)
    else:
        raw = list(csv.DictReader(io.StringIO(text)))

    rows: list[AnswerKeyRow] = []
    for r in raw:
        subject = normalize_subject(r.get("materia") or r.get("subject"))
        page = _to_int(r.get("pagina") or r.get("page"))
        number = _to_int(r.get("ejercicio") or r.get("number"))
        if not subject or page <= 0 or number <= 0:
            continue
        answer = str(r.get("respuesta") or r.get("answer") or "").strip().upper()[:8]
        rows.append(
            AnswerKeyRow(
                subject=subject,
                topic=str(r.get("tema") or r.get("topic") or "").strip()[:255],
                page=page,
                number=number,
                prefix=str(r.get("prefijo") or r.get("prefix") or "").strip()[:8],
                answer=answer,
                detail=str(r.get("detalle") or r.get("detail") or "").strip()[:255],
                difficulty=max(0, min(4, _to_int(r.get("dificultad") or r.get("difficulty")))),
                readable=_to_bool(r.get("legible", r.get("readable", True))),
                note=str(r.get("nota") or r.get("note") or "").strip(),
            )
        )
    return rows


def replace_key(session: Session, rows: list[AnswerKeyRow]) -> int:
    session.execute(delete(AnswerKeyRow))
    session.add_all(rows)
    session.flush()
    return len(rows)


def _clean_key_topic(topic: str) -> str:
    # "Estequiometría (1)" -> "Estequiometría"; "Problemas: edades" -> "Problemas: edades"
    return clean_topic(re.sub(r"\s*\(\d+\)\s*$", "", topic))


def _merge(rows: list[AnswerKeyRow]) -> dict:
    answers = list(dict.fromkeys(r.answer for r in rows if r.answer))
    detail = next((r.detail for r in rows if r.detail), "")
    notes: list[str] = []
    if len(answers) > 1:
        notes.append("La clave da respuestas distintas para esta pregunta (" + " / ".join(answers) + ").")
    if not answers:
        notes.append("La clave no trae respuesta para esta pregunta.")
    elif any(a not in "ABCDE" for a in answers):
        notes.append("La alternativa de la clave no está entre A y E; verifícala.")
    if detail.lower().startswith("falta dato"):
        notes.append("Según la clave, al ejercicio le falta un dato.")
    if answers and len(answers) == 1 and not all(r.readable for r in rows):
        notes.append("Respuesta transcrita de una foto poco legible; verifícala.")
    return {
        "answer": "/".join(answers)[:8],
        "answer_detail": detail,
        "difficulty": next((r.difficulty for r in rows if r.difficulty), 0),
        "key_note": " ".join(notes),
        "subject": rows[0].subject,
        "topic": _clean_key_topic(rows[0].topic) if rows[0].topic else None,
    }


def apply_answer_key(session: Session, document_id: int | None = None) -> dict:
    """Escribe respuesta, dificultad, materia y tema en las preguntas que coinciden con la clave."""
    key_rows = session.scalars(select(AnswerKeyRow)).all()

    reset = update(Question).values(answer="", answer_detail="", difficulty=0, key_note="")
    if document_id is not None:
        reset = reset.where(Question.document_id == document_id)
    session.execute(reset)
    if not key_rows:
        return {"key_rows": 0, "matched_questions": 0, "unmatched_key_rows": 0}

    groups: dict[tuple[int, int, str], list[AnswerKeyRow]] = defaultdict(list)
    for r in key_rows:
        groups[(r.page, r.number, family(r.subject))].append(r)

    q_stmt = select(Question).where(Question.page_number.in_({k[0] for k in groups}))
    if document_id is not None:
        q_stmt = q_stmt.where(Question.document_id == document_id)
    by_slot: dict[tuple[int, int, str], list[Question]] = defaultdict(list)
    for q in session.scalars(q_stmt):
        by_slot[(q.page_number, q.question_number, family(q.subject))].append(q)

    matched = 0
    unmatched: list[str] = []
    for slot, rows in groups.items():
        questions = by_slot.get(slot)
        if not questions:
            unmatched.append(f"p{slot[0]} {rows[0].prefix}{slot[1]} ({rows[0].subject})")
            continue
        values = _merge(rows)
        for q in questions:
            q.answer = values["answer"]
            q.answer_detail = values["answer_detail"]
            q.difficulty = values["difficulty"]
            q.key_note = values["key_note"]
            q.subject = values["subject"]
            if values["topic"]:
                q.topic = values["topic"]
            matched += 1
    session.flush()
    if unmatched:
        logger.info("Filas de la clave sin pregunta: %s", ", ".join(unmatched[:50]))
    return {
        "key_rows": len(key_rows),
        "matched_questions": matched,
        "unmatched_key_rows": len(unmatched),
        "unmatched": unmatched[:100],
    }


def main(argv: list[str]) -> None:
    from app.database import SyncSessionLocal

    if len(argv) != 2:
        print("Uso: python -m app.answer_key <claves.json|claves.csv>")
        raise SystemExit(2)
    path = argv[1]
    with open(path, "rb") as fh:
        rows = parse_key_file(fh.read(), path)
    with SyncSessionLocal() as s:
        n = replace_key(s, rows)
        stats = apply_answer_key(s)
        s.commit()
    print(f"Clave cargada: {n} filas")
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv)
