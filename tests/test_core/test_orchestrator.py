import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.orchestrator import VMOrchestrator
from db.models import VM, Task, TaskStatus, User


@pytest.mark.asyncio
async def test_request_vm_creation_success(db_session: AsyncSession, test_user: User):
    orchestrator = VMOrchestrator(db_session)

    with patch("workers.tasks.vm_tasks.create_vm_task.apply_async") as mock_apply:
        task = await orchestrator.request_vm_creation(
            user_id=test_user.id,
            name="new-vm",
            vcpus=2,
            memory_mb=2048,
            disk_gb=20,
            image_source="/base.qcow2",
        )

    assert task.user_id == test_user.id
    assert task.task_type == "create_vm"
    assert task.status == TaskStatus.PENDING
    assert task.input_params["name"] == "new-vm"
    mock_apply.assert_called_once()


@pytest.mark.asyncio
async def test_request_vm_creation_duplicate_name(
    db_session: AsyncSession, test_user: User
):
    vm = VM(
        user_id=test_user.id,
        name="existing",
        libvirt_domain_name="existing",
        vcpus=1,
        memory_mb=512,
        disk_path="/disk.qcow2",
    )
    db_session.add(vm)
    await db_session.commit()

    orchestrator = VMOrchestrator(db_session)
    with pytest.raises(ValueError, match="already exists"):
        await orchestrator.request_vm_creation(
            user_id=test_user.id,
            name="existing",
            vcpus=2,
            memory_mb=2048,
            disk_gb=20,
            image_source="/base.qcow2",
        )


@pytest.mark.asyncio
async def test_request_vm_deletion(db_session: AsyncSession, test_user: User):
    vm = VM(
        user_id=test_user.id,
        name="to-delete",
        libvirt_domain_name="to-delete",
        vcpus=1,
        memory_mb=512,
        disk_path="/disk.qcow2",
    )
    db_session.add(vm)
    await db_session.commit()

    orchestrator = VMOrchestrator(db_session)
    with patch("workers.tasks.vm_tasks.delete_vm_task.apply_async") as mock_apply:
        task = await orchestrator.request_vm_deletion(test_user.id, vm.id)

    assert task.task_type == "delete_vm"
    mock_apply.assert_called_once()


@pytest.mark.asyncio
async def test_request_vm_operation_pause(db_session: AsyncSession, test_user: User):
    vm = VM(
        user_id=test_user.id,
        name="running-vm",
        libvirt_domain_name="running-vm",
        vcpus=1,
        memory_mb=512,
        disk_path="/disk.qcow2",
        state="running",
    )
    db_session.add(vm)
    await db_session.commit()

    orchestrator = VMOrchestrator(db_session)
    with patch("workers.tasks.vm_tasks.pause_vm_task.apply_async") as mock_apply:
        task = await orchestrator.request_vm_operation(test_user.id, vm.id, "pause")

    assert task.task_type == "pause_vm"
    mock_apply.assert_called_once()
