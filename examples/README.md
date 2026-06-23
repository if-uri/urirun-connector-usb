# Examples — urirun-connector-usb

```bash
# Everything plugged in (skip hubs):
urirun-usb list

# As JSON, including hubs:
urirun-usb list --include_hubs true

# Cameras only, with their /dev/video* capture nodes:
urirun-usb cameras

# Keyboards and mice:
urirun-usb input
urirun-usb input --kind keyboard

# Find a device by name / id:
urirun-usb find --query webcam
urirun-usb find --vendor_id 046d
```

Over a urirun node the same routes are reachable as URIs, e.g.
`usb://host/cameras/query/list` — used by the camera connector to discover which
`/dev/video*` to capture from before taking a photo and OCR-ing it.
