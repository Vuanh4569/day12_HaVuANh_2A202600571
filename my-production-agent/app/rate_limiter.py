"""Redis-backed sliding-window rate limiter with in-memory fallback."""
import time
import logging
from collections import defaultdict, deque
import redis
from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize redis connection
redis_client = None
if settings.redis_url:
    try:
        redis_client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        redis_client.ping()
        logger.info("Rate limiter successfully connected to Redis")
    except Exception as e:
        logger.warning(f"Rate limiter failed to connect to Redis ({e}). Falling back to in-memory.")
        redis_client = None

# In-memory store for fallback
_in_memory_windows = defaultdict(deque)

def check_rate_limit(user_id: str):
    limit = settings.rate_limit_per_minute
    window = 60
    now = time.time()

    if redis_client:
        try:
            key = f"rate_limit:{user_id}"
            pipe = redis_client.pipeline()
            # Remove old requests
            pipe.zremrangebyscore(key, 0, now - window)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Count request in this window
            pipe.zcard(key)
            # Set key expiration
            pipe.expire(key, window + 10)
            
            _, _, count, _ = pipe.execute()
            
            if count > limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {limit} req/min",
                    headers={"Retry-After": "60"},
                )
            return
        except redis.RedisError as re:
            logger.warning(f"Redis rate limiting error: {re}. Falling back to in-memory.")

    # Fallback to in-memory sliding window
    user_deque = _in_memory_windows[user_id]
    while user_deque and user_deque[0] < now - window:
        user_deque.popleft()
    if len(user_deque) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} req/min",
            headers={"Retry-After": "60"},
        )
    user_deque.append(now)
