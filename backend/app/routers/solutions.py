from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import Question, QuestionSolution
from app.schemas import SolutionOut
from app.worker.celery_app import celery_app

router = APIRouter(prefix="/api/questions", tags=["solutions"])

SOLVE_TASK = "bancopreu.solve_question"
# Si una generación quedó "pending" más de este tiempo (worker reiniciado), se puede relanzar.
STALE_AFTER = timedelta(minutes=10)


def _out(question_id: int, sol: QuestionSolution | None) -> SolutionOut:
    can = settings.solutions_enabled
    if sol is None:
        return SolutionOut(question_id=question_id, status="none", can_generate=can)
    out = SolutionOut.model_validate(sol)
    out.can_generate = can
    return out


@router.get("/{question_id}/solution", response_model=SolutionOut)
async def get_solution(question_id: int, session: AsyncSession = Depends(get_session)) -> SolutionOut:
    return _out(question_id, await session.get(QuestionSolution, question_id))


@router.post("/{question_id}/solution", response_model=SolutionOut)
async def request_solution(
    question_id: int,
    regenerate: bool = Query(False, description="Vuelve a generarla aunque ya exista"),
    session: AsyncSession = Depends(get_session),
) -> SolutionOut:
    """Devuelve la solución guardada o encola su generación (la tarjeta consulta el GET hasta que esté)."""
    sol = await session.get(QuestionSolution, question_id)
    if sol is not None and sol.status == "done" and not regenerate:
        return _out(question_id, sol)
    if not settings.solutions_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La generación de soluciones está deshabilitada")
    if await session.get(Question, question_id) is None:
        raise HTTPException(404, "Pregunta no encontrada")

    now = datetime.now(timezone.utc)
    if sol is not None and sol.status == "pending" and not regenerate and now - sol.updated_at < STALE_AFTER:
        return _out(question_id, sol)  # ya se está generando

    if sol is None:
        sol = QuestionSolution(question_id=question_id)
        session.add(sol)
    sol.status = "pending"
    sol.error = ""
    sol.updated_at = now
    await session.commit()
    await session.refresh(sol)
    celery_app.send_task(SOLVE_TASK, args=[question_id])
    return _out(question_id, sol)
