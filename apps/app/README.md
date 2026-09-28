# GeoFatali — the client

One Flutter codebase, four platforms: **Android, Windows, macOS and Linux**.
The directory is `app`, not `mobile`, because a desktop build comes out of it.

It is a client and nothing else. No site data is stored here — projects,
boreholes, soil layers, calculations and reports all live behind the API, which
is what lets a phone on site and a laptop in the office show the same work
under the same email with nothing to pair or sync.

```bash
flutter pub get
flutter test                  # 73 tests
flutter analyze --fatal-infos

flutter run                   # a connected Android device
flutter run -d windows        # or linux, macos
```

## Layout

| Path | What is in it |
| --- | --- |
| `lib/api/client.dart` | Every HTTP call the app makes |
| `lib/api/discovery.dart` | Finding the backend without being told an address |
| `lib/state/app_state.dart` | Session, the address in use, and how it was found |
| `lib/models/` | What the server sends, parsed |
| `lib/screens/` | One file per screen |
| `lib/widgets/layout.dart` | The phone/desktop breakpoint and the shapes it picks |
| `lib/widgets/common.dart` | The provenance chip, the warning list, the preliminary banner |
| `lib/theme.dart` | The palette, and tabular figures so columns of depths line up |

## Pointing it at a server

Builds normally find the backend themselves. To fix one to a particular
address:

```bash
flutter build apk --release --dart-define=GEOFATALI_API_URL=https://api.example.com
```

## Further reading

* [../../docs/product/ANDROID.md](../../docs/product/ANDROID.md) — the APK and Google Play
* [../../docs/product/DESKTOP.md](../../docs/product/DESKTOP.md) — Windows, macOS and Linux
