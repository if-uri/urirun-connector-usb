# urirun-connector-usb

**USB devices** — connector ekosystemu [ifURI / urirun](https://github.com/if-uri/urirun).
Schemat URI: `usb://`

Enumerate and classify the USB devices plugged into a computer over `usb://` URIs. Reads the kernel's sysfs view (no root, no extra deps), labels each device by USB class codes (**camera/webcam, keyboard, mouse, audio, storage, hub, printer, bluetooth, serial, smart-card/security-key**) and maps it to the `/dev` nodes it owns (`/dev/video*`, `/dev/input/*`, `/dev/ttyUSB*`, `/dev/hidraw*`).

## Routes (URI)

| URI | What it does |
| --- | --- |
| `usb://host/devices/query/list` | List every device with category, roles, ids and device nodes (`include_hubs`, `category` filters) |
| `usb://host/devices/query/find` | Search by `query` / `vendor_id` / `product_id` / `category` |
| `usb://host/cameras/query/list` | Only USB cameras/webcams, with their `/dev/video*` nodes |
| `usb://host/input/query/list` | Keyboards, mice and other HID, with their `/dev/input` nodes (`kind` filter) |
| `usb://host/devices/query/probe` | Host support + helper availability (lsusb, pyusb) |

## Opis

`usb://` answers *"what is physically connected to this machine?"* as a first-class URI instead of ad-hoc `lsusb` parsing. Each device gets a friendly **category** (derived from its USB class codes), a list of **roles** (a combo device can be both `keyboard` and `mouse`), vendor/product ids, and the **device nodes** it exposes. `usb://host/cameras/query/list` is the discovery layer the [camera connector](../urirun-connector-camera) builds on — it returns each webcam together with the `/dev/video*` node to capture from.

Built on Linux sysfs (`/sys/bus/usb/devices`) and `/sys/class/*` node mapping. `lsusb` is used only to fill in nicer vendor/product names when a device omits its own descriptor strings.

## Wymagania

- **system:** Linux sysfs (`/sys/bus/usb`)
- **python:** urirun
- **optional:** `lsusb` (nicer names), `pyusb`

## Instalacja (dev)

```bash
pip install -e .
pytest -q
```

## Szybki start

```bash
# list non-hub devices
urirun-usb list

# just the cameras (and their /dev/video* nodes)
urirun-usb cameras

# find a Logitech device
urirun-usb find --query logitech
```

## Powiązane

- Rdzeń: [if-uri/urirun](https://github.com/if-uri/urirun)
- Kamera: [urirun-connector-camera](../urirun-connector-camera) — capture + crop + OCR
- Hub connectorów: [connect.ifuri.com](https://connect.ifuri.com)

---
Kategoria: Hardware · Słowa kluczowe: usb, devices, hardware, camera, webcam, keyboard, mouse, hid, lsusb, sysfs · Wydawca: if-uri
