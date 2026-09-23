# Hosting GeoFatali

The app is a client. Once the backend is on the internet with a real
certificate, the app connects from anywhere — mobile data, another building,
anyone who installs it from the Play Store — and nobody ever thinks about an
address again.

This takes about twenty minutes.

---

## What you need

- **A machine on the internet.** Any small VPS does: 1 vCPU and 1 GB of RAM is
  enough to start. Hetzner, DigitalOcean, Linode, Vultr, or a Kenyan provider —
  it makes no difference, the whole thing is containers.
- **A domain name**, with an A record pointing at that machine. A subdomain is
  fine: `api.yourdomain.com`.
- **Docker** on the machine: `curl -fsSL https://get.docker.com | sh`

---

## Deploy

```bash
# on the server
git clone https://github.com/fatalibuilders-cloud/geofatali.git
cd geofatali/deploy
cp .env.prod.example .env
```

Edit `.env`:

```ini
DOMAIN=api.yourdomain.com
ACME_EMAIL=you@yourdomain.com
POSTGRES_PASSWORD=<openssl rand -base64 24>
JWT_SECRET=<openssl rand -hex 32>
```

Then:

```bash
docker compose -f docker-compose.prod.yml up -d
```

That starts PostgreSQL with PostGIS, applies the migrations, serves the API,
and gets a Let's Encrypt certificate. Check it:

```bash
curl https://api.yourdomain.com/health
```

You want `{"status":"ok", ...,"database":{"reachable":true,"schema_version":"0002"}}`.

The certificate needs port 80 reachable from the internet on first start, so
open 80 and 443 on the provider's firewall.

---

## Point the app at it

In GitHub → **Settings → Secrets and variables → Actions → Variables**, add:

| Variable | Value |
|---|---|
| `GEOFATALI_API_URL` | `https://api.yourdomain.com` |

Push anything, or re-run the Android workflow. Every APK from then on has that
address compiled in, connects immediately, and never sweeps the local network.

---

## What is exposed

Only Caddy publishes ports. The API and the database sit on an internal
network and cannot be reached from outside, so the only way in is TLS on 443.

The API refuses to start in production without a real `DATABASE_URL` and
`JWT_SECRET`, rather than falling back to a default that every deployment
would share.

---

## Before real users

Two things this setup does **not** do yet, and you should know which:

- **No rate limiting on `/auth/*`.** Registration and sign-in are open
  endpoints. On the public internet that invites both password guessing and
  junk accounts. Worth adding before you let anyone in.
- **No backups.** The database lives in a Docker volume. A one-line nightly
  `pg_dump` to object storage is enough, and it is the difference between a
  bad afternoon and losing everyone's site data.

---

## Updating

```bash
cd geofatali && git pull
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Migrations apply on start, so a schema change needs nothing extra. Calculations
and reports are append-only, so an upgrade never rewrites existing records.

---

## Day to day

```bash
docker compose -f docker-compose.prod.yml logs -f api   # what it is doing
docker compose -f docker-compose.prod.yml ps            # what is running
docker compose -f docker-compose.prod.yml restart api   # after changing .env

# a backup worth having
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U geofatali geofatali | gzip > backup-$(date +%F).sql.gz
```
