from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func

from domain.models.activitylog import (
    activitylog as m_actlog,
    repository as a_repo,
    command as a_cmd,
)


class ActivityLogRepository(a_repo.IActivityLogRepository):
    session: AsyncSession

    def __init__(self, ses: AsyncSession):
        self.session = ses

    async def save_all(self, log_entries: list[m_actlog.ActivityLog]):
        ses = self.session
        for log_entry in log_entries:
            if not log_entry.id:
                ses.add(log_entry)
                await ses.flush()
                continue
            db_actlog: m_actlog.ActivityLog = await ses.get(
                m_actlog.ActivityLog, log_entry.id
            )

            if not db_actlog:
                raise ValueError(f"not found update_entry.id ,{log_entry.id}")
            db_actlog.target_id = log_entry.target_id
            db_actlog.target_table = log_entry.target_table
            db_actlog.activity_type = log_entry.activity_type
            db_actlog.current_state = log_entry.current_state
            db_actlog.caller_type = log_entry.caller_type
            db_actlog.meta = log_entry.meta
            db_actlog.error_msg = log_entry.error_msg
            continue

        await ses.commit()
        for log_entry in log_entries:
            await ses.refresh(log_entry)
        return

    async def get(
        self, command: a_cmd.ActivityLogGetCommand
    ) -> list[m_actlog.ActivityLog]:
        stmt = select(m_actlog.ActivityLog)
        if command.id:
            stmt = stmt.where(m_actlog.ActivityLog.id == command.id)
        if command.target_id:
            stmt = stmt.where(m_actlog.ActivityLog.target_id == command.target_id)
        if command.target_table:
            stmt = stmt.where(m_actlog.ActivityLog.target_table == command.target_table)
        if command.activity_types:
            stmt = stmt.where(
                m_actlog.ActivityLog.activity_type.in_(command.activity_types)
            )
        if command.current_states:
            stmt = stmt.where(
                m_actlog.ActivityLog.current_state.in_(command.current_states)
            )
        if command.caller_type:
            stmt = stmt.where(m_actlog.ActivityLog.caller_type == command.caller_type)
        if command.is_error:
            stmt = stmt.where(func.length(m_actlog.ActivityLog.error_msg) >= 1)
        if command.updated_at_start:
            stmt = stmt.where(
                m_actlog.ActivityLog.updated_at >= command.updated_at_start
            )
        if command.updated_at_end:
            stmt = stmt.where(m_actlog.ActivityLog.updated_at >= command.updated_at_end)

        res = await self.session.execute(stmt)
        results = res.scalars()
        if not results:
            return []
        return results.all()
