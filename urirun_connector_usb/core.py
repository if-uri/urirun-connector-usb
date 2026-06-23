# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# usb:// connector — turn "what is plugged into this computer?" into a first-class URI.
# It reads the kernel's USB view from sysfs (/sys/bus/usb/devices), classifies every
# device by its USB class codes (camera/webcam, keyboard, mouse, audio, storage, hub,
# printer, bluetooth, serial, smart-card/security-key, ...) and enriches each one with
# the device nodes it owns (/dev/video*, /dev/input/event*, /dev/ttyUSB*, /dev/hidraw*,
# block devices). Everything works with the Python stdlib and no root; lsusb is used
# only to provide nicer vendor/product names when a device omits its own strings.

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any

import urirun

CONNECTOR_ID = "usb"
USB = urirun.connector(CONNECTOR_ID, scheme="usb", target="host", meta={"label": "USB devices"})

SYS_USB = "/sys/bus/usb/devices"

# USB base class codes → short names (subset that matters for classification).
USB_CLASS = {
    0x00: "per-interface",
    0x01: "audio",
    0x02: "communications",
    0x03: "hid",
    0x05: "physical",
    0x06: "image",
    0x07: "printer",
    0x08: "mass-storage",
    0x09: "hub",
    0x0A: "cdc-data",
    0x0B: "smart-card",
    0x0D: "content-security",
    0x0E: "video",
    0x0F: "personal-healthcare",
    0x10: "audio-video",
    0xDC: "diagnostic",
    0xE0: "wireless",
    0xEF: "miscellaneous",
    0xFE: "application-specific",
    0xFF: "vendor-specific",
}

# Friendly category priority — when a device exposes several interfaces, the first
# matching role in this list wins as the device's primary `category`.
_CATEGORY_PRIORITY = [
    "camera", "keyboard", "mouse", "gamepad", "storage", "printer", "scanner",
    "audio", "smart-card", "bluetooth", "wireless", "serial", "hub", "hid",
    "network", "vendor-specific", "unknown",
]

# /sys/class subsystems that map a USB device to a /dev node (or interface name).
#   subsystem -> (node category, how to build the user-facing path)
_NODE_SUBSYSTEMS = {
    "video4linux": ("video", lambda b: f"/dev/{b}"),
    "input": ("input", lambda b: f"/dev/input/{b}"),
    "tty": ("serial", lambda b: f"/dev/{b}"),
    "hidraw": ("hidraw", lambda b: f"/dev/{b}"),
    "block": ("block", lambda b: f"/dev/{b}"),
    "net": ("network", lambda b: b),
    "sound": ("sound", lambda b: f"/dev/snd/{b}"),
}


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _read_int(path: str, base: int = 16) -> int | None:
    raw = _read(path)
    if not raw:
        return None
    try:
        return int(raw, base)
    except ValueError:
        return None


def _is_device_dir(name: str) -> bool:
    """sysfs USB *device* dirs have no ':' (interfaces look like '3-11:1.0')."""
    return ":" not in name and name not in (".", "..")


def _driver_of(path: str) -> str:
    link = os.path.join(path, "driver")
    if os.path.islink(link):
        return os.path.basename(os.path.realpath(link))
    return ""


def _interfaces(dev_dir: str, dev_name: str) -> list[dict[str, Any]]:
    """Read the interface descriptors (class/subclass/protocol/driver) of a device."""
    out: list[dict[str, Any]] = []
    prefix = dev_name + ":"
    try:
        entries = sorted(os.listdir(dev_dir))
    except OSError:
        return out
    for entry in entries:
        if not entry.startswith(prefix):
            continue
        ipath = os.path.join(dev_dir, entry)
        cls = _read_int(os.path.join(ipath, "bInterfaceClass"))
        sub = _read_int(os.path.join(ipath, "bInterfaceSubClass"))
        proto = _read_int(os.path.join(ipath, "bInterfaceProtocol"))
        out.append({
            "interface": entry,
            "class": cls,
            "className": USB_CLASS.get(cls, "unknown") if cls is not None else None,
            "subClass": sub,
            "protocol": proto,
            "driver": _driver_of(ipath),
        })
    return out


def _roles(dev_class: int | None, interfaces: list[dict[str, Any]]) -> list[str]:
    """Map USB class codes to friendly roles. A device can have several (e.g. a combo
    keyboard that also presents a mouse interface)."""
    roles: list[str] = []

    def add(role: str) -> None:
        if role not in roles:
            roles.append(role)

    # Gather every class that the device advertises: the device descriptor itself plus
    # each interface (devices with bDeviceClass == 0 defer entirely to their interfaces).
    classes: list[tuple[int | None, int | None, int | None]] = []
    if dev_class not in (None, 0x00):
        classes.append((dev_class, None, None))
    for iface in interfaces:
        classes.append((iface.get("class"), iface.get("subClass"), iface.get("protocol")))

    for cls, sub, proto in classes:
        if cls == 0x0E or cls == 0x10:          # video / audio-video
            add("camera")
        elif cls == 0x06:                       # still-image (PTP) → scanner/camera
            add("scanner")
        elif cls == 0x03:                       # HID
            if proto == 1:
                add("keyboard")
            elif proto == 2:
                add("mouse")
            else:
                add("hid")
        elif cls == 0x08:                       # mass storage
            add("storage")
        elif cls == 0x07:                       # printer
            add("printer")
        elif cls == 0x01:                       # audio
            add("audio")
        elif cls == 0x09:                       # hub
            add("hub")
        elif cls == 0x0B:                       # smart card (incl. FIDO security keys)
            add("smart-card")
        elif cls == 0xE0:                       # wireless
            if sub == 0x01 and proto == 0x01:
                add("bluetooth")
            else:
                add("wireless")
        elif cls in (0x02, 0x0A):               # CDC / CDC-data → serial / network
            add("serial")
        else:
            name = USB_CLASS.get(cls or -1)
            if name:
                add(name)
    return roles


def _primary_category(roles: list[str]) -> str:
    for cat in _CATEGORY_PRIORITY:
        if cat in roles:
            return cat
    return roles[0] if roles else "unknown"


def _device_realpaths() -> dict[str, str]:
    """Map each sysfs USB device name → its resolved /sys/devices path (for node mapping)."""
    out: dict[str, str] = {}
    try:
        names = os.listdir(SYS_USB)
    except OSError:
        return out
    for name in names:
        if _is_device_dir(name):
            out[name] = os.path.realpath(os.path.join(SYS_USB, name))
    return out


def _owning_device(node_realpath: str, dev_realpaths: dict[str, str]) -> str | None:
    """Return the USB device name whose sysfs path is the *deepest* ancestor of a node."""
    best: tuple[int, str | None] = (-1, None)
    for name, rp in dev_realpaths.items():
        if node_realpath == rp or node_realpath.startswith(rp + os.sep):
            if len(rp) > best[0]:
                best = (len(rp), name)
    return best[1]


def _collect_nodes(dev_realpaths: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    """Build {usb_device_name: [{type, path, subsystem}, ...]} from /sys/class/*."""
    nodes: dict[str, list[dict[str, str]]] = {}
    for subsystem, (kind, build) in _NODE_SUBSYSTEMS.items():
        base = os.path.join("/sys/class", subsystem)
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for entry in entries:
            if subsystem == "input" and not entry.startswith(("event", "mouse", "js")):
                continue
            real = os.path.realpath(os.path.join(base, entry))
            owner = _owning_device(real, dev_realpaths)
            if not owner:
                continue
            nodes.setdefault(owner, []).append({
                "type": kind,
                "path": build(entry),
                "subsystem": subsystem,
            })
    for items in nodes.values():
        items.sort(key=lambda n: (n["type"], n["path"]))
    return nodes


def _lsusb_names() -> dict[str, str]:
    """Map 'vvvv:pppp' → human name from lsusb, used as a fallback for missing strings."""
    if not shutil.which("lsusb"):
        return {}
    try:
        proc = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return {}
    out: dict[str, str] = {}
    pat = re.compile(r"ID ([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)$")
    for line in proc.stdout.splitlines():
        m = pat.search(line)
        if m:
            out[f"{m.group(1).lower()}:{m.group(2).lower()}"] = m.group(3).strip()
    return out


def _read_device(name: str, dev_realpaths: dict[str, str],
                 nodes: dict[str, list[dict[str, str]]], lsusb: dict[str, str]) -> dict[str, Any]:
    path = os.path.join(SYS_USB, name)
    vendor = (_read(os.path.join(path, "idVendor")) or "").lower()
    product = (_read(os.path.join(path, "idProduct")) or "").lower()
    manufacturer = _read(os.path.join(path, "manufacturer"))
    product_name = _read(os.path.join(path, "product"))
    dev_class = _read_int(os.path.join(path, "bDeviceClass"))
    interfaces = _interfaces(path, name)
    roles = _roles(dev_class, interfaces)
    category = _primary_category(roles)

    key = f"{vendor}:{product}" if vendor and product else ""
    name_parts = [p for p in (manufacturer, product_name) if p]
    display = " ".join(name_parts) or lsusb.get(key, "") or "(unknown device)"

    is_hub = category == "hub"
    speed = _read(os.path.join(path, "speed"))
    return {
        "name": display,
        "category": category,
        "roles": roles,
        "isHub": is_hub,
        "vendorId": vendor,
        "productId": product,
        "id": key,
        "manufacturer": manufacturer,
        "product": product_name,
        "serial": _read(os.path.join(path, "serial")),
        "busnum": _read_int(os.path.join(path, "busnum"), base=10),
        "devnum": _read_int(os.path.join(path, "devnum"), base=10),
        "deviceClass": dev_class,
        "deviceClassName": USB_CLASS.get(dev_class, "unknown") if dev_class is not None else None,
        "speedMbps": int(speed) if speed.isdigit() else None,
        "usbVersion": _read(os.path.join(path, "version")),
        "sysfs": name,
        "interfaces": interfaces,
        "devNodes": nodes.get(name, []),
    }


def _all_devices() -> list[dict[str, Any]]:
    """Enumerate every USB device on this host with classification and device nodes."""
    dev_realpaths = _device_realpaths()
    nodes = _collect_nodes(dev_realpaths)
    lsusb = _lsusb_names()
    devices = [_read_device(name, dev_realpaths, nodes, lsusb) for name in sorted(dev_realpaths)]
    devices.sort(key=lambda d: (d.get("busnum") or 0, d.get("devnum") or 0))
    return devices


def _supported() -> bool:
    return os.path.isdir(SYS_USB)


def _summary(devices: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for dev in devices:
        counts[dev["category"]] = counts.get(dev["category"], 0) + 1
    return dict(sorted(counts.items()))


@USB.handler("devices/query/probe", isolated=True,
             meta={"label": "Probe USB backends and support", "cliAlias": "probe"})
def probe() -> dict[str, Any]:
    """Report whether USB enumeration works on this host and which helpers are available."""
    return urirun.ok(
        connector=CONNECTOR_ID, kind="probe", live=False,
        supported=_supported(),
        sysfs=SYS_USB,
        sysfsPresent=os.path.isdir(SYS_USB),
        tools={
            "lsusb": shutil.which("lsusb") or "",
            "v4l2-ctl": shutil.which("v4l2-ctl") or "",
        },
        modules={"pyusb": _module_available("usb")},
        platform=os.uname().sysname if hasattr(os, "uname") else "",
    )


def _module_available(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:  # noqa: BLE001
        return False


@USB.handler("devices/query/list", isolated=True,
             meta={"label": "List all USB devices with category and device nodes", "cliAlias": "list"})
def list_devices(include_hubs: bool = False, category: str = "") -> dict[str, Any]:
    """List every USB device plugged into this computer, each classified into a category
    (camera, keyboard, mouse, audio, storage, hub, printer, bluetooth, serial, ...) and
    enriched with the /dev nodes it owns. include_hubs=True keeps root/internal hubs;
    category filters to a single category (e.g. 'camera')."""
    if not _supported():
        return urirun.fail("USB enumeration requires Linux sysfs (/sys/bus/usb/devices)",
                           connector=CONNECTOR_ID)
    devices = _all_devices()
    if not include_hubs:
        devices = [d for d in devices if not d["isHub"]]
    wanted = category.strip().lower()
    if wanted:
        devices = [d for d in devices if d["category"] == wanted or wanted in d["roles"]]
    return urirun.ok(connector=CONNECTOR_ID, kind="device-list", live=False, count=len(devices),
                     summary=_summary(devices), devices=devices)


@USB.handler("devices/query/find", isolated=True,
             meta={"label": "Find USB devices by name, vendor, product or category", "cliAlias": "find"})
def find(query: str = "", vendor_id: str = "", product_id: str = "",
         category: str = "", include_hubs: bool = True) -> dict[str, Any]:
    """Search the connected USB devices. `query` matches (case-insensitively) the device
    name, manufacturer, product or vendor:product id; `vendor_id`/`product_id`/`category`
    narrow further. Returns every matching device."""
    if not _supported():
        return urirun.fail("USB enumeration requires Linux sysfs (/sys/bus/usb/devices)",
                           connector=CONNECTOR_ID)
    devices = _all_devices()
    if not include_hubs:
        devices = [d for d in devices if not d["isHub"]]
    q = query.strip().lower()
    vid = vendor_id.strip().lower().removeprefix("0x")
    pid = product_id.strip().lower().removeprefix("0x")
    cat = category.strip().lower()

    def matches(d: dict[str, Any]) -> bool:
        if vid and d["vendorId"] != vid:
            return False
        if pid and d["productId"] != pid:
            return False
        if cat and d["category"] != cat and cat not in d["roles"]:
            return False
        if q:
            hay = " ".join(str(d.get(k, "")) for k in
                           ("name", "manufacturer", "product", "id", "category")).lower()
            if q not in hay:
                return False
        return True

    matched = [d for d in devices if matches(d)]
    return urirun.ok(connector=CONNECTOR_ID, kind="device-list", live=False, query=query, count=len(matched), devices=matched)


@USB.handler("cameras/query/list", isolated=True,
             meta={"label": "List USB cameras / webcams", "cliAlias": "cameras"})
def cameras() -> dict[str, Any]:
    """List USB cameras and webcams (USB video-class devices), each with its /dev/video*
    capture nodes — the entry point for the camera connector to grab a frame."""
    if not _supported():
        return urirun.fail("USB enumeration requires Linux sysfs (/sys/bus/usb/devices)",
                           connector=CONNECTOR_ID)
    cams = [d for d in _all_devices() if d["category"] == "camera" or "camera" in d["roles"]]
    for cam in cams:
        cam["videoNodes"] = [n["path"] for n in cam["devNodes"] if n["type"] == "video"]
    return urirun.ok(connector=CONNECTOR_ID, kind="device-list", live=False, count=len(cams), cameras=cams)


@USB.handler("input/query/list", isolated=True,
             meta={"label": "List USB input devices (keyboards, mice, HID)", "cliAlias": "input"})
def input_devices(kind: str = "") -> dict[str, Any]:
    """List USB human-interface devices — keyboards, mice and other HID gear — with the
    /dev/input nodes they own. `kind` filters to 'keyboard', 'mouse' or 'hid'."""
    if not _supported():
        return urirun.fail("USB enumeration requires Linux sysfs (/sys/bus/usb/devices)",
                           connector=CONNECTOR_ID)
    roles = {"keyboard", "mouse", "hid", "gamepad"}
    want = kind.strip().lower()
    devices = []
    for d in _all_devices():
        dev_roles = set(d["roles"]) & roles
        if not dev_roles:
            continue
        if want and want not in d["roles"]:
            continue
        devices.append(d)
    return urirun.ok(connector=CONNECTOR_ID, kind="device-list", live=False, count=len(devices), devices=devices)


def urirun_bindings() -> dict[str, Any]:
    """Serializable v2 bindings for this connector."""
    return USB.bindings()


def connector_manifest() -> dict[str, Any]:
    """Full manifest: prose plus derived routes."""
    return USB.manifest(urirun.load_manifest(__package__))


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point."""
    return USB.cli(argv, manifest_prose=urirun.load_manifest(__package__))


if __name__ == "__main__":
    raise SystemExit(main())
