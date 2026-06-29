# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Route contracts for the usb connector — USB device enumeration, read-only."""
from __future__ import annotations

from urirun_connectors_toolkit.contract_gate import Contract

_DEVICE = {"vendorId": "str", "productId": "str", "name": "str",
           "category": "str", "roles": "list", "isHub": "bool"}

CONTRACTS: dict[str, Contract] = {
    "devices/query/probe": Contract(
        version="v1",
        effect="query",
        reversible=False,
        inp={},
        out={"ok": "bool", "supported": "bool", "sysfs": "str",
             "sysfsPresent": "bool", "tools": "obj", "modules": "obj", "platform": "str"},
        errors=(),
        examples=(
            {
                "payload": {},
                "result": {
                    "ok": True,
                    "connector": "usb",
                    "kind": "probe",
                    "live": False,
                    "supported": True,
                    "sysfs": "/sys/bus/usb/devices",
                    "sysfsPresent": True,
                    "tools": {"lsusb": "/usr/bin/lsusb", "v4l2-ctl": ""},
                    "modules": {"pyusb": False},
                    "platform": "Linux",
                },
            },
        ),
    ),
    "devices/query/list": Contract(
        version="v1",
        effect="query",
        reversible=False,
        inp={"include_hubs": "?bool", "category": "?str"},
        out={"ok": "bool", "count": "int", "summary": "obj", "devices": [_DEVICE]},
        errors=("precondition-unmet",),
        examples=(
            {
                "payload": {"category": "camera"},
                "result": {
                    "ok": True,
                    "connector": "usb",
                    "kind": "device-list",
                    "live": False,
                    "count": 1,
                    "summary": {"camera": 1},
                    "devices": [{"vendorId": "046d", "productId": "085e",
                                  "name": "Logitech BRIO", "category": "camera",
                                  "roles": ["camera"], "isHub": False}],
                },
            },
        ),
    ),
    "devices/query/find": Contract(
        version="v1",
        effect="query",
        reversible=False,
        inp={"query": "?str", "vendor_id": "?str", "product_id": "?str",
             "category": "?str", "include_hubs": "?bool"},
        out={"ok": "bool", "count": "int", "devices": [_DEVICE]},
        errors=("precondition-unmet",),
        examples=(
            {
                "payload": {"query": "logitech"},
                "result": {
                    "ok": True,
                    "connector": "usb",
                    "count": 1,
                    "devices": [{"vendorId": "046d", "productId": "085e",
                                  "name": "Logitech BRIO", "category": "camera",
                                  "roles": ["camera"], "isHub": False}],
                },
            },
        ),
    ),
    "cameras/query/list": Contract(
        version="v1",
        effect="query",
        reversible=False,
        inp={},
        out={"ok": "bool", "count": "int", "summary": "obj", "devices": "list"},
        errors=(),
        examples=(
            {
                "payload": {},
                "result": {
                    "ok": True,
                    "connector": "usb",
                    "count": 1,
                    "summary": {"camera": 1},
                    "devices": [{"vendorId": "046d", "productId": "085e",
                                  "name": "Logitech BRIO", "category": "camera",
                                  "roles": ["camera"], "isHub": False}],
                },
            },
        ),
    ),
    "input/query/list": Contract(
        version="v1",
        effect="query",
        reversible=False,
        inp={"kind": "?str"},
        out={"ok": "bool", "count": "int", "summary": "obj", "devices": "list"},
        errors=(),
        examples=(
            {
                "payload": {},
                "result": {
                    "ok": True,
                    "connector": "usb",
                    "count": 0,
                    "summary": {},
                    "devices": [],
                },
            },
        ),
    ),
}
