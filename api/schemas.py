from pydantic import BaseModel, UUID4, Field, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any
from db.models.task import TaskStatus


# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    email: str | None = None


class UserResponse(BaseModel):
    id: UUID4
    username: str
    email: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# VM schemas
class VMCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=63)
    vcpus: int = Field(1, ge=1, le=64)
    memory_mb: int = Field(512, ge=512, le=262144)
    disk_gb: int = Field(10, ge=1, le=1024)
    image_source: str = Field(..., description="Path to base image (qcow2)")


class VMResponse(BaseModel):
    id: UUID4
    name: str
    state: str
    vcpus: int
    memory_mb: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class VMCloneRequest(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=63)


# Task schemas
class TaskResponse(BaseModel):
    id: UUID4
    task_type: str
    status: TaskStatus
    input_params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)