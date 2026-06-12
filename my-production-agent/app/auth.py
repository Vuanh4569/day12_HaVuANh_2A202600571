"""Authentication dependency for API Key verification."""
from fastapi import Header, HTTPException
from app.config import settings

def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> str:
    if not x_api_key or x_api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    # Return user_id/client_id, here we use a derived identifier or the key itself
    return "user_" + x_api_key[:8]
