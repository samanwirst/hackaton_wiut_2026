# Private server staging

This is the CPU demo, **not** the offline GPU evaluation image at the repository root.
It reuses the tested app, configuration and YOLO11n weights without changing inference.

Build on a development machine, not on a shared production host:

```bash
STAGING_DIR=$(mktemp -d .cache/server-demo.XXXXXX)
bash demo/prepare_space.sh "$STAGING_DIR/space"
cp demo/server/Dockerfile "$STAGING_DIR/space/Dockerfile"
docker build -t trafficwatch-demo:20260927 "$STAGING_DIR/space"
```

Transfer the image with `docker save` / `docker load` and copy only this directory's
`compose.yaml` into a new dedicated deployment directory. Do not copy original videos,
credentials, an entire development environment or another site's Compose file.
The base Python image is digest-pinned; `demo/requirements.txt` pins the principal runtime
dependencies. Save the built image ID and installed-package list with deployment evidence.

After confirming the destination is unused, start only this project:

```bash
docker compose -f /opt/trafficwatch-demo/compose.yaml config -q
docker compose -f /opt/trafficwatch-demo/compose.yaml up -d --no-build
docker compose -f /opt/trafficwatch-demo/compose.yaml ps
```

Defaults deliberately **do not publish a demo**:

- Bind only `127.0.0.1:17860`; preview through an authorised SSH local-port forward.
- A dedicated internal network has no shared application/database network membership.
- `traefik.enable=false`; no changes to existing proxy routes, ports 80/443 or certificates.
- Hard limits: 0.75 CPU, 1.5 GiB memory including swap, 256 processes; low relative CPU shares.
- Unprivileged UID, read-only image, no added capabilities or host/Docker-socket mounts.
- A dedicated cache volume holds temporary uploads/results; the app's six-hour TTL applies.
  It is not a disk quota: check free disk space before public release and while operating.
- Logs rotate at two 5 MB files. Model downloads and analytics are disabled.

Verify an actual two-minute upload through the tunnel, not only the health endpoint.
Check existing-site HTTP responses and container start/restart counts before and after.
Resource limits reduce contention; they do not prove zero performance impact.

Stopping only the new demo preserves its cache and all other services:

```bash
docker compose -f /opt/trafficwatch-demo/compose.yaml stop demo
```

Never run a global Docker prune, restart Docker, or run Compose against another project's
configuration. Public HTTPS routing is a separate, explicitly approved release step.
