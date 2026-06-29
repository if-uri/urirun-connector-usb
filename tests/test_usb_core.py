"""Tests for the usb connector. Pure-logic tests run everywhere; sysfs tests are
gated on a real Linux /sys/bus/usb/devices so the suite stays green on any host."""
import os
import pytest
import urirun_connector_usb.core as c

HAS_SYSFS = os.path.isdir(c.SYS_USB)


def test_bindings_valid():
    b = c.urirun_bindings()
    assert set(b["bindings"]) == {
        "usb://host/devices/query/probe",
        "usb://host/devices/query/list",
        "usb://host/devices/query/find",
        "usb://host/cameras/query/list",
        "usb://host/input/query/list",
    }


def test_is_device_dir():
    assert c._is_device_dir("3-11")
    assert c._is_device_dir("usb1")
    assert not c._is_device_dir("3-11:1.0")   # interface, not a device


def test_roles_webcam():
    # USB video class interface → camera role.
    roles = c._roles(0x00, [{"class": 0x0E, "subClass": 0x01, "protocol": 0x00}])
    assert "camera" in roles
    assert c._primary_category(roles) == "camera"


def test_roles_keyboard_and_mouse_combo():
    interfaces = [
        {"class": 0x03, "subClass": 0x01, "protocol": 1},   # boot keyboard
        {"class": 0x03, "subClass": 0x01, "protocol": 2},   # boot mouse
    ]
    roles = c._roles(0x00, interfaces)
    assert "keyboard" in roles and "mouse" in roles
    # keyboard outranks mouse in the priority order.
    assert c._primary_category(roles) == "keyboard"


def test_roles_hub_and_storage():
    assert c._primary_category(c._roles(0x09, [])) == "hub"
    assert c._primary_category(c._roles(0x00, [{"class": 0x08, "subClass": 6, "protocol": 0x50}])) == "storage"


def test_roles_bluetooth():
    roles = c._roles(0xE0, [{"class": 0xE0, "subClass": 0x01, "protocol": 0x01}])
    assert "bluetooth" in roles


def test_owning_device_deepest_ancestor():
    devs = {"3-11": "/sys/devices/pci/usb3/3-11", "3-11.3": "/sys/devices/pci/usb3/3-11/3-11.3"}
    node = "/sys/devices/pci/usb3/3-11/3-11.3/3-11.3:1.0/video4linux/video0"
    assert c._owning_device(node, devs) == "3-11.3"   # deepest, not the parent hub


def test_probe_runs():
    r = c.probe()
    assert r["ok"] and "supported" in r and "tools" in r


@pytest.mark.skipif(not HAS_SYSFS, reason="no /sys/bus/usb/devices on this host")
def test_list_devices_live():
    r = c.list_devices(include_hubs=True)
    assert r["ok"] and isinstance(r["devices"], list)
    if r["devices"]:
        d = r["devices"][0]
        assert "category" in d and "roles" in d and "devNodes" in d


@pytest.mark.skipif(not HAS_SYSFS, reason="no /sys/bus/usb/devices on this host")
def test_cameras_live_shape():
    r = c.cameras()
    assert r["ok"]
    for cam in r["cameras"]:
        assert "videoNodes" in cam


def test_contract_output_shape() -> None:
    """devices/query/probe live output must satisfy the declared out-schema."""
    import importlib.util, sys
    sys.path.insert(0, "/home/tom/github/if-uri/urirun-contract")
    from urirun_connectors_toolkit.contract_gate import validate_output
    spec = importlib.util.spec_from_file_location(
        "contracts_usb",
        "/home/tom/github/if-uri/urirun-connector-usb/urirun_connector_usb/contracts.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result = c.probe()
    assert result["ok"] is True
    validate_output(mod.CONTRACTS["devices/query/probe"], result)
