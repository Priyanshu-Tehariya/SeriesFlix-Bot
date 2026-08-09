from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.user import User
from bot.database.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def upsert(
        self,
        user_id: int,
        full_name: str,
        username: str | None,
    ) -> User:
        """Get or create a user row; update full_name/username on every call."""
        user = await self.get_by_id(user_id)
        if user is None:
            user = User(user_id=user_id, full_name=full_name, username=username)
            self.session.add(user)
            await self.session.flush()
        else:
            user.full_name = full_name
            user.username = username
        return user

    async def set_banned(self, user_id: int, is_banned: bool, ban_reason: str | None = None) -> bool:
        result = await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(is_banned=is_banned, ban_reason=ban_reason)
        )
        return result.rowcount > 0

    async def get_banned_users(self) -> list[User]:
        result = await self.session.execute(select(User).where(User.is_banned.is_(True)))
        return list(result.scalars().all())

    async def increment_request_count(self, user_id: int) -> None:
        user = await self.get_by_id(user_id)
        if user:
            user.total_requests += 1

    async def get_total_users(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(select(func.count(User.user_id)))
        return result.scalar_one()

    async def get_all_user_ids(self) -> list[int]:
        # Filter out banned/blocked users (including those marked by broadcast error handling)
        result = await self.session.execute(
            select(User.user_id).where(User.is_banned == False)
        )
        return list(result.scalars().all())
