from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_

from domain.models.cache import cache, command, repository


class SearchCacheRepository(repository.ISearchCacheRepository):
    session: AsyncSession

    def __init__(self, ses: AsyncSession):
        self.session = ses

    async def save(self, data: cache.SearchCache):
        ses = self.session
        if not data.id:
            await ses.add(data)
            await ses.commit()
            await ses.refresh(data)
            return
        db_data: cache.SearchCache = await ses.get(cache.SearchCache, data.id)
        if not db_data:
            ValueError(f"not found id ,{data.id}")
        db_data.domain = data.domain
        db_data.url = data.url
        db_data.download_type = data.download_type
        db_data.download_text = data.download_text
        db_data.error_msg = data.error_msg
        db_data.expires = db_data.expires
        await ses.commit()
        await ses.refresh(data)
        return

    async def get(
        self, command: command.SearchCacheGetCommand
    ) -> list[cache.SearchCache]:
        ses = self.session
        stmt = select(cache.SearchCache)
        if command.domain:
            stmt = stmt.where(cache.SearchCache.domain == command.domain)
        if command.url:
            stmt = stmt.where(cache.SearchCache.url == command.url)
        if command.expires_start:
            stmt = stmt.where(cache.SearchCache.expires >= command.expires_start)
        if command.is_error:
            stmt = stmt.where(func.length(cache.SearchCache.error_msg) >= 1)
        stmt = stmt.order_by(cache.SearchCache.created_at.desc())
        res = await ses.execute(stmt)
        result = res.scalars()
        if not result:
            return []
        return result.all()


class SearchCacheDeleteRepository(repository.ISearchCacheDeleteRepository):
    session: AsyncSession

    def __init__(self, ses: AsyncSession):
        self.session = ses

    async def delete_all(self, command: command.SearchCacheDeleteCommand):
        stmt = delete(cache.SearchCache)
        if command.domain:
            stmt = stmt.where(cache.SearchCache.domain == command.domain)
        if command.expires_end:
            stmt = stmt.where(cache.SearchCache.expires <= command.expires_end)
        if command.is_error is not None:
            if command.is_error:
                stmt = stmt.where(func.length(cache.SearchCache.error_msg) >= 1)
            else:
                stmt = stmt.where(
                    or_(
                        cache.SearchCache.is_(None),
                        func.length(cache.SearchCache.error_msg) == 0,
                    )
                )
        await self.session.execute(stmt)
