from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_body_size_bytes: int = 10_485_760):
        super().__init__(app)
        self.max_body_size_bytes = max_body_size_bytes

    async def dispatch(self, request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_size_bytes:
                    return JSONResponse(status_code=413, content={"detail": "Request body too large"})
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
        return await call_next(request)
