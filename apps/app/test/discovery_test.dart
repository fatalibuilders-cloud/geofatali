import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:geofatali/api/discovery.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

http.Response _geofatali() => http.Response(
      jsonEncode({'status': 'ok', 'engine_version': '0.1.0'}),
      200,
    );

void main() {
  group('deciding what to probe', () {
    test('sweeps the /24 the phone is on', () {
      final candidates = ServerDiscovery.candidatesFor(['192.168.100.23']);
      expect(candidates, contains('192.168.100.16'));
      expect(candidates, contains('192.168.100.1'));
      expect(candidates, contains('192.168.100.254'));
      expect(candidates.length, 253); // 254 hosts, minus the phone itself
    });

    test('never probes the phone itself', () {
      final candidates = ServerDiscovery.candidatesFor(['192.168.100.23']);
      expect(candidates, isNot(contains('192.168.100.23')));
    });

    test('covers every private range', () {
      expect(ServerDiscovery.candidatesFor(['10.1.2.3']), contains('10.1.2.50'));
      expect(ServerDiscovery.candidatesFor(['172.16.5.9']), contains('172.16.5.50'));
      expect(ServerDiscovery.candidatesFor(['172.31.0.9']), contains('172.31.0.50'));
    });

    test('refuses to sweep anything public', () {
      // Spraying requests at addresses that are not the user's to probe would
      // be both rude and useless.
      expect(ServerDiscovery.candidatesFor(['8.8.8.8']), isEmpty);
      expect(ServerDiscovery.candidatesFor(['172.32.0.1']), isEmpty);
      expect(ServerDiscovery.candidatesFor(['203.0.113.5']), isEmpty);
    });

    test('handles several interfaces without duplicating work', () {
      final candidates =
          ServerDiscovery.candidatesFor(['192.168.1.5', '192.168.1.6']);
      expect(candidates.toSet().length, candidates.length);
      // Each address is excluded from its own sweep, so both are absent.
      expect(candidates, isNot(contains('192.168.1.5')));
      expect(candidates, isNot(contains('192.168.1.6')));
    });

    test('ignores malformed and absent addresses', () {
      expect(ServerDiscovery.candidatesFor([]), isEmpty);
      expect(ServerDiscovery.candidatesFor(['not-an-address']), isEmpty);
      expect(ServerDiscovery.candidatesFor(['192.168.1']), isEmpty);
    });
  });

  group('recognising a server', () {
    test('accepts a GeoFatali health document', () async {
      final discovery = ServerDiscovery(
        httpClient: MockClient((_) async => _geofatali()),
      );
      expect(await discovery.isGeoFatali('http://192.168.1.9:8000'), isTrue);
    });

    test('rejects something else answering on the port', () async {
      // A router admin page, a printer, another service — all answer 200.
      final discovery = ServerDiscovery(
        httpClient: MockClient(
            (_) async => http.Response('<html>Router setup</html>', 200)),
      );
      expect(await discovery.isGeoFatali('http://192.168.1.1:8000'), isFalse);
    });

    test('rejects JSON without an engine version', () async {
      final discovery = ServerDiscovery(
        httpClient:
            MockClient((_) async => http.Response('{"status":"ok"}', 200)),
      );
      expect(await discovery.isGeoFatali('http://192.168.1.9:8000'), isFalse);
    });

    test('a refusal or an error is simply not a server', () async {
      final refused = ServerDiscovery(
        httpClient: MockClient((_) async => throw const _Refused()),
      );
      final error = ServerDiscovery(
        httpClient: MockClient((_) async => http.Response('nope', 500)),
      );
      expect(await refused.isGeoFatali('http://192.168.1.9:8000'), isFalse);
      expect(await error.isGeoFatali('http://192.168.1.9:8000'), isFalse);
    });
  });

  group('sweeping', () {
    test('finds the one server among a network of other things', () async {
      final discovery = ServerDiscovery(
        localAddresses: () async => ['192.168.100.23'],
        httpClient: MockClient((request) async {
          if (request.url.host == '192.168.100.16') return _geofatali();
          if (request.url.host == '192.168.100.1') {
            return http.Response('<html>Router</html>', 200);
          }
          throw const _Refused();
        }),
      );
      expect(await discovery.find(), 'http://192.168.100.16:8000');
    });

    test('returns null when nothing on the network is a server', () async {
      final discovery = ServerDiscovery(
        localAddresses: () async => ['192.168.100.23'],
        httpClient: MockClient((_) async => throw const _Refused()),
      );
      expect(await discovery.find(), isNull);
    });

    test('returns null when the device has no private address', () async {
      final discovery = ServerDiscovery(
        localAddresses: () async => [],
        httpClient: MockClient((_) async => _geofatali()),
      );
      expect(await discovery.find(), isNull);
    });

    test('reports progress so the screen can show something moving', () async {
      final progress = <int>[];
      final discovery = ServerDiscovery(
        localAddresses: () async => ['192.168.100.23'],
        httpClient: MockClient((_) async => throw const _Refused()),
        concurrency: 64,
      );
      await discovery.find(onProgress: (tried, total) => progress.add(tried));
      expect(progress, isNotEmpty);
      expect(progress.last, 253);
    });

    test('uses the documented backend port', () async {
      late Uri seen;
      final discovery = ServerDiscovery(
        localAddresses: () async => ['192.168.100.23'],
        httpClient: MockClient((request) async {
          seen = request.url;
          return _geofatali();
        }),
      );
      await discovery.find();
      expect(seen.port, ServerDiscovery.defaultPort);
      expect(seen.path, '/health');
    });
  });
}

/// Stands in for a refused connection.
class _Refused implements Exception {
  const _Refused();
  @override
  String toString() => 'Connection refused';
}
