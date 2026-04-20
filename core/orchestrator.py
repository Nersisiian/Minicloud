import uuid
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Task, TaskStatus, VM
from workers.celery_app import celery_app
from workers.tasks.vm_tasks import (
    create_vm_task,
    delete_vm_task,
    pause_vm_task,
    resume_vm_task,
    clone_vm_task,
)


class VMOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _create_task_record(
        self,
        user_id: uuid.UUID,
        task_type: str,
        input_params: Dict[str, Any],
    ) -> Task:
        task = Task(
            user_id=user_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            input_params=input_params,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def request_vm_creation(
        self,
        user_id: uuid.UUID,
        name: str,
        vcpus: int,
        memory_mb: int,
        disk_gb: int,
        image_source: str,
    ) -> Task:
        # Basic validation: name uniqueness per user
        stmt = select(VM).where(VM.user_id == user_id, VM.name == name)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError(f"VM with name '{name}' already exists")

        params = {
            "name": name,
            "vcpus": vcpus,
            "memory_mb": memory_mb,
            "disk_gb": disk_gb,
            "image_source": image_source,
        }
        task = await self._create_task_record(user_id, "create_vm", params)

        # Enqueue Celery task, using task.id as Celery task ID for correlation
        create_vm_task.apply_async(
            args=[str(task.id)],
            task_id=str(task.id),
        )
        return task

    async def request_vm_deletion(self, user_id: uuid.UUID, vm_id: uuid.UUID) -> Task:
        vm = await self.db.get(VM, vm_id)
        if not vm or vm.user_id != user_id:
            raise ValueError("VM not found")

        params = {"vm_id": str(vm_id)}
        task = await self._create_task_record(user_id, "delete_vm", params)

        delete_vm_task.apply_async(
            args=[str(task.id)],
            task_id=str(task.id),
        )
        return task

    async def request_vm_operation(self, user_id: uuid.UUID, vm_id: uuid.UUID, operation: str) -> Task:
        vm = await self.db.get(VM, vm_id)
        if not vm or vm.user_id != user_id:
            raise ValueError("VM not found")

        params = {"vm_id": str(vm_id), "operation": operation}
        task = await self._create_task_record(user_id, f"{operation}_vm", params)

        task_func = {
            "pause": pause_vm_task,
            "resume": resume_vm_task,
        }[operation]

        task_func.apply_async(
            args=[str(task.id)],
            task_id=str(task.id),
        )
        return task

    async def request_vm_clone(self, user_id: uuid.UUID, source_vm_id: uuid.UUID, new_name: str) -> Task:
        source_vm = await self.db.get(VM, source_vm_id)
        if not source_vm or source_vm.user_id != user_id:
            raise ValueError("Source VM not found")

        # Check new name uniqueness
        stmt = select(VM).where(VM.user_id == user_id, VM.name == new_name)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError(f"VM with name '{new_name}' already exists")

        params = {"source_vm_id": str(source_vm_id), "new_name": new_name}
        task = await self._create_task_record(user_id, "clone_vm", params)

        clone_vm_task.apply_async(
            args=[str(task.id)],
            task_id=str(task.id),
        )
        return task