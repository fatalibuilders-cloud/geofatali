# GeoFatali on the desktop

The desktop app is the same application as the phone app, built from the same
`apps/app` directory for Windows, macOS and Linux. It is not a separate
product and it does not have a separate account.

## How it "connects with the mobile one"

It does not talk to the phone. Both talk to the same backend.

Every project, borehole, soil layer, calculation and report lives in the
PostgreSQL database behind the API. Neither client stores any of it — a phone
holds nothing but its session token, and so does a laptop. So:

* sign in on the desktop with **the same email** used on the phone, and the
  same projects are there;
* a layer logged standing over a trial pit is on the laptop before anyone gets
  back to the office;
* a calculation run at a desk is on the phone on the next screen refresh.

There is nothing to pair, nothing to sync, and no file to move between them.
If the two ever showed different data, that would be a bug in the backend, not
something a user should have to reconcile.

## Finding the backend

The app is never asked for a server address. On launch it tries, in order:

1. the address it remembered last time;
2. the address this build was made with (`GEOFATALI_API_URL`);
3. **on desktop only**, the machine it is running on — `127.0.0.1:8000`;
4. failing all of those, a sweep of the local network.

Step 3 is the one that matters for a laptop. The overwhelmingly common desktop
case is `docker compose up` running in a terminal on that same laptop, and the
network sweep can never find it: the sweep deliberately skips every address the
machine itself holds, which is exactly where the server is.

So on a laptop the whole setup is:

```bash
cp .env.example .env      # set POSTGRES_PASSWORD and JWT_SECRET
docker compose up
```

then start GeoFatali. It finds the backend and goes straight to sign-in.

## Getting a build

Every push builds all three desktop platforms. Open the repository on GitHub →
**Actions** → **Desktop build** → the most recent run → **Artifacts**:

| Artifact | Contents | How to run it |
| --- | --- | --- |
| `geofatali-windows` | `geofatali-windows.zip` | Unzip anywhere, run `geofatali.exe` |
| `geofatali-macos` | `geofatali-macos.zip` | Unzip, drag `GeoFatali.app` to Applications |
| `geofatali-linux` | `geofatali-linux.tar.gz` | `tar -xzf`, run `./geofatali` |

Each has to be built on its own operating system — there is no cross-compiling
a Windows executable from Linux — so the workflow is three jobs on three
runners.

### The builds are not code-signed

This is worth saying plainly rather than letting an operating system warning
say it for you.

* **Windows** will show *"Windows protected your PC"* from SmartScreen. Click
  **More info → Run anyway**. Signing this away needs an Authenticode
  certificate, which costs money annually and is bought against a registered
  company.
* **macOS** will refuse to open it: *"GeoFatali can't be opened because Apple
  cannot check it for malicious software."* Right-click the app → **Open**, or
  run `xattr -dr com.apple.quarantine /Applications/GeoFatali.app`. Signing and
  notarising needs a paid Apple Developer account.
* **Linux** has no equivalent check; make it executable and run it.

Do not tell anyone to turn SmartScreen or Gatekeeper off. The instructions
above are per-application and leave the rest of the protection in place.

## What the desktop does differently

Nothing functional. What changes is the shape of the window:

* content is held to a readable column and centred, rather than stretched
  across a monitor — a form field a foot wide is worse than one that is not;
* the bottom navigation bar becomes a rail down the left side, because the
  bottom of a monitor is the furthest point from both the content and the
  reader's eye;
* floating action buttons become ordinary buttons in the app bar;
* the projects list gains a refresh button, because pull-to-refresh is a touch
  gesture that does not exist with a mouse.

The switch is on window width (760 logical pixels), not on the platform. A
desktop window dragged narrow gets the phone layout, because at that width the
phone layout is the right one.

## Building it yourself

```bash
cd apps/app
flutter config --enable-windows-desktop   # or --enable-linux-desktop, --enable-macos-desktop
flutter pub get
flutter run -d windows                    # or linux, macos
```

Linux needs some development packages first:

```bash
sudo apt-get install -y ninja-build libgtk-3-dev libsecret-1-dev libjsoncpp-dev
```

`libsecret` is the system keyring, which is where the session token goes. If
the keyring is unavailable — a headless machine, or a locked keyring — the app
still works; it just asks you to sign in again next time.

To point a build at a hosted backend rather than letting it search:

```bash
flutter build windows --release --dart-define=GEOFATALI_API_URL=https://api.example.com
```

CI does this from the `GEOFATALI_API_URL` repository variable when one is set.

## Known gaps

* **Icons.** The desktop builds use the stock Flutter icon in the taskbar and
  dock, as the Android build does. The GeoFatali mark is drawn in the app
  itself but has not been exported to `.ico`, `.icns` and the Android mipmaps.
* **No installer.** Windows gets a zip, not an `.msi`; macOS gets a zipped
  `.app`, not a `.dmg`. Both run fine; neither appears in Add/Remove Programs.
* **No auto-update.** A new version means downloading the artifact again.
* **No offline mode.** The desktop app is as dependent on reaching the backend
  as the phone app is.
