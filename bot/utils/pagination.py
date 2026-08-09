from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    items: list[T]
    page: int
    total_pages: int
    total_items: int

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


def paginate(items: list[T], page: int = 1, per_page: int = 10) -> Page[T]:
    """Slice a list into a Page. page is 1-indexed."""
    page = max(1, page)
    total_items = len(items)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    end = start + per_page
    return Page(
        items=items[start:end],
        page=page,
        total_pages=total_pages,
        total_items=total_items,
    )
