import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/client.dart';
import '../models/models.dart';

/// Application state: who is signed in.
///
/// The server address is baked in at build time rather than asked for on
/// first launch. Opening an app and being asked for an IP address is not a
/// reasonable thing to put in front of someone; they sign in with an email
/// address and the app knows where its own backend is.
///
/// It is still overridable, in Settings, because the backend is self-hosted
/// and someone running their own instance has to be able to point at it. That
/// is an advanced setting, not the front door.
///
/// The bearer token lives in the platform keystore rather than in shared
/// preferences, because anyone holding it is the user.
class AppState extends ChangeNotifier {
  AppState({FlutterSecureStorage? secureStorage})
      : _secure = secureStorage ?? const FlutterSecureStorage();

  static const _baseUrlKey = 'api_base_url';
  static const _tokenKey = 'auth_token';

  /// Where this build talks to, unless someone has overridden it.
  ///
  /// Set at build time:
  ///   flutter build apk --dart-define=GEOFATALI_API_URL=https://api.example.com
  ///
  /// The default is the Android emulator's alias for the host machine, which
  /// makes `flutter run` work against a local backend with no configuration.
  /// A shipped build must define this, or it points at nothing useful — the
  /// CI workflow passes it from a repository variable.
  static const String bakedInApiUrl = String.fromEnvironment(
    'GEOFATALI_API_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  final FlutterSecureStorage _secure;

  String? _baseUrl;
  String? _token;
  Account? _account;
  bool _ready = false;
  String? _lastError;

  /// The address in use: an override if one was set, otherwise this build's.
  String get baseUrl => _baseUrl?.isNotEmpty == true ? _baseUrl! : bakedInApiUrl;

  /// True when someone has pointed this install at their own server.
  bool get hasOverride => _baseUrl?.isNotEmpty == true;

  Account? get account => _account;
  bool get ready => _ready;
  bool get isSignedIn => _token != null && _account != null;
  String? get lastError => _lastError;

  GeoFataliApi get api => GeoFataliApi(baseUrl: baseUrl, token: _token);

  /// Load what was stored last time and try to restore the session.
  Future<void> restore() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString(_baseUrlKey);
    try {
      _token = await _secure.read(key: _tokenKey);
    } on Exception {
      // A keystore that cannot be read is not fatal — it means signing in again.
      _token = null;
    }
    if (_token != null) {
      try {
        _account = await api.me();
      } on ApiException {
        // Expired or revoked. Clear it rather than leaving a token that will
        // fail on every subsequent screen.
        await signOut(notify: false);
      }
    }
    _ready = true;
    notifyListeners();
  }

  /// Point this install at a different server. Verifies it before storing.
  Future<void> setBaseUrl(String value) async {
    final cleaned = _normalise(value);
    // A short timeout here: this is someone checking an address they just
    // typed, and thirty seconds of spinner is a poor way to learn it is wrong.
    final probe = GeoFataliApi(
      baseUrl: cleaned,
      timeout: const Duration(seconds: 8),
    );
    final health = await probe.health();
    if (health['engine_version'] == null) {
      throw ApiException(
        'That address answered, but it does not look like a GeoFatali server — '
        'its /health response has no engine version.',
      );
    }
    probe.close();
    _baseUrl = cleaned;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_baseUrlKey, cleaned);
    notifyListeners();
  }

  /// Accept what people actually type: a bare host, a host:port, or a full URL.
  ///
  /// The port is the trap. Someone types `192.168.1.24`, the URL resolves to
  /// port 80, nothing is listening there, and the app waits out a timeout for
  /// a server that is running perfectly well on 8000. So a private address
  /// with no port gets 8000 — the port the backend documents and uvicorn
  /// defaults to. A public host keeps the scheme default, because anything
  /// hosted properly sits behind 443.
  static const int defaultDevPort = 8000;

  static final RegExp _privateHost = RegExp(
    r'^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.|localhost$)',
  );

  static bool isPrivateHost(String host) => _privateHost.hasMatch(host);

  static String _normalise(String value) {
    var v = value.trim();
    if (v.isEmpty) return v;

    if (!v.startsWith('http://') && !v.startsWith('https://')) {
      // Plain http for a private address, https for anything public: a phone
      // on site wifi talking to a laptop has no certificate.
      final hostPart = v.split('/').first.split(':').first;
      v = '${isPrivateHost(hostPart) ? 'http' : 'https'}://$v';
    }

    while (v.endsWith('/')) {
      v = v.substring(0, v.length - 1);
    }

    final parsed = Uri.tryParse(v);
    if (parsed == null || parsed.host.isEmpty) return v;

    // Uri.hasPort is false for a port that matches the scheme default, so
    // someone who deliberately typed :80 would have it silently replaced.
    // Read the port off the text they actually entered instead.
    final authority = v.replaceFirst(RegExp(r'^https?://'), '').split('/').first;
    final hasExplicitPort = RegExp(r':\d+$').hasMatch(authority);

    if (!hasExplicitPort && isPrivateHost(parsed.host)) {
      return parsed.replace(port: defaultDevPort).toString();
    }
    return v;
  }

  /// Exposed for tests: address handling is the thing people get wrong, so it
  /// is worth testing directly rather than only through a live probe.
  @visibleForTesting
  static String normaliseForTest(String value) => _normalise(value);

  Future<void> signIn({required String email, required String password}) async {
    final session = await api.login(email: email, password: password);
    await _storeSession(session);
  }

  Future<void> signUp({
    required String email,
    required String password,
    String? name,
  }) async {
    final session = await api.register(email: email, password: password, name: name);
    await _storeSession(session);
  }

  Future<void> _storeSession(Session session) async {
    _token = session.token;
    try {
      await _secure.write(key: _tokenKey, value: session.token);
    } on Exception {
      // Keep working this session even if the keystore refuses to persist.
      _lastError = 'Signed in, but this device would not store the session, '
          'so you will need to sign in again next time.';
    }
    _account = await api.me();
    notifyListeners();
  }

  /// Drop the override and go back to the address this build was made with.
  Future<void> clearBaseUrl() async {
    await signOut(notify: false);
    _baseUrl = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_baseUrlKey);
    notifyListeners();
  }

  Future<void> signOut({bool notify = true}) async {
    _token = null;
    _account = null;
    try {
      await _secure.delete(key: _tokenKey);
    } on Exception {
      // Nothing to do; the in-memory token is already gone.
    }
    if (notify) notifyListeners();
  }

  void clearError() {
    _lastError = null;
    notifyListeners();
  }
}
