import uuid
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from celery import states
from db.models import Task as TaskModel, VM, TaskStatus, User
from workers.tasks.vm_tasks import create_vm_task, delete_vm_task


@pytest.mark.asyncio
async def test_create_vm_task_success(db_session, test_user):
    task_id = uuid.uuid4()
    task_record = TaskModel(
        id=task_id,
        user_id=test_user.id,
        task_type="create_vm",
        status=TaskStatus.PENDING,
        input_params={
            "name": "test-vm",
            "vcpus": 2,
            "memory_mb": 2048,
            "disk_gb": 10,
            "image_source": "/base.qcow2",
        },
    )
    db_session.add(task_record)
    await db_session.commit()

    with patch("workers.tasks.vm_tasks.LibvirtManager") as MockMgr:
        mock_mgr = MockMgr.return_value
        mock_mgr.create_disk = AsyncMock(return_value="/new/disk.qcow2")
        mock_dom = MagicMock()
        mock_dom.name.return_value = "test-vm"
        mock_mgr.define_vm = AsyncMock(return_value=mock_dom)
        mock_mgr.start_vm = AsyncMock()

        result = create_vm_task(str(task_id))

    assert result["vm_id"] is not None

    # Verify task status updated (in on_success hook, but we can check DB)
    await db_session.refresh(task_record)
    assert task_record.status == TaskStatus.SUCCESS

    # Verify VM created in DB
    vm = await db_session.get(VM, uuid.UUID(result["vm_id"]))
    assert vm is not None
    assert vm.name == "test-vm"


@pytest.mark.asyncio
async def test_delete_vm_task_success(db_session, test_user):
    vm = VM(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="to-delete",
        libvirt_domain_name="to-delete",
        vcpus=1,
        memory_mb=512,
        disk_path="/disk.qcow2",
        state="running",
    )
    db_session.add(vm)
    await db_session.commit()

    task_id = uuid.uuid4()
    task_record = TaskModel(
        id=task_id,
        user_id=test_user.id,
        task_type="delete_vm",
        status=TaskStatus.PENDING,
        input_params={"vm_id": str(vm.id)},
    )
    db_session.add(task_record)
    await db_session.commit()

    with patch("workers.tasks.vm_tasks.LibvirtManager") as MockMgr:
        mock_mgr = MockMgr.return_value
        mock_mgr.delete_vm = AsyncMock()

        result = delete_vm_task(str(task_id))

    assert result["vm_id"] == str(vm.id)

    await db_session.refresh(task_record)
    assert task_record.status == TaskStatus.SUCCESS

    deleted_vm = await db_session.get(VM, vm.id)
    assert deleted_vm is None