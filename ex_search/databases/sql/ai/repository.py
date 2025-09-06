from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func

from domain.models.ai import (
    ailog as m_ailog,
    repository as a_repo,
    command as a_cmd,
)


class ParserGenerationLogRepository(a_repo.IParserGenerationLogRepository):
    session: AsyncSession

    def __init__(self, ses: AsyncSession):
        self.session = ses

    async def save_all(self, log_entries: list[m_ailog.ParserGenerationLog]):
        ses = self.session
        for log_entry in log_entries:
            if not log_entry.id:
                ses.add(log_entry)
                await ses.flush()
                continue
            db_ailog: m_ailog.ParserGenerationLog = await ses.get(
                m_ailog.ParserGenerationLog, log_entry.id
            )

            if not db_ailog:
                raise ValueError(f"not found update_entry.id ,{log_entry.id}")
            db_ailog.label = log_entry.label
            db_ailog.target_url = log_entry.target_url
            db_ailog.query = log_entry.query
            db_ailog.response = log_entry.response
            db_ailog.error_info = log_entry.error_info
            db_ailog.meta = log_entry.meta
            continue

        await ses.commit()
        for log_entry in log_entries:
            await ses.refresh(log_entry)
        return

    async def get(
        self, command: a_cmd.ParserGenerationLogGetCommand
    ) -> list[m_ailog.ParserGenerationLog]:
        stmt = select(m_ailog.ParserGenerationLog)
        if command.id:
            stmt = stmt.where(m_ailog.ParserGenerationLog.id == command.id)
        if command.label:
            stmt = stmt.where(m_ailog.ParserGenerationLog.label == command.label)
        if command.target_url:
            stmt = stmt.where(
                m_ailog.ParserGenerationLog.target_url == command.target_url
            )
        if command.updated_at_start:
            stmt = stmt.where(
                m_ailog.ParserGenerationLog.updated_at >= command.updated_at_start
            )
        if command.updated_at_end:
            stmt = stmt.where(
                m_ailog.ParserGenerationLog.updated_at <= command.updated_at_end
            )
        if command.is_error is not None:
            if command.is_error is False:
                stmt = stmt.where(m_ailog.ParserGenerationLog.error_info.is_(None))
            else:
                stmt = stmt.where(m_ailog.ParserGenerationLog.error_info.is_not(None))
        stmt = stmt.order_by(m_ailog.ParserGenerationLog.id.desc())
        res = await self.session.execute(stmt)
        return res.scalars().all()
