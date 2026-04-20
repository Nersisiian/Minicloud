import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from db.base import Base


class VM(Base):
    __tablename__ = "vms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(64), nullable=False)
    libvirt_domain_name = Column(String(128), unique=True, nullable=False)
    vcpus = Column(Integer, nullable=False)
    memory_mb = Column(Integer, nullable=False)
    disk_path = Column(Text, nullable=False)
    state = Column(String(32), nullable=False, default="defined")  # defined, running, paused, shutoff
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())