import 'package:flutter_test/flutter_test.dart';
import 'package:geofatali/state/app_state.dart';

/// `_normalise` is private, so it is exercised through the public surface that
/// uses it. These cases are the ones people actually type on a site.
void main() {
  group('the server address someone types', () {
    test('a bare private address gets the backend port, not port 80', () {
      // The failure this prevents: typing 192.168.100.16, resolving to port 80,
      // and waiting out a timeout for a server running fine on 8000.
      expect(AppState.normaliseForTest('192.168.100.16'),
          'http://192.168.100.16:8000');
      expect(AppState.normaliseForTest('10.0.0.5'), 'http://10.0.0.5:8000');
      expect(AppState.normaliseForTest('172.16.4.2'), 'http://172.16.4.2:8000');
      expect(AppState.normaliseForTest('localhost'), 'http://localhost:8000');
    });

    test('an explicit port is always respected', () {
      expect(AppState.normaliseForTest('192.168.100.16:9000'),
          'http://192.168.100.16:9000');
      expect(AppState.normaliseForTest('192.168.100.16:80'),
          'http://192.168.100.16:80');
    });

    test('a private address gets http, a public host gets https', () {
      expect(AppState.normaliseForTest('192.168.1.24'), startsWith('http://'));
      expect(AppState.normaliseForTest('geofatali.example.com'),
          startsWith('https://'));
    });

    test('a public host keeps the scheme default rather than 8000', () {
      // Anything hosted properly sits behind 443; forcing 8000 would break it.
      expect(AppState.normaliseForTest('geofatali.example.com'),
          'https://geofatali.example.com');
    });

    test('a full URL is left alone apart from a trailing slash', () {
      expect(AppState.normaliseForTest('https://geo.example.com/'),
          'https://geo.example.com');
      expect(AppState.normaliseForTest('http://192.168.1.24:8000/'),
          'http://192.168.1.24:8000');
    });

    test('whitespace and an empty entry are handled', () {
      expect(AppState.normaliseForTest('  192.168.1.24  '),
          'http://192.168.1.24:8000');
      expect(AppState.normaliseForTest(''), '');
    });

    test('private ranges are matched, near-misses are not', () {
      expect(AppState.isPrivateHost('192.168.0.1'), isTrue);
      expect(AppState.isPrivateHost('172.16.0.1'), isTrue);
      expect(AppState.isPrivateHost('172.31.255.1'), isTrue);
      expect(AppState.isPrivateHost('localhost'), isTrue);
      // 172.32 is outside the private block, and a host merely starting with
      // the digits of one is not private either.
      expect(AppState.isPrivateHost('172.32.0.1'), isFalse);
      expect(AppState.isPrivateHost('192.1680.1'), isFalse);
      expect(AppState.isPrivateHost('geofatali.example.com'), isFalse);
    });
  });
}
