"""Recorte de las figuras de cada pregunta directamente desde el PDF.

- Páginas con texto (Word/PDF nativo): las figuras son imágenes incrustadas. Se descartan logos y marcas
  de agua (imágenes repetidas en muchas páginas) y cada figura se asigna a la pregunta cuya etiqueta
  ("F8.-", "G2.", "5.") está justo encima. No usa IA.
- Páginas escaneadas (toda la página es una foto): se usa la caja `figure_box` que devolvió la IA al
  extraer la página ([ymin, xmin, ymax, xmax] normalizado a 0-1000).

Uso por consola (dentro del contenedor backend o worker):
    python -m app.figures <document_id>
"""

import logging
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import fitz  # PyMuPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.answer_key import family
from app.config import settings
from app.models import Document, Question

logger = logging.getLogger(__name__)

FIG_DPI = 200
_LABEL_RE = re.compile(r"^\s*([A-Za-z]{0,2})\s*-?\s*(\d{1,2})\s*(?:[.)]|-(?!\d))(?!\d)")
_PREFIX_FAMILY = {"A": "AA", "G": "GT", "F": "FISICA", "Q": "QUIMICA", "B": "BIOLOGIA"}


def _figs_dir(document_id: int) -> Path:
    return settings.pages_dir / str(document_id) / "figs"


def _rel(path: Path) -> str:
    return path.relative_to(settings.storage_path).as_posix()


def _render(page: fitz.Page, rect: fitz.Rect, out: Path) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(dpi=FIG_DPI, clip=rect & page.rect, alpha=False)
    pix.save(out)
    return _rel(out)


def _labels(page: fitz.Page) -> list[tuple[str, int, float]]:
    """Etiquetas de pregunta al inicio de línea: [(prefijo, número, y)] en orden vertical."""
    found = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            if line["bbox"][0] > page.rect.width * 0.35:
                continue
            text = "".join(s["text"] for s in line["spans"])
            m = _LABEL_RE.match(text)
            if not m or m.group(1).upper() not in ("", *_PREFIX_FAMILY):
                continue
            # Un número suelto solo cuenta como etiqueta si le sigue el enunciado ("1. Tres aviones…")
            if not m.group(1) and len(text[m.end():].strip()) < 4:
                continue
            found.append((m.group(1).upper(), int(m.group(2)), line["bbox"][1]))
    # Si la página usa etiquetas con prefijo (A1, G2, F3…), los números sueltos son de fórmulas o fechas
    if any(prefix for prefix, _, _ in found):
        found = [t for t in found if t[0]]
    found.sort(key=lambda t: t[2])
    return found


def _match(label: tuple[str, int, float], index: int, labels: list, questions: list[Question]) -> Question | None:
    prefix, number, _ = label
    tag = f"{prefix}{number}"
    for q in questions:
        if q.question_label and q.question_label.replace("-", "").upper() == tag:
            return q
    fam = _PREFIX_FAMILY.get(prefix)
    same_number = [q for q in questions if q.question_number == number]
    if fam:
        same_family = [q for q in same_number if family(q.subject) == fam]
        if len(same_family) == 1:
            return same_family[0]
    # Mismo número de etiquetas que de preguntas: se empareja por orden de aparición
    # (cubre las páginas donde la extracción renumeró A1..A3, G1..G3 como 1..6).
    if len(labels) == len(questions):
        q = questions[index]
        return q if not fam or family(q.subject) == fam else None
    if not fam and len(same_number) == 1:
        return same_number[0]
    return None


def _valid_box(box) -> bool:
    if not isinstance(box, list) or len(box) != 4:
        return False
    try:
        y0, x0, y1, x1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return False
    return 0 <= y0 < y1 <= 1000 and 0 <= x0 < x1 <= 1000 and (y1 - y0) * (x1 - x0) >= 400


def extract_figures(session: Session, document_id: int) -> dict:
    doc = session.get(Document, document_id)
    if doc is None:
        return {"status": "missing"}
    pdf_path = settings.storage_path / doc.file_path
    out_dir = _figs_dir(document_id)
    shutil.rmtree(out_dir, ignore_errors=True)

    by_page: dict[int, list[Question]] = defaultdict(list)
    for q in session.scalars(
        select(Question).where(Question.document_id == document_id).order_by(Question.page_number, Question.id)
    ):
        q.figures = []
        by_page[q.page_number].append(q)

    stats = Counter()
    with fitz.open(pdf_path) as pdf:
        # Imágenes que se repiten en muchas páginas = logos, encabezados, marcas de agua
        uses: Counter = Counter()
        for page in pdf:
            for xref in {img[0] for img in page.get_images(full=True)}:
                uses[xref] += 1

        for page_no, questions in by_page.items():
            if page_no < 1 or page_no > pdf.page_count:
                continue
            page = pdf[page_no - 1]
            area = page.rect.width * page.rect.height
            figs: list[fitz.Rect] = []
            scanned = False
            for info in page.get_image_info(xrefs=True):
                r = fitz.Rect(info["bbox"]) & page.rect
                if info.get("xref") and uses[info["xref"]] > 3:
                    continue
                if r.width * r.height > 0.3 * area or r.width > 0.75 * page.rect.width:
                    scanned = True  # la página (o media página) es una foto escaneada
                    continue
                if r.width < 25 or r.height < 18 or r.y1 < 55 or r.y0 > page.rect.height - 50:
                    continue
                figs.append(r)

            assigned: dict[int, list[fitz.Rect]] = defaultdict(list)
            if figs and not scanned:
                labels = _labels(page)
                for rect in sorted(figs, key=lambda r: r.y0):
                    cy = (rect.y0 + rect.y1) / 2
                    above = [i for i, lab in enumerate(labels) if lab[2] <= cy + 4]
                    if not above:
                        stats["figuras_sin_pregunta"] += 1
                        continue
                    i = above[-1]
                    q = _match(labels[i], i, labels, questions)
                    if q is None:
                        stats["figuras_sin_pregunta"] += 1
                        continue
                    assigned[q.id].append(rect)

            for q in questions:
                rects = assigned.get(q.id, [])
                paths: list[str] = []
                for k, rect in enumerate(rects):
                    paths.append(_render(page, rect + (-4, -4, 4, 4), out_dir / f"q{q.id}_{k}.png"))
                if not paths and _valid_box(q.figure_box):
                    y0, x0, y1, x1 = (float(v) / 1000 for v in q.figure_box)  # type: ignore[union-attr]
                    w, h = page.rect.width, page.rect.height
                    rect = fitz.Rect(x0 * w, y0 * h, x1 * w, y1 * h) + (-0.015 * w, -0.015 * h, 0.015 * w, 0.015 * h)
                    paths.append(_render(page, rect, out_dir / f"q{q.id}_box.png"))
                    stats["desde_ia"] += 1
                if paths:
                    q.figures = paths
                    q.has_diagram = True
                    stats["preguntas_con_figura"] += 1
                    stats["figuras"] += len(paths)
    session.flush()
    return dict(stats)


def main(argv: list[str]) -> None:
    from app.database import SyncSessionLocal

    if len(argv) != 2:
        print("Uso: python -m app.figures <document_id>")
        raise SystemExit(2)
    with SyncSessionLocal() as s:
        stats = extract_figures(s, int(argv[1]))
        s.commit()
    print(stats)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv)
