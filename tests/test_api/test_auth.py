import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_password_hash
from db.models import User


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db_session: AsyncSession):
    response = await client.post(
        "/auth/register",
        json={"username": "newuser", "password": "newpass", "email": "new@example.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert "id" in data

    # Verify user in database
    user = await db_session.get(User, data["id"])
    assert user is not None
    assert user.username == "newuser"


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient, test_user: User):
    response = await client.post(
        "/auth/register",
        json={
            "username": test_user.username,
            "password": "pass",
            "email": "dup@example.com",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User):
    response = await client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_user: User):
    response = await client.post(
        "/auth/token",
        data={"username": "testuser", "password": "wrongpass"},
    )
    assert response.status_code == 401
