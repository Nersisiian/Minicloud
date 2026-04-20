from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from api.schemas import (TaskResponse, VMCloneRequest, VMCreateRequest,
                         VMResponse)
from core.orchestrator import VMOrchestrator
from db.base import get_db
from db.models import VM, User

router = APIRouter(prefix="/vms", tags=["Virtual Machines"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def create_vm(
    request: Request,
    vm_req: VMCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = VMOrchestrator(db)
    task = await orchestrator.request_vm_creation(
        user_id=current_user.id,
        name=vm_req.name,
        vcpus=vm_req.vcpus,
        memory_mb=vm_req.memory_mb,
        disk_gb=vm_req.disk_gb,
        image_source=vm_req.image_source,
    )
    return TaskResponse.model_validate(task)


@router.get("/{vm_id}", response_model=VMResponse)
async def get_vm(
    vm_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vm = await db.get(VM, vm_id)
    if not vm or vm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="VM not found")
    return VMResponse.model_validate(vm)


@router.delete(
    "/{vm_id}", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED
)
async def delete_vm(
    vm_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vm = await db.get(VM, vm_id)
    if not vm or vm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="VM not found")

    orchestrator = VMOrchestrator(db)
    task = await orchestrator.request_vm_deletion(
        user_id=current_user.id,
        vm_id=vm_id,
    )
    return TaskResponse.model_validate(task)


@router.post(
    "/{vm_id}/pause", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED
)
async def pause_vm(
    vm_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vm = await db.get(VM, vm_id)
    if not vm or vm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="VM not found")

    if vm.state != "running":
        raise HTTPException(status_code=400, detail="VM must be running to pause")

    orchestrator = VMOrchestrator(db)
    task = await orchestrator.request_vm_operation(
        user_id=current_user.id,
        vm_id=vm_id,
        operation="pause",
    )
    return TaskResponse.model_validate(task)


@router.post(
    "/{vm_id}/resume", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED
)
async def resume_vm(
    vm_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vm = await db.get(VM, vm_id)
    if not vm or vm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="VM not found")

    if vm.state != "paused":
        raise HTTPException(status_code=400, detail="VM must be paused to resume")

    orchestrator = VMOrchestrator(db)
    task = await orchestrator.request_vm_operation(
        user_id=current_user.id,
        vm_id=vm_id,
        operation="resume",
    )
    return TaskResponse.model_validate(task)


@router.post(
    "/{vm_id}/clone", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED
)
async def clone_vm(
    vm_id: UUID,
    clone_req: VMCloneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vm = await db.get(VM, vm_id)
    if not vm or vm.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="VM not found")

    orchestrator = VMOrchestrator(db)
    task = await orchestrator.request_vm_clone(
        user_id=current_user.id,
        source_vm_id=vm_id,
        new_name=clone_req.new_name,
    )
    return TaskResponse.model_validate(task)
