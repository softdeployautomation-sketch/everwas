"""Admin surfaces: users, API keys, sites.

Admin-only throughout. A request is authenticated as an admin session
(`everwas_session` cookie) or as an API key bearer (`ewpk_...`) holding the
appropriate `sites:*` scope. Session admins manage users and API keys; scoped
API keys manage sites. Every mutation is audited.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

import structlog
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select

from everwas.api.deps import DbSession
from everwas.models.api_key import ApiKey
from everwas.models.device import Site
from everwas.models.user import Role, User
from everwas.schemas.admin import (
    ApiKeyCreated,
    ApiKeyIn,
    ApiKeyOut,
    SiteIn,
    SiteOut,
    UserIn,
    UserOut,
    UserRoleIn,
)
from everwas.security.api_keys import KEY_PREFIX, authenticate_key
from everwas.security.sessions import SESSION_COOKIE, resolve_session
from everwas.security.tenancy import scope_to_org
from everwas.services.admin import (
    KNOWN_SCOPES,
    AdminError,
    create_site,
    create_user,
    delete_site,
    mint_api_key,
    rename_site,
    revoke_api_key,
    set_user_active,
    set_user_role,
)

router = APIRouter()
log = structlog.get_logger()


@dataclass(frozen=True)
class AdminActor:
    """Who is making an admin request — session admin or scoped API key.

    Session admins carry no scopes (empty frozenset) and are implicitly
    authorized for every admin surface. API key actors carry the key's
    scopes and must hold the specific scope a route requires.
    """

    email: str
    org_id: uuid.UUID | None
    scopes: frozenset[str] = frozenset()
    is_session: bool = False

    def requires(self, scope: str) -> None:
        """Raise 403 if this actor lacks `scope`; session admins always pass."""
        if not self.is_session and scope not in self.scopes:
            held = ", ".join(sorted(self.scopes)) or "none"
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"This token lacks the '{scope}' scope. Scopes on this token: {held}.",
            )


async def _admin_actor(
    db: DbSession,
    everwas_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> AdminActor:
    """Resolve the caller: admin session cookie OR scoped API key bearer.

    Raises 401/403 when neither auth path succeeds.
    """
    # Path 1: admin session cookie.
    if everwas_session:
        user = await resolve_session(db, everwas_session)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
        if user.role != Role.admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return AdminActor(email=user.email, org_id=user.org_id, is_session=True)

    # Path 2: API key Bearer (`ewpk_...`).
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
            return AdminActor(
                email=principal.name,
                org_id=principal.org_id,
                scopes=frozenset(principal.scopes),
            )

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated. Present an admin session cookie or an API key: "
        "Authorization: Bearer ewpk_...",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _refused(exc: AdminError) -> HTTPException:
    # 409, not 400: these are all "the current state does not allow this",
    # which is a different thing from a malformed request and reads
    # differently to whoever is looking at it.
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


# ---------------------------------------------------------------- users


@router.get("/users")
async def list_users(db: DbSession, actor: AdminActor = Depends(_admin_actor)) -> list[UserOut]:
    if not actor.is_session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot manage users.")
    rows = await db.execute(
        scope_to_org(select(User).order_by(User.email), User.org_id, actor.org_id)
    )
    return [UserOut.model_validate(u) for u in rows.scalars()]


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def add_user(
    body: UserIn, db: DbSession, actor: AdminActor = Depends(_admin_actor)
) -> UserOut:
    if not actor.is_session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot manage users.")
    try:
        created = await create_user(
            db,
            email=body.email,
            password=body.password,
            role=body.role,
            actor=actor.email,
            actor_org=actor.org_id,
        )
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()
    return UserOut.model_validate(created)


@router.post("/users/{user_id}/role")
async def change_role(
    user_id: uuid.UUID,
    body: UserRoleIn,
    db: DbSession,
    actor: AdminActor = Depends(_admin_actor),
) -> UserOut:
    if not actor.is_session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot manage users.")
    try:
        updated = await set_user_role(
            db, user_id, role=body.role, actor=actor.email, actor_org=actor.org_id
        )
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()
    return UserOut.model_validate(updated)


@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: uuid.UUID,
    db: DbSession,
    actor: AdminActor = Depends(_admin_actor),
) -> UserOut:
    if not actor.is_session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot manage users.")
    try:
        updated = await set_user_active(
            db, user_id, active=False, actor=actor.email, actor_org=actor.org_id
        )
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()
    return UserOut.model_validate(updated)


@router.post("/users/{user_id}/enable")
async def enable_user(
    user_id: uuid.UUID,
    db: DbSession,
    actor: AdminActor = Depends(_admin_actor),
) -> UserOut:
    if not actor.is_session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot manage users.")
    try:
        updated = await set_user_active(
            db, user_id, active=True, actor=actor.email, actor_org=actor.org_id
        )
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()
    return UserOut.model_validate(updated)


# ------------------------------------------------------------- api keys


@router.get("/api-keys")
async def list_api_keys(
    db: DbSession, actor: AdminActor = Depends(_admin_actor)
) -> list[ApiKeyOut]:
    if not actor.is_session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot manage API keys.")
    rows = await db.execute(
        scope_to_org(select(ApiKey).order_by(ApiKey.created_at.desc()), ApiKey.org_id, actor.org_id)
    )
    return [ApiKeyOut.model_validate(k) for k in rows.scalars()]


@router.get("/api-keys/scopes")
async def list_scopes(actor: AdminActor = Depends(_admin_actor)) -> list[str]:
    """So the UI offers the real set instead of a free-text box where a typo
    mints a key that looks privileged and can do nothing."""
    return sorted(KNOWN_SCOPES)


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def add_api_key(
    body: ApiKeyIn, db: DbSession, actor: AdminActor = Depends(_admin_actor)
) -> ApiKeyCreated:
    """The response carries the key in plaintext. It is the only time it
    exists in readable form; only sha256(secret) is stored."""
    if not actor.is_session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot manage API keys.")
    try:
        key, plaintext = await mint_api_key(
            db,
            name=body.name,
            scopes=body.scopes,
            ttl_days=body.ttl_days,
            actor=actor.email,
            actor_org=actor.org_id,
        )
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()
    return ApiKeyCreated(key=ApiKeyOut.model_validate(key), secret=plaintext)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: uuid.UUID, db: DbSession, actor: AdminActor = Depends(_admin_actor)
) -> None:
    if not actor.is_session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot manage API keys.")
    try:
        await revoke_api_key(db, key_id, actor=actor.email, actor_org=actor.org_id)
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()


# ---------------------------------------------------------------- sites


@router.get("/sites")
async def list_sites(db: DbSession, actor: AdminActor = Depends(_admin_actor)) -> list[SiteOut]:
    actor.requires("sites:read")
    rows = await db.execute(
        scope_to_org(select(Site).order_by(Site.name), Site.org_id, actor.org_id)
    )
    return [SiteOut.model_validate(s) for s in rows.scalars()]


@router.post("/sites", status_code=status.HTTP_201_CREATED)
async def add_site(
    body: SiteIn, db: DbSession, actor: AdminActor = Depends(_admin_actor)
) -> SiteOut:
    actor.requires("sites:write")
    try:
        site = await create_site(
            db,
            name=body.name,
            actor=actor.email,
            actor_org=actor.org_id,
            description=body.description,
            address=body.address,
        )
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()
    return SiteOut.model_validate(site)


@router.put("/sites/{site_id}")
async def edit_site(
    site_id: uuid.UUID, body: SiteIn, db: DbSession, actor: AdminActor = Depends(_admin_actor)
) -> SiteOut:
    actor.requires("sites:write")
    try:
        site = await rename_site(
            db,
            site_id,
            name=body.name,
            actor=actor.email,
            actor_org=actor.org_id,
            description=body.description,
            address=body.address,
        )
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()
    return SiteOut.model_validate(site)


@router.delete("/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_site(
    site_id: uuid.UUID, db: DbSession, actor: AdminActor = Depends(_admin_actor)
) -> None:
    actor.requires("sites:write")
    try:
        await delete_site(db, site_id, actor=actor.email, actor_org=actor.org_id)
    except AdminError as exc:
        raise _refused(exc) from exc
    await db.commit()
