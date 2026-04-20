from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libvirt.exceptions import LibvirtOperationError
from libvirt.manager import LibvirtManager


@pytest.fixture
def libvirt_mgr(mock_libvirt):
    return LibvirtManager()


@pytest.mark.asyncio
async def test_create_disk_success(libvirt_mgr):
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")
        mock_exec.return_value = mock_proc

        path = await libvirt_mgr.create_disk("test", 10, "/base.qcow2")
        assert path.endswith("test.qcow2")
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_create_disk_failure(libvirt_mgr):
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", b"error")
        mock_exec.return_value = mock_proc

        with pytest.raises(LibvirtOperationError):
            await libvirt_mgr.create_disk("test", 10, "/base.qcow2")


def test_define_vm_success(libvirt_mgr, mock_libvirt):
    mock_conn = mock_libvirt.return_value
    mock_dom = MagicMock()
    mock_conn.defineXML.return_value = mock_dom

    dom = asyncio.run(libvirt_mgr.define_vm("test", 2, 2048, "/disk.qcow2"))
    assert dom == mock_dom
    mock_conn.defineXML.assert_called_once()


def test_start_vm_success(libvirt_mgr):
    mock_dom = MagicMock()
    mock_dom.create.return_value = 0

    asyncio.run(libvirt_mgr.start_vm(mock_dom))
    mock_dom.create.assert_called_once()


def test_delete_vm(libvirt_mgr, mock_libvirt):
    mock_conn = mock_libvirt.return_value
    mock_dom = MagicMock()
    mock_dom.isActive.return_value = True
    mock_conn.lookupByName.return_value = mock_dom

    with patch("os.path.exists", return_value=True), patch("os.remove") as mock_remove:
        asyncio.run(libvirt_mgr.delete_vm("test", "/disk.qcow2"))

    mock_dom.destroy.assert_called_once()
    mock_dom.undefine.assert_called_once()
    mock_remove.assert_called_once_with("/disk.qcow2")
