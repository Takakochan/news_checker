from a2wsgi import ASGIMiddleware

from backend.main import app as asgi_app

application = ASGIMiddleware(asgi_app)
