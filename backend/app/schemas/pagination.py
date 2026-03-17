"""Pagination schemas for list endpoints.

These schemas provide a consistent structure for paginated responses across all list endpoints.
"""

from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response structure.

    Attributes:
        items: List of items for the current page
        total: Total number of items across all pages
        limit: Maximum items per page
        offset: Number of items skipped before this page
        has_more: Whether there are more items after this page
    """

    items: List[T]
    total: int
    limit: int = Field(ge=1, le=200, description="Items per page")
    offset: int = Field(ge=0, description="Items to skip")
    has_more: bool

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        limit: int,
        offset: int,
    ) -> "PaginatedResponse[T]":
        """Create a paginated response.

        Args:
            items: List of items for the current page
            total: Total number of items across all pages
            limit: Maximum items per page
            offset: Number of items skipped before this page

        Returns:
            A PaginatedResponse instance
        """
        return cls(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(items) < total,
        )
