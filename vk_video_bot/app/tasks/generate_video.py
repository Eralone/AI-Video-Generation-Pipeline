from __future__ import annotations

from celery import Celery
import structlog

from ..config import settings
from ..db.session import async_session_factory
from ..services.ai_text_service import AITextService
from ..services.generation_pipeline import GenerationPipeline
from ..services.kinescope_service import KinescopeService
from ..services.user_settings_service import UserSettingsService
from ..services.voispark_service import VoiSparkService


logger = structlog.get_logger(__name__)

celery_app = Celery(
    "vk_video_bot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)


@celery_app.task(name="generate_video_task")
def generate_video_task(job_id: str, user_id: int) -> None:
    async def _run() -> None:
        async with async_session_factory() as session:
            user_settings_service = UserSettingsService(session)
            ai_text_service = AITextService()
            voispark_service = VoiSparkService()
            kinescope_service = KinescopeService()

            pipeline = GenerationPipeline(
                job_id=job_id,
                user_id=user_id,
                db_session=session,
                user_settings_service=user_settings_service,
                ai_text_service=ai_text_service,
                voispark_service=voispark_service,
                kinescope_service=kinescope_service,
            )
            await pipeline.run()

    import asyncio

    logger.info("generate_video_task_started", job_id=job_id, user_id=user_id)
    asyncio.run(_run())
    logger.info("generate_video_task_finished", job_id=job_id, user_id=user_id)

