"""Middleware package for dashKo backend."""

from app.middleware.request_size import LimitRequestSizeMiddleware

__all__ = ["LimitRequestSizeMiddleware"]
