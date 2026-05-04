from starlette.middleware.base import BaseHTTPMiddleware


class StaticCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith('/static/'):
            response.headers.setdefault('Cache-Control', 'public, max-age=86400')
        return response
