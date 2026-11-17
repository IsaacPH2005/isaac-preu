from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.config import settings


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    # Ruta interna del PDF: nunca se envía al cliente (ver pdf_url).
    file_path: str = Field(exclude=True)
    total_pages: int
    processed_pages: int
    status: str
    error_message: str | None = None
    created_at: datetime
    question_count: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress(self) -> float:
        if not self.total_pages:
            return 0.0
        return round(min(1.0, self.processed_pages / self.total_pages), 4)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pdf_url(self) -> str | None:
        return f"/storage/{self.file_path}" if settings.expose_pdf else None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    document_filename: str
    question_number: int
    page_number: int
    page_image_path: str
    subject: str
    topic: str
    statement: str
    options: list[str]
    has_diagram: bool
    rank: float | None = None
    pdf_path: str = Field(exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def page_image_url(self) -> str:
        return f"/storage/{self.page_image_path}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pdf_url(self) -> str | None:
        if not settings.expose_pdf:
            return None
        return f"/storage/{self.pdf_path}#page={self.page_number}"


class QuestionPage(BaseModel):
    items: list[QuestionOut]
    total: int
    page: int
    limit: int
    pages: int


class SubjectCount(BaseModel):
    subject: str
    count: int


class TopicCount(BaseModel):
    topic: str
    count: int


class FiltersOut(BaseModel):
    total: int
    diagram_count: int
    subjects: list[SubjectCount]
    topics: dict[str, list[TopicCount]]
