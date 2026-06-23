# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""usb:// connector — enumerate and classify USB devices (cameras, keyboards, mice, …)."""

from .core import (
    USB,
    cameras,
    connector_manifest,
    find,
    input_devices,
    list_devices,
    main,
    probe,
    urirun_bindings,
)

__all__ = [
    "USB",
    "cameras",
    "connector_manifest",
    "find",
    "input_devices",
    "list_devices",
    "main",
    "probe",
    "urirun_bindings",
]
