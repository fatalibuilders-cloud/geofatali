import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:geofatali/api/client.dart';
import 'package:geofatali/models/models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

GeoFataliApi _api(
  Future<http.Response> Function(http.Request) handler, {
  String base = 'http://10.0.0.5:8000',
  String? token,
}) =>
    GeoFataliApi(baseUrl: base, httpClient: MockClient(handler), token: token);

void main() {
  group('talking to the server', () {
    test('a trailing slash on the base URL does not double up', () async {
      late Uri seen;
      final api = _api((request) async {
        seen = request.url;
        return http.Response('[]', 200);
      }, base: 'http://10.0.0.5:8000/');
      await api.projects();
      expect(seen.toString(), 'http://10.0.0.5:8000/api/v1/projects');
    });

    test('the token is sent as a bearer credential', () async {
      late Map<String, String> headers;
      final api = _api((request) async {
        headers = request.headers;
        return http.Response('[]', 200);
      }, token: 'a-token');
      await api.projects();
      expect(headers['Authorization'], 'Bearer a-token');
    });

    test('no token means no Authorization header at all', () async {
      late Map<String, String> headers;
      final api = _api((request) async {
        headers = request.headers;
        return http.Response('{"status":"ok","engine_version":"0.1.0"}', 200);
      });
      await api.health();
      expect(headers.containsKey('Authorization'), isFalse);
    });

    test('a refusal comes back as a result, not an exception', () async {
      final api = _api((request) async => http.Response(
            jsonEncode({
              'calculation_type': 'bearing_capacity',
              'method': 'vesic',
              'status': 'INSUFFICIENT_DATA',
              'results': {},
              'warnings': [
                {
                  'severity': 'CRITICAL',
                  'code': 'MISSING_REQUIRED_INPUT',
                  'message': 'friction_angle_deg is required.',
                }
              ],
            }),
            201,
          ));
      final result = await api.bearingCapacity('p1', {});
      expect(result.isRefusal, isTrue);
      expect(result.warnings.single.isCritical, isTrue);
    });

    test('a server message is passed through verbatim', () async {
      const message =
          'A layer from 1.0 m to 3.0 m overlaps one already logged in this borehole.';
      final api = _api((request) async =>
          http.Response(jsonEncode({'detail': message}), 409));
      await expectLater(
        api.addLayer('p', 'b', {}),
        throwsA(isA<ApiException>()
            .having((e) => e.message, 'message', message)
            .having((e) => e.statusCode, 'status', 409)),
      );
    });

    test('a structured error keeps its list of valid values', () async {
      final api = _api((request) async => http.Response(
            jsonEncode({
              'detail': {
                'error': 'UNKNOWN_SECTOR',
                'message': "'mystery' is not a sector the engine models.",
                'known': ['roads', 'dams'],
              }
            }),
            422,
          ));
      await expectLater(
        api.createProject({}),
        throwsA(isA<ApiException>().having(
          (e) => e.message,
          'message',
          allOf(contains('not a sector'), contains('roads, dams')),
        )),
      );
    });

    test('a FastAPI validation error names the field', () async {
      final api = _api((request) async => http.Response(
            jsonEncode({
              'detail': [
                {
                  'loc': ['body', 'password'],
                  'msg': 'String should have at least 12 characters',
                }
              ]
            }),
            422,
          ));
      await expectLater(
        api.register(email: 'a@b.c', password: 'short'),
        throwsA(isA<ApiException>()
            .having((e) => e.message, 'message', contains('password'))),
      );
    });

    test('an unreachable server explains what to check', () async {
      final api = _api((request) async => throw const SocketishFailure());
      await expectLater(
        api.projects(),
        throwsA(isA<ApiException>().having(
          (e) => e.message,
          'message',
          allOf(contains('Could not reach'), contains('Settings')),
        )),
      );
    });

    test('an HTML page is not mistaken for an API', () async {
      final api = _api((request) async =>
          http.Response('<html><body>Hello</body></html>', 200));
      await expectLater(
        api.projects(),
        throwsA(isA<ApiException>()
            .having((e) => e.message, 'message', contains('not JSON'))),
      );
    });

    test('a 401 is marked as an auth failure so the app can sign out', () async {
      final api = _api((request) async => http.Response('{}', 401));
      try {
        await api.projects();
        fail('should have thrown');
      } on ApiException catch (error) {
        expect(error.isAuthFailure, isTrue);
      }
    });

    test('screening pairs each candidate with its stored foundation id', () async {
      final api = _api((request) async => http.Response(
            jsonEncode({
              'id': 'calc-1',
              'calculation_type': 'foundation_screening',
              'method': 'rules_based_screening',
              'status': 'CALCULATED',
              'results': {
                'candidates': [
                  {
                    'foundation_type': 'raft',
                    'label': 'Raft (mat) foundation',
                    'status': 'PRELIMINARY_CANDIDATE',
                    'criteria': [],
                    'construction_steps': [],
                  },
                  {
                    'foundation_type': 'strip',
                    'label': 'Strip footing',
                    'status': 'NOT_RECOMMENDED',
                    'criteria': [],
                    'construction_steps': [],
                  },
                ]
              },
              'warnings': [],
              'foundation_ids': ['f-1', 'f-2'],
            }),
            201,
          ));
      final (result, candidates) = await api.foundationOptions('p', {});
      expect(result.status, 'CALCULATED');
      expect(candidates.map((c) => c.id), ['f-1', 'f-2']);
      expect(candidates.first.foundationType, 'raft');
    });
  });
}

/// Stands in for a connection failure; the client treats any Exception from
/// the transport the same way.
class SocketishFailure implements Exception {
  const SocketishFailure();
  @override
  String toString() => 'Connection refused';
}
