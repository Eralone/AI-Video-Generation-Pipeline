from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.generation_job import GenerationJob
from ..services.ai_text_service import AITextService
from ..services.kinescope_service import KinescopeService
from ..services.veo3_service import Veo3Service
from ..services.user_settings_service import UserSettingsService
from ..services.voispark_service import VoiSparkService
from ..utils.types import PublicationText, ShareLinks


logger = structlog.get_logger(__name__)


class GenerationPipeline:
    def __init__(
        self,
        job_id: str,
        user_id: int,
        db_session: AsyncSession,
        user_settings_service: UserSettingsService,
        ai_text_service: AITextService,
        voispark_service: VoiSparkService,
        kinescope_service: KinescopeService,
    ) -> None:
        self.job_id = job_id
        self.user_id = user_id
        self.db_session = db_session
        self.user_settings_service = user_settings_service
        self.ai_text_service = ai_text_service
        self.voispark_service = voispark_service
        self.kinescope_service = kinescope_service
        self.veo3_service = Veo3Service()

    async def update_job_status(self, status: str, **kwargs) -> None:
        values = {"status": status, **kwargs}
        if status in {"done", "error"}:
            values["completed_at"] = datetime.now(timezone.utc)
        stmt = update(GenerationJob).where(GenerationJob.id == self.job_id).values(**values)
        await self.db_session.execute(stmt)
        await self.db_session.commit()

    async def handle_error(self, exc: Exception) -> None:
        await self.update_job_status("error", error_message=str(exc))
        logger.exception("generation_pipeline_error", job_id=self.job_id, user_id=self.user_id, error=str(exc))
        # Отправка уведомления пользователю будет реализована через VKBotHandler из фонового воркера

    async def send_result_to_user(self, user_id: int, links: ShareLinks, pub: PublicationText) -> None:
        # В этой версии пайплайн только сохраняет данные; отправка через VK Bot реализуется отдельно
        logger.info(
            "generation_pipeline_result_ready",
            user_id=user_id,
            watch_url=links.watch_url,
            download_url=links.download_url,
            title=pub.title,
        )

    async def run(self) -> None:
        try:
            await self.update_job_status("processing")

            settings = await self.user_settings_service.get_settings(self.user_id)

            audio_script = await self.ai_text_service.generate_audio_script(
                topic=settings.topic or "",
                avatar_prompt=settings.avatar.prompt if settings.avatar_id else "",
                keywords=settings.keywords,
                description=settings.description,
            )

            publication = await self.ai_text_service.generate_publication_text(
                topic=settings.topic or "",
                script=audio_script,
            )

            avatar_prompt = settings.avatar.prompt if settings.avatar_id else ""
            background_prompt = settings.background.prompt if settings.background_id else ""
            video_prompt = await self.ai_text_service.generate_video_prompt(avatar_prompt, background_prompt)

            voice_prompt = settings.voice.prompt if settings.voice_id else ""
            audio_prompt = await self.ai_text_service.generate_audio_prompt(audio_script, voice_prompt)

            audio_path = await self.voispark_service.generate_and_save(
                audio_script,
                audio_prompt,
                self.job_id,
            )
            await self.update_job_status("processing", audio_path=audio_path)

            video_local_path = await self.veo3_service.generate_and_upload(
                video_prompt,
                audio_path,
                self.job_id,
            )

            kinescope_project_id = "default"  # может быть вынесено в конфиг
            share_links = await self.kinescope_service.publish_video(video_local_path, publication, kinescope_project_id)

            await self.update_job_status(
                "done",
                video_local_path=video_local_path,
                video_url=share_links.watch_url,
                download_url=share_links.download_url,
            )

            await self.send_result_to_user(self.user_id, share_links, publication)
            await self.user_settings_service.clear_generation_data(self.user_id)
        except Exception as exc:  # noqa: BLE001
            await self.handle_error(exc)

