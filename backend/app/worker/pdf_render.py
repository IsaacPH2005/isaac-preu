from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from app.config import settings


@dataclass(frozen=True)
class RenderedPage:
    number: int  # 1-based
    abs_path: Path
    rel_path: str  # relativo a STORAGE_DIR, ej. "pages/3/page_12.png"


def render_pdf_pages(pdf_path: Path, document_id: int, dpi: int | None = None) -> list[RenderedPage]:
    """Renderiza cada página del PDF a PNG en /storage/pages/{doc_id}/page_{n}.png."""
    dpi = dpi or settings.render_dpi
    out_dir = settings.pages_dir / str(document_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages: list[RenderedPage] = []
    with fitz.open(pdf_path) as pdf:
        for index, page in enumerate(pdf):
            n = index + 1
            abs_path = out_dir / f"page_{n}.png"
            if not abs_path.exists():
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                tmp = abs_path.with_suffix(".tmp.png")
                pix.save(tmp)
                tmp.replace(abs_path)
            pages.append(
                RenderedPage(number=n, abs_path=abs_path, rel_path=f"pages/{document_id}/page_{n}.png")
            )
    return pages
