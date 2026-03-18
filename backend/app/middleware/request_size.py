"""Pure ASGI middleware for request size limiting.

This middleware operates directly on the ASGI layer, avoiding the overhead
of BaseHTTPMiddleware which wraps every request in additional coroutines.
"""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse


class LimitRequestSizeMiddleware:
    """Pure ASGI middleware to limit request body size.

    Checks the content-length header before processing the request.
    Returns 413 Payload Too Large if the content length exceeds the limit.
    Does not read the request body, just checks the header.

    This is more efficient than BaseHTTPMiddleware because it operates
    directly on the ASGI layer without additional coroutine wrapping.
    """

    def __init__(self, app, max_size: int = 1_048_576):
        """Initialize the middleware.

        Args:
            app: The ASGI application to wrap
            max_size: Maximum request body size in bytes (default: 1MB)
        """
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope, receive, send):
        """Process the ASGI request.

        Args:
            scope: ASGI scope dict with request info
            receive: ASGI receive callable
            send: ASGI send callable
        """
        # Only handle HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check content-length header
        headers = Headers(scope=scope)
        content_length = headers.get("content-length")

        if content_length and int(content_length) > self.max_size:
            # Create a 413 response
            response = JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Max size: {self.max_size} bytes"
                },
            )
            # Send the response directly via ASGI
            await response(scope, receive, send)
            return

        # Proceed with the request
        await self.app(scope, receive, send)
