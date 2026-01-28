# ABOUTME: Admin API endpoints
# ABOUTME: Provides administrative functions like key management and data imports

import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import verify_api_key
from app.models.database import APIKey as APIKeyModel

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateAPIKeyRequest(BaseModel):
    """Request body for creating a new API key."""
    owner_email: str
    owner_name: str
    rate_limit_tier: str = "free"
    is_admin: bool = False


class CreateAPIKeyResponse(BaseModel):
    """Response containing the newly created API key."""
    api_key: str
    key_prefix: str
    owner_email: str
    owner_name: str
    rate_limit_tier: str
    is_admin: bool


def verify_admin_api_key(
    api_key: APIKeyModel = Depends(verify_api_key)
) -> APIKeyModel:
    """Verify that the API key has admin privileges."""
    if not api_key.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Admin privileges required"}
        )
    return api_key


@router.post("/keys", status_code=201, response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    db: Session = Depends(get_db),
    admin_key: APIKeyModel = Depends(verify_admin_api_key)
):
    """
    Create a new API key (admin only).

    The API key is generated securely and returned only once.
    Only the SHA-256 hash is stored in the database.
    """
    # Generate a secure random API key
    # Format: rcapi_<32 random hex characters>
    plaintext_key = f"rcapi_{secrets.token_hex(32)}"

    # Hash the key for storage
    key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
    key_prefix = plaintext_key[:8]

    # Create the API key in the database
    new_api_key = APIKeyModel(
        key_hash=key_hash,
        key_prefix=key_prefix,
        owner_email=request.owner_email,
        owner_name=request.owner_name,
        rate_limit_tier=request.rate_limit_tier,
        is_admin=request.is_admin
    )

    db.add(new_api_key)
    db.commit()
    db.refresh(new_api_key)

    # Return the plaintext key (only time it's visible)
    return CreateAPIKeyResponse(
        api_key=plaintext_key,
        key_prefix=key_prefix,
        owner_email=new_api_key.owner_email,
        owner_name=new_api_key.owner_name,
        rate_limit_tier=new_api_key.rate_limit_tier,
        is_admin=new_api_key.is_admin
    )
