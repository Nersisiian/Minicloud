import asyncio
import logging
import uuid

from celery import Task
from sqlalchemy import select

from db.base import async_session_factory
from db.models import VM, Event
from db.models import Task as TaskModel
from db.models import TaskStatus
from libvirt.manager import LibvirtManager
from observability.metrics import (task_completed_counter, vm_created_counter,
                                   vm_deleted_counter, vm_operation_failures)
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class DBTask(Task):
    """Base Celery task that updates DB state."""

    abstract = True

    def on_success(self, retval, task_id, args, kwargs):
        self._update_task_status(task_id, TaskStatus.SUCCESS, result=retval)
        task_completed_counter.labels(task_type=self.name, status="success").inc()

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        self._update_task_status(task_id, TaskStatus.FAILED, error=str(exc))
        task_completed_counter.labels(task_type=self.name, status="failure").inc()
        logger.error(f"Task {task_id} failed: {exc}", exc_info=True)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Task {task_id} retrying due to {exc}")

    def _update_task_status(self, task_id, status, result=None, error=None):
        async def _update():
            async with async_session_factory() as session:
                task = await session.get(TaskModel, uuid.UUID(task_id))
                if task:
                    task.status = status
                    if result:
                        task.result = result
                    if error:
                        task.error = error
                    await session.commit()

        asyncio.run(_update())


@celery_app.task(bind=True, base=DBTask, name="vm.create")
def create_vm_task(self, task_id: str):
    """Create a VM asynchronously."""
    self.update_state(state="RUNNING")

    async def _run():
        async with async_session_factory() as session:
            task = await session.get(TaskModel, uuid.UUID(task_id))
            if not task:
                raise ValueError(f"Task {task_id} not found")

            params = task.input_params
            libvirt_mgr = LibvirtManager()

            # Create disk
            disk_path = await libvirt_mgr.create_disk(
                name=params["name"],
                size_gb=params["disk_gb"],
                base_image=params["image_source"],
            )

            # Define and start VM
            dom = await libvirt_mgr.define_vm(
                name=params["name"],
                vcpus=params["vcpus"],
                memory_mb=params["memory_mb"],
                disk_path=disk_path,
            )
            await libvirt_mgr.start_vm(dom)

            # Create VM record
            vm = VM(
                user_id=task.user_id,
                name=params["name"],
                libvirt_domain_name=dom.name(),
                vcpus=params["vcpus"],
                memory_mb=params["memory_mb"],
                disk_path=disk_path,
                state="running",
            )
            session.add(vm)

            # Log event
            event = Event(
                user_id=task.user_id,
                vm_id=vm.id,
                event_type="vm.created",
                payload={"vcpus": params["vcpus"], "memory_mb": params["memory_mb"]},
            )
            session.add(event)

            await session.commit()
            vm_created_counter.inc()

            logger.info(f"VM created: {vm.id} for user {task.user_id}")
            return {"vm_id": str(vm.id)}

    return asyncio.run(_run())


@celery_app.task(bind=True, base=DBTask, name="vm.delete")
def delete_vm_task(self, task_id: str):
    self.update_state(state="RUNNING")

    async def _run():
        async with async_session_factory() as session:
            task = await session.get(TaskModel, uuid.UUID(task_id))
            if not task:
                raise ValueError(f"Task {task_id} not found")

            vm_id = uuid.UUID(task.input_params["vm_id"])
            vm = await session.get(VM, vm_id)
            if not vm:
                raise ValueError(f"VM {vm_id} not found")

            libvirt_mgr = LibvirtManager()
            await libvirt_mgr.delete_vm(vm.libvirt_domain_name, vm.disk_path)

            # Delete VM record
            await session.delete(vm)
            # Log event
            event = Event(
                user_id=task.user_id,
                vm_id=vm_id,
                event_type="vm.deleted",
                payload={"name": vm.name},
            )
            session.add(event)
            await session.commit()

            vm_deleted_counter.inc()
            logger.info(f"VM deleted: {vm_id}")
            return {"vm_id": str(vm_id)}

    return asyncio.run(_run())


@celery_app.task(bind=True, base=DBTask, name="vm.pause")
def pause_vm_task(self, task_id: str):
    self.update_state(state="RUNNING")

    async def _run():
        async with async_session_factory() as session:
            task = await session.get(TaskModel, uuid.UUID(task_id))
            vm_id = uuid.UUID(task.input_params["vm_id"])
            vm = await session.get(VM, vm_id)

            libvirt_mgr = LibvirtManager()
            await libvirt_mgr.pause_vm(vm.libvirt_domain_name)
            vm.state = "paused"
            await session.commit()

            logger.info(f"VM paused: {vm_id}")
            return {"vm_id": str(vm_id)}

    return asyncio.run(_run())


@celery_app.task(bind=True, base=DBTask, name="vm.resume")
def resume_vm_task(self, task_id: str):
    self.update_state(state="RUNNING")

    async def _run():
        async with async_session_factory() as session:
            task = await session.get(TaskModel, uuid.UUID(task_id))
            vm_id = uuid.UUID(task.input_params["vm_id"])
            vm = await session.get(VM, vm_id)

            libvirt_mgr = LibvirtManager()
            await libvirt_mgr.resume_vm(vm.libvirt_domain_name)
            vm.state = "running"
            await session.commit()

            logger.info(f"VM resumed: {vm_id}")
            return {"vm_id": str(vm_id)}

    return asyncio.run(_run())


@celery_app.task(bind=True, base=DBTask, name="vm.clone")
def clone_vm_task(self, task_id: str):
    self.update_state(state="RUNNING")

    async def _run():
        async with async_session_factory() as session:
            task = await session.get(TaskModel, uuid.UUID(task_id))
            params = task.input_params
            source_vm_id = uuid.UUID(params["source_vm_id"])
            new_name = params["new_name"]

            source_vm = await session.get(VM, source_vm_id)
            if not source_vm:
                raise ValueError("Source VM not found")

            libvirt_mgr = LibvirtManager()
            new_disk_path, new_dom_name = await libvirt_mgr.clone_vm(
                source_vm.libvirt_domain_name,
                source_vm.disk_path,
                new_name,
            )

            # Create new VM record
            new_vm = VM(
                user_id=task.user_id,
                name=new_name,
                libvirt_domain_name=new_dom_name,
                vcpus=source_vm.vcpus,
                memory_mb=source_vm.memory_mb,
                disk_path=new_disk_path,
                state="shutoff",  # clone is shutoff initially
            )
            session.add(new_vm)

            event = Event(
                user_id=task.user_id,
                vm_id=new_vm.id,
                event_type="vm.cloned",
                payload={"source_vm_id": str(source_vm_id)},
            )
            session.add(event)
            await session.commit()

            vm_created_counter.inc()
            logger.info(f"VM cloned: {new_vm.id} from {source_vm_id}")
            return {"vm_id": str(new_vm.id)}

    return asyncio.run(_run())
