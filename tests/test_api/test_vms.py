import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch
from db.models import VM, Task, TaskStatus


@pytest.mark.asyncio
async def test_create_vm_unauthorized(client: AsyncClient):
    response = await client.post("/vms/", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_vm_success(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    with patch("core.orchestrator.VMOrchestrator.request_vm_creation") as mock_req:
        mock_task = Task(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            task_type="create_vm",
            status=TaskStatus.PENDING,
        )
        mock_req.return_value = mock_task

        response = await client.post(
            "/vms/",
            headers=auth_headers,
            json={
                "name": "test-vm",
                "vcpus": 2,
                "memory_mb": 2048,
                "disk_gb": 20,
                "image_source": "/fake/path.qcow2",
            },
        )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"
    assert data["task_type"] == "create_vm"


@pytest.mark.asyncio
async def test_get_vm_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = uuid.uuid4()
    response = await client.get(f"/vms/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_vm_success(client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    vm = VM(
        user_id=test_user.id,
        name="existing-vm",
        libvirt_domain_name="existing-vm",
        vcpus=1,
        memory_mb=1024,
        disk_path="/path/to/disk.qcow2",
        state="running",
    )
    db_session.add(vm)
    await db_session.commit()

    response = await client.get(f"/vms/{vm.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "existing-vm"
    assert data["state"] == "running"


@pytest.mark.asyncio
async def test_delete_vm_success(client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    vm = VM(
        user_id=test_user.id,
        name="to-delete",
        libvirt_domain_name="to-delete",
        vcpus=1,
        memory_mb=512,
        disk_path="/path.qcow2",
        state="running",
    )
    db_session.add(vm)
    await db_session.commit()

    with patch("core.orchestrator.VMOrchestrator.request_vm_deletion") as mock_req:
        mock_task = Task(
            id=uuid.uuid4(),
            user_id=test_user.id,
            task_type="delete_vm",
            status=TaskStatus.PENDING,
        )
        mock_req.return_value = mock_task

        response = await client.delete(f"/vms/{vm.id}", headers=auth_headers)
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_access_other_user_vm(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    other_user = User(
        username="other",
        hashed_password="hash",
    )
    db_session.add(other_user)
    await db_session.commit()

    vm = VM(
        user_id=other_user.id,
        name="others-vm",
        libvirt_domain_name="others-vm",
        vcpus=1,
        memory_mb=512,
        disk_path="/path.qcow2",
        state="running",
    )
    db_session.add(vm)
    await db_session.commit()

    response = await client.get(f"/vms/{vm.id}", headers=auth_headers)
    assert response.status_code == 404  # Should not be visible