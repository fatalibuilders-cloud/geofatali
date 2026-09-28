import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/models.dart';

/// The one place the app talks to the server.
///
/// The base URL is configured by the user rather than compiled in, because
/// GeoFatali's backend is self-hosted: a contractor running their own instance
/// and someone testing against a laptop on the site wifi are both normal.
///
/// Two rules:
///
/// * A refusal is not an error. When the engine answers `INSUFFICIENT_DATA`
///   the server returns 200 with that status, and this client passes it
///   through untouched so the UI can show what is missing. Turning it into an
///   exception would lose the reason.
/// * Server messages are shown to the user verbatim. They are written to be
///   read by a site technician — "a layer from 1.0 m to 3.0 m overlaps one
///   already logged" — and paraphrasing them here would throw that away.
class GeoFataliApi {
  GeoFataliApi({
    required this.baseUrl,
    http.Client? httpClient,
    this.token,
    Duration? timeout,
  })  : _http = httpClient ?? http.Client(),
        _timeout = timeout ?? const Duration(seconds: 30);

  final String baseUrl;
  final http.Client _http;
  final Duration _timeout;
  String? token;

  Uri _uri(String path, [Map<String, String>? query]) {
    final normalised = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    return Uri.parse('$normalised$path').replace(queryParameters: query);
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<dynamic> _send(
    String method,
    String path, {
    Object? body,
    Map<String, String>? query,
  }) async {
    final uri = _uri(path, query);
    late http.Response response;
    try {
      response = await switch (method) {
        'GET' => _http.get(uri, headers: _headers),
        'POST' => _http.post(uri, headers: _headers, body: jsonEncode(body ?? {})),
        'PATCH' => _http.patch(uri, headers: _headers, body: jsonEncode(body ?? {})),
        'DELETE' => _http.delete(uri, headers: _headers),
        _ => throw ArgumentError('Unsupported method $method'),
      }
          .timeout(_timeout);
    } on Exception catch (error) {
      final port = uri.hasPort ? '${uri.port}' : (uri.scheme == 'https' ? '443' : '80');
      throw ApiException(
        'Could not reach the server at $baseUrl (port $port).\n\n'
        'Check that:\n'
        '  • the port is right — the backend runs on 8000 by default\n'
        '  • the server was started with --host 0.0.0.0, not just localhost\n'
        '  • this phone is on the same network, not mobile data\n'
        '  • the machine\'s firewall allows the port\n\n$error',
      );
    }

    if (response.statusCode == 204) return null;

    dynamic decoded;
    if (response.body.isNotEmpty) {
      try {
        decoded = jsonDecode(response.body);
      } on FormatException {
        throw ApiException(
          'The server replied with something that is not JSON '
          '(HTTP ${response.statusCode}). Is that address really a GeoFatali API?',
          statusCode: response.statusCode,
        );
      }
    }

    if (response.statusCode >= 400) {
      throw ApiException(
        _messageFrom(decoded, response.statusCode),
        statusCode: response.statusCode,
        detail: decoded,
      );
    }
    return decoded;
  }

  /// Pull something readable out of whatever shape the error took.
  String _messageFrom(dynamic decoded, int status) {
    if (decoded is Map) {
      final detail = decoded['detail'] ?? decoded['message'] ?? decoded['error'];
      if (detail is String) return detail;
      if (detail is Map) {
        final message = detail['message'];
        if (message is String) {
          final known = detail['known'];
          if (known is List && known.isNotEmpty) {
            return '$message\n\nValid values: ${known.join(', ')}';
          }
          return message;
        }
      }
      if (detail is List && detail.isNotEmpty) {
        // FastAPI validation errors.
        final first = detail.first;
        if (first is Map) {
          final loc = (first['loc'] as List?)?.where((p) => p != 'body').join('.') ?? '';
          final msg = first['msg'] ?? 'is not valid';
          return loc.isEmpty ? '$msg' : '$loc: $msg';
        }
      }
    }
    return switch (status) {
      401 => 'Your session has expired. Sign in again.',
      403 => 'You do not have permission to do that.',
      404 => 'Not found.',
      >= 500 => 'The server hit an error (HTTP $status). Try again shortly.',
      _ => 'Request failed (HTTP $status).',
    };
  }

  // ── health and reference data ──────────────────────────────────────────

  Future<Map<String, dynamic>> health() async =>
      (await _send('GET', '/health')) as Map<String, dynamic>;

  Future<List<Sector>> sectors() async {
    final body = await _send('GET', '/api/v1/reference/sectors') as Map<String, dynamic>;
    return [
      for (final s in body['sectors'] as List) Sector.fromJson(s as Map<String, dynamic>),
    ];
  }

  Future<List<Map<String, dynamic>>> standards() async {
    final body = await _send('GET', '/api/v1/reference/standards') as Map<String, dynamic>;
    return [
      for (final s in body['standards'] as List) s as Map<String, dynamic>,
    ];
  }

  // ── auth ───────────────────────────────────────────────────────────────

  Future<Session> register({
    required String email,
    required String password,
    String? name,
  }) async {
    final body = await _send('POST', '/api/v1/auth/register', body: {
      'email': email,
      'password': password,
      if (name != null && name.isNotEmpty) 'name': name,
    });
    return Session.fromJson(body as Map<String, dynamic>);
  }

  Future<Session> login({required String email, required String password}) async {
    final body = await _send('POST', '/api/v1/auth/login', body: {
      'email': email,
      'password': password,
    });
    return Session.fromJson(body as Map<String, dynamic>);
  }

  Future<Account> me() async =>
      Account.fromJson(await _send('GET', '/api/v1/auth/me') as Map<String, dynamic>);

  // ── projects ───────────────────────────────────────────────────────────

  Future<List<Project>> projects() async {
    final body = await _send('GET', '/api/v1/projects') as List;
    return [for (final p in body) Project.fromJson(p as Map<String, dynamic>)];
  }

  Future<Project> createProject(Map<String, dynamic> fields) async =>
      Project.fromJson(await _send('POST', '/api/v1/projects', body: fields)
          as Map<String, dynamic>);

  Future<Project> project(String id) async =>
      Project.fromJson(await _send('GET', '/api/v1/projects/$id') as Map<String, dynamic>);

  Future<void> deleteProject(String id) => _send('DELETE', '/api/v1/projects/$id');

  // ── the ground record ──────────────────────────────────────────────────

  Future<List<Borehole>> boreholes(String projectId) async {
    final body = await _send('GET', '/api/v1/projects/$projectId/boreholes') as List;
    return [for (final b in body) Borehole.fromJson(b as Map<String, dynamic>)];
  }

  Future<Borehole> createBorehole(String projectId, Map<String, dynamic> fields) async =>
      Borehole.fromJson(
          await _send('POST', '/api/v1/projects/$projectId/boreholes', body: fields)
              as Map<String, dynamic>);

  Future<List<SoilLayer>> layers(String projectId, String boreholeId) async {
    final body = await _send(
        'GET', '/api/v1/projects/$projectId/boreholes/$boreholeId/layers') as List;
    return [for (final l in body) SoilLayer.fromJson(l as Map<String, dynamic>)];
  }

  Future<SoilLayer> addLayer(
    String projectId,
    String boreholeId,
    Map<String, dynamic> fields,
  ) async =>
      SoilLayer.fromJson(await _send(
        'POST',
        '/api/v1/projects/$projectId/boreholes/$boreholeId/layers',
        body: fields,
      ) as Map<String, dynamic>);

  Future<Map<String, dynamic>> addSpt(
    String projectId,
    String boreholeId,
    Map<String, dynamic> fields,
  ) async =>
      await _send(
        'POST',
        '/api/v1/projects/$projectId/boreholes/$boreholeId/spt',
        body: fields,
      ) as Map<String, dynamic>;

  // ── calculations ───────────────────────────────────────────────────────

  Future<CalculationResult> bearingCapacity(
    String projectId,
    Map<String, dynamic> request,
  ) async =>
      CalculationResult.fromJson(await _send(
        'POST',
        '/api/v1/projects/$projectId/calculations/bearing-capacity',
        body: request,
      ) as Map<String, dynamic>);

  Future<CalculationResult> sizeFooting(
    String projectId,
    Map<String, dynamic> request,
  ) async =>
      CalculationResult.fromJson(await _send(
        'POST',
        '/api/v1/projects/$projectId/calculations/footing',
        body: request,
      ) as Map<String, dynamic>);

  /// Screen the foundation options. Returns the candidates, each with the
  /// construction sequence for this site.
  Future<(CalculationResult, List<FoundationCandidate>)> foundationOptions(
    String projectId,
    Map<String, dynamic> request,
  ) async {
    final body = await _send(
      'POST',
      '/api/v1/projects/$projectId/calculations/foundation-options',
      body: request,
    ) as Map<String, dynamic>;
    final result = CalculationResult.fromJson(body);
    final ids = [for (final i in (body['foundation_ids'] as List? ?? [])) i as String];
    final raw = (body['results']?['candidates'] as List? ?? []);
    final candidates = <FoundationCandidate>[];
    for (var i = 0; i < raw.length; i++) {
      final parsed = FoundationCandidate.fromJson(raw[i] as Map<String, dynamic>);
      candidates.add(FoundationCandidate(
        foundationType: parsed.foundationType,
        label: parsed.label,
        status: parsed.status,
        criteria: parsed.criteria,
        rationale: parsed.rationale,
        conditions: parsed.conditions,
        missingData: parsed.missingData,
        relativeCost: parsed.relativeCost,
        steps: parsed.steps,
        id: i < ids.length ? ids[i] : null,
      ));
    }
    return (result, candidates);
  }

  Future<List<CalculationResult>> calculations(String projectId) async {
    final body = await _send('GET', '/api/v1/projects/$projectId/calculations') as List;
    return [
      for (final c in body) CalculationResult.fromJson(c as Map<String, dynamic>),
    ];
  }

  Future<Map<String, dynamic>> selectFoundation(
          String projectId, String foundationId) async =>
      await _send('POST', '/api/v1/projects/$projectId/foundations/$foundationId/select')
          as Map<String, dynamic>;

  // ── reports ────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> generateReport(String projectId) async =>
      await _send('POST', '/api/v1/projects/$projectId/reports')
          as Map<String, dynamic>;

  Future<List<Map<String, dynamic>>> reports(String projectId) async {
    final body = await _send('GET', '/api/v1/projects/$projectId/reports') as List;
    return [for (final r in body) r as Map<String, dynamic>];
  }

  void close() => _http.close();
}
