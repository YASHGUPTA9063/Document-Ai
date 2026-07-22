"""
Queue Client
============
Provides a connection pool to enqueue tasks to Redis (arq).
"""

from arq import create_pool
from arq.connections import RedisSettings
from config import settings
import urllib.parse
from fastapi import Request

async def get_redis_pool():
    """
    Dependency to get the arq Redis pool for enqueuing jobs.
    In a real app, this should be initialized on app startup and stored
    on app.state. Here we create it lazily.
    """
    redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    parsed = urllib.parse.urlparse(redis_url)
    
    redis_settings = RedisSettings(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 6379,
        database=int((parsed.path or '/0').lstrip('/')),
        password=parsed.password
    )
    return await create_pool(redis_settings)
