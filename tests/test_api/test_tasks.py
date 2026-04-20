import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Task, TaskStatus, User


@pytest.mark.asyncio
async def test_get_task_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = uuid.uuid4()
    response = await client.get(f"/tasks/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_success(client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    task = Task(
        user_id=test_user.id,
        task_type="create_vm",
        status=TaskStatus.SUCCESS,
        input_params={"name": "myvm"},
        result={"vm_id": str(uuid.uuid4())},
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.get(f"/tasks/{task.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["task_type"] == "create_vm"


@pytest.mark.asyncio
async def test_cannot_access_other_user_task(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    other_user = User(username="other", hashed_password="hash")
    db_session.add(other_user)
    await db_session.commit()

    task = Task(
        user_id=other_user.id,
        task_type="delete_vm",
        status=TaskStatus.PENDING,
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.get(f"/tasks/{task.id}", headers=auth_headers)
    assert response.status_code == 404