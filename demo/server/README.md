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

- No host port is published. Docker 29 suppresses published ports on internal-only networks;
  obtain this project's container IP with `docker inspect` and preview it through an
  authorised SSH local-port forward. Bind the local end only to `127.0.0.1`.
- A dedicated internal network has no shared application/database network membership.
- `traefik.enable=false`; no changes to existing proxy routes, ports 80/443 or certificates.
- Hard limits: 0.75 CPU, 1.5 GiB memory including swap, 256 processes; low relative CPU shares.
- Unprivileged UID, read-only image, no added capabilities or host/Docker-socket mounts.
- The app is launched by absolute path with `/tmp` as its working directory: Ultralytics
  creates a `runs/` directory even with output saving disabled. Model/config paths remain
  relative to their source tree, so this changes storage location, not inference settings.
- A dedicated cache volume holds temporary uploads/results; the app's six-hour TTL applies.
  It is not a disk quota: check free disk space before public release and while operating.
- Logs rotate at two 5 MB files. Model downloads and analytics are disabled.

For example, after reading the actual private container IP on the server, use
`ssh -N -L 127.0.0.1:17861:<private-container-ip>:7860 <approved-server>` on the development
machine. Do not guess the IP or add a public host-port mapping to work around isolation.
Verify an actual two-minute upload through the tunnel, not only the health endpoint.
Check existing-site HTTP responses and container start/restart counts before and after.
Resource limits reduce contention; they do not prove zero performance impact.

Stopping only the new demo preserves its cache and all other services:

```bash
docker compose -f /opt/trafficwatch-demo/compose.yaml stop demo
```

Never run a global Docker prune, restart Docker, or run Compose against another project's
configuration. Public HTTPS routing is a separate, explicitly approved release step.

## Approved HTTPS release

`compose.public.yaml` adds a small, read-only Nginx gateway on the pre-existing `apps`
proxy network. It does not attach the model to that network, mount proxy credentials,
change existing routers or restart Traefik. The deployment assumes the inspected host's
`websecure` entry point and `letsencrypt` resolver; verify those names on another host.
The hostname is mandatory and must already resolve to the chosen server.
The public override enables forwarded-header trust only behind this isolated gateway,
which sets the external HTTPS scheme. See the official
[FastAPI proxy guidance](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).

```bash
export TRAFFICWATCH_DEMO_HOST=<approved-hostname>
docker compose -f /opt/trafficwatch-demo/compose.yaml \
  -f /opt/trafficwatch-demo/compose.public.yaml config -q
docker compose -f /opt/trafficwatch-demo/compose.yaml \
  -f /opt/trafficwatch-demo/compose.public.yaml up -d --no-build
```

Copy `nginx.conf` and the public Compose file into the dedicated directory before this step.
Test HTTPS certificate validation and an actual public upload, including the page embedded
in the public website. An uploaded two-minute clip must complete with visible progress,
annotated playback and JSON download; a 124-second clip must be rejected clearly.
Only then put the verified HTTPS address in both `demo_url` and `demo_embed_url`.
