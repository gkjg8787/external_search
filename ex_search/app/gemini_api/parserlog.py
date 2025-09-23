import copy

from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.ai import ailog as m_ailog, command as a_cmd, repository as a_repo
from .models import AskGeminiErrorInfo


class UpdateParserLog:
    session: AsyncSession
    repository: a_repo.IParserGenerationLogRepository

    def __init__(self, ses: AsyncSession, repo: a_repo.IParserGenerationLogRepository):
        self.session = ses
        self.repository = repo

    async def save_log(
        self,
        label: str,
        target_url: str,
        query: str,
        response: dict,
        error_info: None | AskGeminiErrorInfo,
        subinfo: dict = {},
    ) -> m_ailog.ParserGenerationLog:
        log_entry = m_ailog.ParserGenerationLog(
            label=label,
            target_url=target_url,
            query=query,
            response=response,
            error_info=error_info.model_dump() if error_info else None,
            meta=subinfo,
        )
        await self.repository.save_all([log_entry])
        await self.session.refresh(log_entry)
        return log_entry

    async def get_log(
        self,
        id: int | None = None,
        label: str = "",
        target_url: str = "",
        is_error: bool | None = None,
    ) -> m_ailog.ParserGenerationLog | None:
        if id:
            command = a_cmd.ParserGenerationLogGetCommand(id=id, is_error=is_error)
        elif label:
            command = a_cmd.ParserGenerationLogGetCommand(
                label=label, is_error=is_error
            )
        elif target_url:
            command = a_cmd.ParserGenerationLogGetCommand(
                target_url=target_url, is_error=is_error
            )
        else:
            return None
        log_entries = await self.repository.get(command=command)
        if not log_entries:
            return None
        latest_log = None
        for log_entry in log_entries:
            if log_entry.error_info and not is_error:
                continue
            if not log_entry.response:
                continue
            latest_log = log_entry
            break
        return latest_log

    async def update_log(
        self,
        log_entry: m_ailog.ParserGenerationLog,
        error_info: None | AskGeminiErrorInfo = None,
        add_subinfo: dict = {},
    ) -> m_ailog.ParserGenerationLog:
        if error_info:
            log_entry.error_info = error_info.model_dump()
        if add_subinfo:
            if not log_entry.meta:
                log_entry.meta = add_subinfo
            elif add_subinfo != log_entry.meta:
                log_entry.meta = copy.deepcopy(log_entry.meta) | add_subinfo
        await self.repository.save_all([log_entry])
        await self.session.refresh(log_entry)
        return log_entry
