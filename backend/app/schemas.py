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
    question_label: str = ""
    page_number: int
    page_image_path: str
    subject: str
    topic: str
    statement: str
    options: list[str]
    has_diagram: bool
    exam: str = ""
    exam_type: str = ""
    exam_year: int | None = None
    answer: str = ""
    answer_detail: str = ""
    difficulty: int = 0
    key_note: str = ""
    has_solution: bool = False
    figures: list[str] = Field(default_factory=list, exclude=True)
    rank: float | None = None
    pdf_path: str = Field(exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def figure_urls(self) -> list[str]:
        return [f"/storage/{p}" for p in self.figures]

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


class ExamCount(BaseModel):
    exam: str
    exam_type: str
    exam_year: int | None
    first_page: int
    last_page: int
    count: int


class ExamTypeCount(BaseModel):
    exam_type: str
    count: int


class DifficultyCount(BaseModel):
    difficulty: int
    count: int


class FiltersOut(BaseModel):
    total: int
    diagram_count: int
    answered_count: int = 0
    page_min: int = 0
    page_max: int = 0
    subjects: list[SubjectCount]
    topics: dict[str, list[TopicCount]]
    exam_types: list[ExamTypeCount] = []
    exams: list[ExamCount] = []
    difficulties: list[DifficultyCount] = []


class SolutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: int
    status: str  # pending | done | failed | none
    figure_data: list[str] = []
    strategy: str = ""
    steps: list[str] = []
    shortcut: str = ""
    common_mistake: str = ""
    final_answer: str = ""
    reaches_key: bool | None = None
    confidence: str = ""
    note: str = ""
    error: str = ""
    can_generate: bool = False


class AnswerKeyStats(BaseModel):
    key_rows: int
    matched_questions: int
    unmatched_key_rows: int
    unmatched: list[str] = []
