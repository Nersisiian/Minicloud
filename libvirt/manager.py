import asyncio
import os
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import libvirt
from core.config import settings
from libvirt.exceptions import LibvirtOperationError


class LibvirtManager:
    def __init__(self):
        self.conn = libvirt.open(settings.LIBVIRT_URI)
        self.template_env = Environment(loader=FileSystemLoader("libvirt/templates"))

    async def create_disk(self, name: str, size_gb: int, base_image: str) -> str:
        """Create a qcow2 disk backed by a base image."""
        dst_path = Path(settings.VM_IMAGE_DIR) / f"{name}.qcow2"
        # Use qemu-img to create a backing file
        loop = asyncio.get_event_loop()
        cmd = [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            "-o",
            f"backing_file={base_image}",
            str(dst_path),
            f"{size_gb}G",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise LibvirtOperationError(f"Failed to create disk: {stderr.decode()}")
        return str(dst_path)

    async def define_vm(self, name: str, vcpus: int, memory_mb: int, disk_path: str):
        """Define a new domain from XML template."""
        template = self.template_env.get_template("vm.xml.j2")
        xml = template.render(
            name=name,
            vcpus=vcpus,
            memory_kib=memory_mb * 1024,
            disk_path=disk_path,
            bridge_iface=settings.VM_BRIDGE_IFACE,
        )
        loop = asyncio.get_event_loop()
        dom = await loop.run_in_executor(None, self.conn.defineXML, xml)
        if not dom:
            raise LibvirtOperationError("Failed to define domain")
        return dom

    async def start_vm(self, dom):
        loop = asyncio.get_event_loop()
        if await loop.run_in_executor(None, dom.create) < 0:
            raise LibvirtOperationError("Failed to start domain")

    # Other methods: destroy, undefine, pause, resume, clone (via snapshots)...
