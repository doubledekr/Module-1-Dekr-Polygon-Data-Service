from app import app as fastapi_app
import asyncio
from typing import Callable, Dict, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flag to ensure services are initialized once
_services_initialized = False

def initialize_services():
    """Initialize services synchronously for WSGI compatibility"""
    global _services_initialized
    
    if _services_initialized:
        return
    
    logger.info("Initializing services for WSGI compatibility...")
    
    # Import and initialize services manually
    from utils.cache_manager import CacheManager
    from utils.rate_limiter import RateLimiter
    from services.polygon_service import PolygonDataService
    from services.websocket_service import WebSocketManager
    import app
    
    # Set up services the same way as in the lifespan function
    app.cache_manager = CacheManager()
    app.rate_limiter = RateLimiter()
    app.polygon_service = PolygonDataService(app.cache_manager)
    app.websocket_manager = WebSocketManager(app.polygon_service)
    
    # Set services as global variables
    app.polygon_service = app.polygon_service
    app.websocket_manager = app.websocket_manager
    app.cache_manager = app.cache_manager
    app.rate_limiter = app.rate_limiter
    
    _services_initialized = True
    logger.info("Services initialized successfully")

# ASGI to WSGI bridge for gunicorn compatibility
class ASGIToWSGI:
    def __init__(self, asgi_app):
        self.asgi_app = asgi_app
        # Initialize services when the adapter is created
        initialize_services()
    
    def __call__(self, environ: Dict[str, Any], start_response: Callable):
        # Simple WSGI adapter for FastAPI
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # Create a new event loop for this request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the ASGI application
            result = loop.run_until_complete(self._run_asgi(environ, start_response))
            return result
        finally:
            loop.close()
    
    async def _run_asgi(self, environ: Dict[str, Any], start_response: Callable):
        # Convert WSGI environ to ASGI scope
        scope = {
            'type': 'http',
            'method': environ['REQUEST_METHOD'],
            'path': environ['PATH_INFO'],
            'raw_path': environ['PATH_INFO'].encode(),
            'query_string': environ.get('QUERY_STRING', '').encode(),
            'root_path': '',
            'headers': [],
            'server': ('localhost', 5000),
            'client': ('127.0.0.1', 0),
        }
        
        # Add headers
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                name = key[5:].lower().replace('_', '-')
                scope['headers'].append([name.encode(), value.encode()])
        
        # Handle the request
        response_started = False
        response_body = []
        
        async def receive():
            return {
                'type': 'http.request',
                'body': b'',
                'more_body': False,
            }
        
        async def send(message):
            nonlocal response_started
            if message['type'] == 'http.response.start':
                status = message['status']
                headers = message.get('headers', [])
                
                # Convert headers to WSGI format
                wsgi_headers = []
                for name, value in headers:
                    wsgi_headers.append((name.decode(), value.decode()))
                
                start_response(f'{status} OK', wsgi_headers)
                response_started = True
            
            elif message['type'] == 'http.response.body':
                body = message.get('body', b'')
                if body:
                    response_body.append(body)
        
        try:
            await self.asgi_app(scope, receive, send)
        except Exception as e:
            if not response_started:
                start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [f'Internal Server Error: {str(e)}'.encode()]
        
        return response_body or [b'']

# Export for gunicorn - use the name expected by the workflow
app = ASGIToWSGI(fastapi_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=5000)
