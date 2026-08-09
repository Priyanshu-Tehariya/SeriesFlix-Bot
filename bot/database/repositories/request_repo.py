from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.file_request import FileRequest, RequestStatus
from bot.database.repositories.base_repo import BaseRepository


class RequestRepository(BaseRepository[FileRequest]):
    model = FileRequest

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, request_id: int) -> FileRequest | None:
        return await self.session.get(FileRequest, request_id)

    async def create(self, user_id: int, query_text: str) -> FileRequest:
        req = FileRequest(user_id=user_id, query_text=query_text)
        self.session.add(req)
        await self.session.flush()
        return req

    async def set_admin_message_id(self, request_id: int, message_id: int) -> None:
        req = await self.get_by_id(request_id)
        if req:
            req.admin_message_id = message_id

    async def update_status(self, request_id: int, status: RequestStatus) -> FileRequest | None:
        req = await self.get_by_id(request_id)
        if req:
            req.status = status
        return req

    async def get_pending(self, limit: int = 50) -> list[FileRequest]:
        result = await self.session.execute(
            select(FileRequest)
            .where(FileRequest.status == RequestStatus.PENDING)
            .order_by(FileRequest.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())
