"""API-key bearer authentication on the admin sites surface.

Covers the auth gap the review found: the admin router previously accepted
only session cookies, so API keys (Vantra's install-link flow) got 401 on
POST /api/v1/admin/sites and GET /api/v1/admin/sites.

Session admins still work on every admin surface; scoped API keys can manage
sites only (sites:read for listing, sites:write for create/rename/delete).
User and API-key management remain session-admin only.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from everwas.api.app import create_app
from everwas.db.engine import get_sessionmaker
from everwas.models.org import DEFAULT_ORG_ID
from everwas.services.admin import create_site, mint_api_key

pytestmark = pytest.mark.usefixtures("pg_database")


async def _app_client():
    """A real HTTP client against the app, no auth overrides."""
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _mint_key(db, scopes, name="tk"):
    _, raw = await mint_api_key(
        db,
        name=name,
        scopes=scopes,
        ttl_days=None,
        actor="test@example.com",
        actor_org=DEFAULT_ORG_ID,
    )
    return raw  # "ewpk_{key_id}_{secret}"


async def test_api_key_with_sites_write_can_create_site(pg_database):
    site_name = f"tk-{uuid.uuid4().hex[:8]}"
    async with get_sessionmaker() as db, db.begin():
        raw_key = await _mint_key(db, ["sites:write"])

    async with _app_client() as c:
        r = await c.post(
            "/api/v1/admin/sites",
            json={"name": site_name},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == site_name


async def test_api_key_with_sites_read_can_list_sites(pg_database):
    site_name = f"tk-{uuid.uuid4().hex[:8]}"
    async with get_sessionmaker() as db, db.begin():
        await create_site(
            db,
            name=site_name,
            actor="test@example.com",
            actor_org=DEFAULT_ORG_ID,
        )
        raw_key = await _mint_key(db, ["sites:read"])

    async with _app_client() as c:
        r = await c.get(
            "/api/v1/admin/sites",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    assert r.status_code == 200, r.text
    names = [s["name"] for s in r.json()]
    assert site_name in names


async def test_api_key_without_sites_scope_gets_403(pg_database):
    async with get_sessionmaker() as db, db.begin():
        raw_key = await _mint_key(db, ["devices:read"])

    async with _app_client() as c:
        r = await c.post(
            "/api/v1/admin/sites",
            json={"name": f"tk-{uuid.uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    assert r.status_code == 403, r.text


async def test_no_auth_gets_401(pg_database):
    async with _app_client() as c:
        r = await c.post(
            "/api/v1/admin/sites",
            json={"name": f"tk-{uuid.uuid4().hex[:8]}"},
        )
    assert r.status_code == 401, r.text


async def test_api_key_cannot_manage_users(pg_database):
    async with get_sessionmaker() as db, db.begin():
        raw_key = await _mint_key(db, ["sites:write"])

    async with _app_client() as c:
        r = await c.post(
            "/api/v1/admin/users",
            json={
                "email": "tk@example.com",
                "password": "a-long-enough-password",
                "role": "viewer",
            },
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    assert r.status_code == 403, r.text


async def test_api_key_cannot_manage_api_keys(pg_database):
    async with get_sessionmaker() as db, db.begin():
        raw_key = await _mint_key(db, ["sites:write"])

    async with _app_client() as c:
        r = await c.post(
            "/api/v1/admin/api-keys",
            json={"name": "tk-key", "scopes": ["devices:read"]},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    assert r.status_code == 403, r.text
