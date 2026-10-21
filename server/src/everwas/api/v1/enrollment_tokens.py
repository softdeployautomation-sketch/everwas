"""POST /api/v1/enrollment-tokens — mint an enrollment token.

Auth: admin session cookie (everwas_session) OR API key Bearer (`ewpk_`)
with the `enrollment-tokens:write` scope.

Body: `{ max_uses?: number, ttl_hours?: number }`
Defaults: `max_uses: 1000`, `ttl_hours: 8760` (1 year — long-lived link).
Token prefix `ew_`.
Returns: `{ token, max_uses, ttl_hours, expires_at }`.
"""

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from everwas.api.deps import DbSession
from everwas.models.device import EnrollmentToken
from everwas.models.user import Role
from everwas.schemas.enrollment import EnrollmentTokenOut
from everwas.security.api_keys import KEY_PREFIX, authenticate_key
from everwas.security.sessions import SESSION_COOKIE, resolve_session
from everwas.services.enrollment import mint_enrollment_token

router = APIRouter()


class EnrollmentTokenIn(BaseModel):
    """Request body — all fields optional, defaults applied server-side."""

    max_uses: int | None = None
    ttl_hours: int | None = None
    site_id: str | None = None

    def resolved(self) -> tuple[int, int]:
        return (
            self.max_uses if self.max_uses is not None else 1000,
            self.ttl_hours if self.ttl_hours is not None else 8760,
        )


async def _enrollment_actor(
    db: DbSession,
    everwas_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Resolve the caller: admin session cookie OR scoped API key bearer.

    Returns a human-readable `created_by` string for the token row.
    Raises 401/403 when neither auth path succeeds.
    """
    # Path 1: admin session cookie.
    if everwas_session:
        user = await resolve_session(db, everwas_session)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
        if user.role != Role.admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user.email

    # Path 2: API key Bearer (`ewpk_...`) with the `enrollment-tokens:write` scope.
    if authorization and authorization.lower().startswith("bearer "):
        raw_key = authorization[len("bearer ") :].strip()
        if raw_key.startswith(KEY_PREFIX):
            principal = await authenticate_key(db, raw_key)
            if principal is None:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    "Invalid or expired API key.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if not principal.has("enrollment-tokens:write"):
                held = ", ".join(principal.scopes) or "none"
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    f"This token lacks the 'enrollment-tokens:write' scope. "
                    f"Scopes on this token: {held}.",
                )
            return principal.name

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated. Present an admin session cookie or an API key: "
        "Authorization: Bearer ewpk_...",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=EnrollmentTokenOut,
)
async def create_enrollment_token(
    db: DbSession,
    body: EnrollmentTokenIn,
    actor: Annotated[str, Depends(_enrollment_actor)],
) -> EnrollmentTokenOut:
    """Mint a long-lived enrollment token for public device onboarding."""
    site_uuid = None
    if body.site_id:
        site_uuid = uuid.UUID(body.site_id)

    _row, token = await mint_enrollment_token(
        db,
        site_id=site_uuid,
        max_uses=body.resolved()[0],
        ttl_hours=body.resolved()[1],
        created_by=actor,
    )
    await db.commit()

    # Reload the row so expires_at (server-defaulted) is populated for the response.
    row = (
        await db.execute(
            select(EnrollmentToken).where(
                EnrollmentToken.token_hash == hashlib.sha256(token.encode()).hexdigest()
            )
        )
    ).scalar_one()

    return EnrollmentTokenOut.model_validate(
        {
            "id": row.id,
            "token": token,
            "site_id": row.site_id,
            "max_uses": row.max_uses,
            "ttl_hours": body.resolved()[1],
            "expires_at": row.expires_at,
        }
    )
