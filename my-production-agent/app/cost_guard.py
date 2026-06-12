"""Redis-backed daily budget enforcement with in-memory fallback."""
import time
import logging
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
        logger.info("Cost guard successfully connected to Redis")
    except Exception as e:
        logger.warning(f"Cost guard failed to connect to Redis ({e}). Falling back to in-memory.")
        redis_client = None

# In-memory store for fallback
_in_memory_budget = {}  # user_id -> daily_spending
_cost_reset_day = time.strftime("%Y-%m-%d")

def _reset_in_memory_if_new_day():
    global _in_memory_budget, _cost_reset_day
    today = time.strftime("%Y-%m-%d")
    if today != _cost_reset_day:
        _in_memory_budget.clear()
        _cost_reset_day = today

def check_budget(user_id: str):
    limit = settings.daily_budget_usd
    today = time.strftime("%Y-%m-%d")
    
    if redis_client:
        try:
            key = f"budget:{user_id}:{today}"
            current = float(redis_client.get(key) or 0.0)
            if current >= limit:
                raise HTTPException(
                    status_code=402,
                    detail=f"Budget exhausted for today: ${limit}. Try again tomorrow."
                )
            return
        except redis.RedisError as re:
            logger.warning(f"Redis budget check error: {re}. Falling back to in-memory.")

    # Fallback to in-memory
    _reset_in_memory_if_new_day()
    current = _in_memory_budget.get(user_id, 0.0)
    if current >= limit:
        raise HTTPException(
            status_code=402,
            detail=f"Budget exhausted for today: ${limit}. Try again tomorrow."
        )

def record_cost(user_id: str, cost: float):
    today = time.strftime("%Y-%m-%d")
    
    if redis_client:
        try:
            key = f"budget:{user_id}:{today}"
            redis_client.incrbyfloat(key, cost)
            redis_client.expire(key, 24 * 3600 + 3600)  # 25 hours
            return
        except redis.RedisError as re:
            logger.warning(f"Redis cost recording error: {re}. Falling back to in-memory.")

    # Fallback to in-memory
    _reset_in_memory_if_new_day()
    _in_memory_budget[user_id] = _in_memory_budget.get(user_id, 0.0) + cost
