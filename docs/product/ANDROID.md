# Getting GeoFatali onto a phone

Two different things, in order: a test APK you sideload yourself, and a Google
Play release. The first takes minutes. The second needs decisions only you can
make.

---

## 1. A test APK on your own phone

### Where the APK comes from

It is built by GitHub Actions, not on a laptop. Every push runs
`.github/workflows/android.yml`, which analyzes, tests and builds the app.

1. Open the repository on GitHub → **Actions** → the most recent **Android
   build** run.
2. Scroll to **Artifacts** at the bottom.
3. Download **geofatali-apk**. It arrives as a zip; unzip it to get
   `app-release.apk`.

### Putting it on the phone

Email it to yourself, put it in Drive, or plug the phone in and copy it across.
Open the file on the phone and Android will ask you to allow installation from
that app (Settings → Apps → Special access → Install unknown apps). This is
normal for an app that did not come from the Play Store.

### It is signed with a debug key

Until you create an upload keystore (below), the APK is signed with Android's
debug key. That is fine for testing on your own phone. It is **not** acceptable
to Google Play, and a debug-signed build cannot be updated by a properly signed
one later — you have to uninstall first.

---

## 2. You need a backend it can reach

This is the part people are surprised by. **The app stores nothing on the
phone.** It is a client for a GeoFatali server, and it signs you in against
that server.

The app finds the server by itself. On first launch it tries, in order:

1. a server it connected to before;
2. the address compiled into the build;
3. **a sweep of the local network** — it takes its own address on the wifi,
   walks the /24 it sits in, and asks each host whether it is a GeoFatali
   server. The first one that returns a proper health document wins and is
   remembered.

So the usual case is: install the APK, start the backend, open the app, sign in
with an email. No address is ever typed.

The sweep only covers the /24 the phone is on, and only private ranges — a
server on another subnet or behind a router will not be found, and those go
through **Settings → Server**. A host merely answering on port 8000 is not
accepted: it has to return the health document with an engine version in it, so
a router admin page or a printer is not mistaken for a backend.

For a hosted deployment the address is compiled into the build, so no sweep
happens at all. Set it with a repository variable named
`GEOFATALI_API_URL` (GitHub → Settings → Secrets and variables → Actions →
Variables), for example `https://api.geofatali.com`. The CI build passes it
through as a `--dart-define`.

With no variable set, the build falls back to `http://10.0.2.2:8000` — the
Android emulator's alias for the host machine, which is useful for `flutter
run` and useless on a real phone. The build prints a warning saying so, and a
Play release refuses to build at all without a real address.

Anyone running their own instance can override it in the app: **Settings →
Server → Use my own server**. That is the escape hatch for self-hosting, not
the front door.

Either way, the API has to be running somewhere the phone can reach, with a
PostgreSQL + PostGIS database behind it.

### Quickest: your laptop, same wifi as the phone

```bash
cp .env.example .env
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
docker compose up
```

That starts PostgreSQL with PostGIS, applies the migrations and serves the API
on port 8000, bound to every interface. It prints the address to use:

```
  GeoFatali API 0.1.0

  On this network:  http://192.168.100.16:8000
  On this machine:  http://127.0.0.1:8000
  Schema:           0002
```

Use the "On this network" line in the app.

Without Docker, the same thing by hand. Note the migration step — skip it and
every request fails with "relation does not exist":

```bash
cd services/api
export DATABASE_URL=postgresql://user:pass@localhost/geofatali
export JWT_SECRET=$(openssl rand -hex 32)
PYTHONPATH=../engineering-engine python -m app.db.cli migrate
PYTHONPATH=../engineering-engine uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` matters: the default only listens on the laptop itself.

Find the laptop's address on the wifi (`ip addr` on Linux, `ipconfig getifaddr
en0` on macOS) and enter it under **Settings → Server → Use my own server** —
for example `192.168.1.24:8000`.

A private address entered without a port gets **8000**, which is what the
backend runs on. Type the port explicitly and that is what is used.

### When it will not connect

Check these in order — the first two account for almost every case:

1. **The port.** `curl http://<address>:8000/health` from the laptop itself
   should return JSON with an engine version. If that fails, nothing else will.
2. **The bind address.** Without `--host 0.0.0.0` uvicorn listens only on the
   laptop, and the phone cannot see it however good the network is.
3. **The network.** Phone on wifi, not mobile data, and the same wifi. Guest
   networks and "client isolation" on a router block device-to-device traffic
   entirely.
4. **The firewall.** `sudo ufw allow 8000` on Linux; on macOS allow incoming
   connections for Python when prompted.

A timeout rather than an immediate refusal points at 3 or 4: packets are being
dropped rather than rejected, which means they are not reaching the process.

The app allows plain HTTP to private addresses only (`10.x`, `172.16–31.x`,
`192.168.x`, localhost) — see
`apps/mobile/android/app/src/main/res/xml/network_security_config.xml`. Anything
on the public internet must be HTTPS, because a bearer token sent in clear over
the open internet is a credential handed to whoever is listening.

### Properly: a hosted instance

Any host that runs a container and a PostgreSQL with PostGIS. It needs
`DATABASE_URL` and `JWT_SECRET` set, and the app then points at your domain over
HTTPS. The service refuses to start in production without either of them rather
than falling back to a default that would be the same on every deployment.

---

## 3. Google Play

### Before anything else

- **A Play Console account.** One-off 25 USD. Individual accounts now need
  identity verification, and new personal developer accounts must run a closed
  test with real testers before they can go to production. Check the current
  rules in the Console — they change.
- **A privacy policy at a public URL.** Required. The app collects an email
  address, a password and the project data people enter, and stores it on a
  server you operate — say exactly that.
- **A Data safety declaration** in the Console matching what the app actually
  does: account creation, project data, no advertising ID, no third-party
  sharing, data encrypted in transit, and that users can request deletion.

### Create the upload keystore

Do this once. **If you lose this file or its passwords you cannot update your
own app** — back it up somewhere you trust.

```bash
keytool -genkey -v -keystore upload-keystore.jks \
  -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

Then add four secrets in GitHub → Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 upload-keystore.jks` |
| `ANDROID_STORE_PASSWORD` | the store password you chose |
| `ANDROID_KEY_PASSWORD` | the key password you chose |
| `ANDROID_KEY_ALIAS` | `upload` |

With those present the workflow signs properly. Push a tag to build the App
Bundle Play wants:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Download the **geofatali-aab** artifact and upload `app-release.aab` in the Play
Console.

### What the listing has to say

This app gives geotechnical and foundation guidance. Be careful and be plain:

- It is a **preliminary screening tool**, not a site investigation and not a
  foundation design. The app says this on its first screen, on every project and
  on every report, and the listing should too.
- Do not claim accuracy for the AI soil classification. There is no evaluation
  dataset yet (spec section 52), so there is nothing to back a number up with.
- Say that final design must be sealed by a registered engineer.

Overstating what this does is both a Play policy risk and, far more seriously,
a way for someone to get hurt.

---

## Current state

| | |
|---|---|
| Sign in, projects, boreholes, soil layers, SPT | Working |
| Bearing capacity, foundation screening, construction steps | Working |
| Reports | Issued and listed; the document is stored, but there is no PDF yet |
| Soil photos and AI analysis | Not built — needs object storage and a vision provider |
| Offline mode | Not built. The app needs the server for everything |

Offline is the one that will matter most in the field: a borehole log is exactly
the thing you record where there is no signal. It is the next piece of work on
the client.
