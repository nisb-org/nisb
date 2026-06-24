# Install NISB on a Fresh VPS

NISB is a self-hosted AI workspace for notes, files, documents, RSS, evidence, Rooms, and MCP capabilities.

This guide installs NISB on a fresh Ubuntu VPS using Docker Compose and Caddy HTTPS.

---

## What you will get

After installation, you should have:

- NISB web UI available at `https://YOUR_DOMAIN.com`
- NISB backend API running behind Caddy
- Room-scoped MCP endpoint available through Caddy
- Automatic HTTPS handled by Caddy
- Docker Compose-managed services:
  - `mcp-nisb`
  - `nisb-web`
  - `caddy`

---

## Requirements

Recommended starting point:

- Fresh Ubuntu 24.04 VPS
- Root SSH access
- At least 1 vCPU / 1 GB RAM for a minimal test install
- A domain or subdomain pointing to the VPS public IP
- TCP ports `80` and `443` open on the VPS/firewall
- Optional LLM/API keys for model-backed features

Caddy requires a real hostname in the Caddyfile and reachable HTTP/HTTPS ports to obtain and serve HTTPS certificates.

---

## Deployment layout

The recommended deployment directory is:

```bash
/opt/mcp-gateway
```

Expected project layout:

```text
/opt/mcp-gateway/
├── docker-compose.yml
├── caddy/
│   ├── Caddyfile
│   └── Caddyfile.example
├── mcp-nisb/
│   ├── .env.example
│   ├── requirements.txt
│   ├── requirements.in
│   └── ...
├── nisb-web/
│   └── ...
└── nisb/
    ├── README.md
    ├── INSTALL.md
    └── ...
```

Important:

- Run Docker Compose commands from `/opt/mcp-gateway`.
- The documentation directory is `/opt/mcp-gateway/nisb`.
- The backend environment file is `/opt/mcp-gateway/mcp-nisb/.env`.
- Do not commit a filled `.env` file.
- Do not store user data only inside containers.

---

## Upload files

Upload or clone the NISB project to:

```bash
/opt/mcp-gateway
```

Example from a local machine:

```bash
rsync -avzhP --delete \
  /path/to/mcp-gateway/ \
  root@YOUR_SERVER_IP:/opt/mcp-gateway/
```

If you maintain server-specific deployment files, avoid overwriting them accidentally:

```bash
rsync -avzhP --delete \
  --exclude='docker-compose.yml' \
  --exclude='caddy/Caddyfile' \
  /path/to/mcp-gateway/ \
  root@YOUR_SERVER_IP:/opt/mcp-gateway/
```

After upload, SSH into the VPS:

```bash
ssh root@YOUR_SERVER_IP
```

Then check:

```bash
cd /opt/mcp-gateway

ls -lah docker-compose.yml caddy/Caddyfile
ls -lah mcp-nisb/.env.example
```

Do not continue if these files are missing.

---

## Configure environment

Copy the backend environment template:

```bash
cd /opt/mcp-gateway

cp mcp-nisb/.env.example mcp-nisb/.env
```

Generate a strong secret key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Edit:

```bash
vim mcp-nisb/.env
```

At minimum, replace:

```env
NISB_SECRET_KEY=change-me
```

with the generated value.

Optional provider keys:

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
SERPER_API_KEY=
PEXELS_API_KEY=
EXA_API_KEY=
```

Default embedding settings:

```env
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
```

User system defaults:

```env
NISB_USER_ID=nisb_default_user
NISB_USER_SYSTEM_ENABLED=true
NISB_REGISTRATION_ENABLED=false
```

For a private single-user deployment, keeping registration disabled is recommended:

```env
NISB_REGISTRATION_ENABLED=false
```

Never publish:

```text
mcp-nisb/.env
```

---

## Configure Caddy

If you do not already have a deployment Caddyfile, copy the example:

```bash
cd /opt/mcp-gateway

cp caddy/Caddyfile.example caddy/Caddyfile
```

Edit:

```bash
vim caddy/Caddyfile
```

Replace:

```text
nisb.example.com
www.nisb.example.com
```

with your real domain.

Important: Caddyfile site labels must be plain hostnames, not Markdown links.

Correct:

```caddyfile
www.YOUR_DOMAIN.com {
  redir https://YOUR_DOMAIN.com{uri} permanent
}

YOUR_DOMAIN.com {
  handle /health {
    respond "Web OK" 200
  }

  handle {
    reverse_proxy nisb-
  }
}
```

Wrong:

```caddyfile
[www.YOUR_DOMAIN.com](https://www.YOUR_DOMAIN.com) {
  redir https://YOUR_DOMAIN.com{uri} permanent
}
```

The full NISB Caddyfile should include routes for:

- `/api/*`
- `/editor/api/*`
- `/api/mcp/stream`
- `/editor/api/mcp/stream`
- `/nisb/mcp*`
- `/assets*`
- `/health`
- frontend fallback to `nisb-web:5173`

The old KB MCP route is retired and may return:

```caddyfile
handle /kb/mcp* {
  respond "KB MCP service has been retired." 410
}
```

Check the configured domains:

```bash
grep -nE '^[a-zA-Z0-9_.-]+[[:space:]]*\{|redir https://' caddy/Caddyfile || true
```

---

## Configure DNS

Set your domain DNS to the VPS public IP.

Example:

```text
YOUR_DOMAIN.com      A      YOUR_SERVER_IP
www.YOUR_DOMAIN.com  A      YOUR_SERVER_IP
```

Check DNS:

```bash
DOMAIN=YOUR_DOMAIN.com

dig +short A "$DOMAIN" @1.1.1.1 || true
dig +short AAAA "$DOMAIN" @1.1.1.1 || true
```

If you do not use IPv6, remove incorrect AAAA records.

If you use Cloudflare, start with DNS-only mode while testing HTTPS. Cloudflare proxy/rules can interfere with ACME HTTP/TLS validation if configured incorrectly.

Caddy can automatically manage HTTPS when it knows the hostname it is serving and the domain can reach the server on the required ports.[web:112]

---

## Install Docker

Run these commands on the VPS as root.

Docker’s official Ubuntu installation path uses Docker’s apt repository and installs Docker Engine, CLI, containerd, Buildx, and the Compose plugin.[web:39]

```bash
cd /opt/mcp-gateway

apt-get update

apt-get remove -y \
  docker.io \
  docker-compose \
  docker-compose-v2 \
  docker-doc \
  podman-docker \
  containerd \
  runc || true

apt-get update
apt-get install -y ca-certificates curl

install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

chmod a+r /etc/apt/keyrings/docker.asc

tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF_DOCKER
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF_DOCKER

apt-get update

apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

Start and verify Docker:

```bash
systemctl daemon-reload
systemctl reset-failed docker docker.socket containerd || true

systemctl enable --now containerd.service
systemctl enable --now docker.service

for i in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then
    echo "Docker OK"
    break
  fi
  echo "waiting for Docker... $i/30"
  sleep 2
done

docker --version
docker compose version
systemctl status docker --no-pager -l | sed -n '1,40p'
```

Do not continue until you see:

```text
Docker OK
```

---

## Validate NISB config

Run:

```bash
cd /opt/mcp-gateway

echo "==> Check required files"
ls -lah docker-compose.yml caddy/Caddyfile mcp-nisb/.env

echo "==> Check that secret key was changed"
grep '^NISB_SECRET_KEY=' mcp-nisb/.env

echo "==> Resolve Docker Compose config"
docker compose config >/tmp/nisb-compose.resolved.yml

echo "==> Show services"
docker compose config --services
```

Expected core services:

```text
mcp-nisb
nisb-web
caddy
```

If `docker compose config` fails, fix `docker-compose.yml` before continuing.

If `NISB_SECRET_KEY=change-me` is still present, stop and edit `mcp-nisb/.env`.

---

## Build NISB

Run:

```bash
cd /opt/mcp-gateway

echo "==> Build NISB images"
docker compose build mcp-nisb nisb-web
```

The first build can take several minutes on a small VPS.

On a 1 vCPU / 1 GB RAM VPS, slow Python, Node, and frontend build steps are normal.

Note for maintainers:

- `mcp-nisb/requirements.in` is the human-maintained dependency input file.
- Release builds should use the pinned `mcp-nisb/requirements.txt`.
- Do not regenerate dependency lock files casually during a user installation.

---

## Start NISB

Run:

```bash
cd /opt/mcp-gateway

echo "==> Start NISB services"
docker compose up -d mcp-nisb nisb-web caddy

echo "==> Show containers"
docker compose ps
```

`docker compose up` creates and starts services from the Compose file; with `-d`, services run in the background.[web:203]

Expected result:

```text
mcp-caddy   Up
mcp-nisb    Up
nisb-web    Up
```

Some services may show `health: starting` for a short time.

Wait 30-60 seconds and run:

```bash
docker compose ps
```

---

## Check logs

Run:

```bash
echo "==> Caddy logs"
docker logs --tail=160 mcp-caddy

echo "==> NISB backend logs"
docker logs --tail=120 mcp-nisb

echo "==> NISB web logs"
docker logs --tail=80 nisb-web
```

Useful Caddy log signs:

```text
obtaining certificate
certificate obtained successfully
serving initial configuration
```

If Caddy is still obtaining a certificate, wait and test again.

---

## Verify HTTP and HTTPS

Replace `YOUR_DOMAIN.com` with your domain:

```bash
DOMAIN=YOUR_DOMAIN.com

echo "==> DNS check"
dig +short A "$DOMAIN" @1.1.1.1 || true
dig +short AAAA "$DOMAIN" @1.1.1.1 || true

echo "==> HTTP check"
curl -I "http://$DOMAIN" --max-time 10 || true

echo "==> HTTPS check"
curl -vkI "https://$DOMAIN" --max-time 20 || true

echo "==> App health check"
curl -I "https://$DOMAIN/health" --max-time 20 || true
```

Expected HTTP result:

```text
HTTP/1.1 308 Permanent Redirect
Location: https://YOUR_DOMAIN.com/
```

Expected health result:

```text
HTTP/2 200
```

or:

```text
HTTP/1.1 200 OK
```

The `/health` endpoint should return:

```text
Web OK
```

---

## Open the UI

Open:

```text
https://YOUR_DOMAIN.com
```

You should see the NISB web UI.

---

## MCP endpoint

The default Room-scoped MCP publish route is exposed through Caddy at:

```text
https://YOUR_DOMAIN.com/nisb/mcp
```

The backend service behind this route is:

```text
mcp-nisb:8005
```

Do not expose private workspace files, private filesystem paths, private memory, or raw bearer tokens publicly.

---

## Update NISB

To deploy new code:

```bash
cd /opt/mcp-gateway

docker compose build mcp-nisb nisb-web
docker compose up -d mcp-nisb nisb-web caddy
docker compose ps
```

Then verify:

```bash
DOMAIN=YOUR_DOMAIN.com

curl -I "https://$DOMAIN/health" --max-time 20 || true
docker logs --tail=120 mcp-nisb
docker logs --tail=80 nisb-web
docker logs --tail=120 mcp-caddy
```

---

## Stop NISB

To stop services without deleting data:

```bash
cd /opt/mcp-gateway

docker compose stop
```

To start again:

```bash
docker compose up -d mcp-nisb nisb-web caddy
```

---

## Do not delete volumes casually

Avoid this unless you intentionally want to remove generated data and Caddy certificate storage:

```bash
docker compose down -v
```

For normal restarts, use:

```bash
docker compose restart
```

or:

```bash
docker compose up -d mcp-nisb nisb-web caddy
```

---

## Troubleshooting

### HTTPS shows `SSL_ERROR_INTERNAL_ERROR_ALERT`

Usually this means Caddy does not have a usable certificate for the domain.

Check:

```bash
DOMAIN=YOUR_DOMAIN.com

dig +short A "$DOMAIN" @1.1.1.1 || true
dig +short AAAA "$DOMAIN" @1.1.1.1 || true

docker logs --tail=200 mcp-caddy
curl -vkI "https://$DOMAIN" --max-time 20 || true
```

Common causes:

- Caddyfile uses a different domain than the one you opened
- Caddyfile contains Markdown-style links instead of plain hostnames
- DNS points to the wrong IP
- Wrong or stale AAAA record
- Cloudflare proxy/rules interfering with ACME challenge
- Ports `80` or `443` blocked
- Caddy certificate volume was deleted and Caddy is still obtaining a new certificate

---

### UI opens but API fails

Check backend container logs:

```bash
docker logs --tail=200 mcp-nisb
```

Check that `mcp-nisb` is running:

```bash
docker compose ps
```

Check API routes in Caddyfile:

```bash
sed -n '1,260p' caddy/Caddyfile
```

---

### Caddy is healthy but domain fails

Check whether Caddy is serving the correct domain:

```bash
docker logs --tail=200 mcp-caddy | grep -E 'automatic TLS|domains|certificate|challenge|error|obtained' || true
```

Your Caddy logs should mention your actual domain.

---

### Docker is installed but not ready

Run:

```bash
systemctl status docker --no-pager -l | sed -n '1,80p'
journalctl -u docker --no-pager -n 120
docker info
```

Then restart safely:

```bash
systemctl reset-failed docker docker.socket containerd || true
systemctl enable --now containerd.service
systemctl enable --now docker.service
```

---

### Build is slow on a small VPS

Check resources:

```bash
free -h
df -h /
docker system df
```

The first build is expected to be slower because Docker downloads base images and installs Python/Node dependencies.

---

### 1 vCPU VPS resource limits

If deploying on a 1 vCPU VPS, make sure `docker-compose.yml` does not request more than the machine can provide.

For example, avoid setting a service to use `2.0` CPUs on a 1 vCPU VPS.

---

### Secret key was not changed

Check:

```bash
grep '^NISB_SECRET_KEY=' mcp-nisb/.env
```

If you see:

```text
NISB_SECRET_KEY=change-me
```

generate a new value:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then edit:

```bash
vim mcp-nisb/.env
```

Restart services:

```bash
docker compose up -d mcp-nisb nisb-web caddy
```

---

## Fresh VPS checklist

Before saying the install is complete, run:

```bash
cd /opt/mcp-gateway

docker compose ps

DOMAIN=YOUR_DOMAIN.com

curl -I "http://$DOMAIN" --max-time 10 || true
curl -I "https://$DOMAIN/health" --max-time 20 || true

docker logs --tail=80 mcp-caddy
docker logs --tail=80 mcp-nisb
docker logs --tail=80 nisb-web
```

Install is complete when:

- `mcp-caddy` is up
- `mcp-nisb` is up
- `nisb-web` is up
- `https://YOUR_DOMAIN.com/health` returns `Web OK`
- The browser can open `https://YOUR_DOMAIN.com`
- `mcp-nisb/.env` exists
- `NISB_SECRET_KEY` is not `change-me`

---

## Remote Install

If you want NISB running on your VPS without doing the setup yourself, remote install support is available:

```text
https://ko-fi.com/nisbdev
```

Remote Install usually covers:

- Docker setup
- Docker Compose deployment
- Caddy HTTPS setup
- Basic UI health check
- Basic backend/container verification
- Short handover notes

Commercial licensing, closed-source integration, hosted/SaaS usage, team deployment, and private redistribution require a separate commercial license discussion.

