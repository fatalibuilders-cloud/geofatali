import 'package:flutter_test/flutter_test.dart';
import 'package:geofatali/api/discovery.dart';
import 'package:geofatali/state/app_state.dart';

/// `_normalise` is private, so it is exercised through the public surface that
/// uses it. These cases are the ones people actually type on a site.
void main() {
  group('the address this build talks to', () {
    test('there is a compiled-in default, so nobody is asked for an IP', () {
      expect(AppState.bakedInApiUrl, isNotEmpty);
      expect(AppState.bakedInApiUrl, startsWith('http'));
    });

    test('with no override, the app uses the compiled-in address', () {
      expect(AppState().baseUrl, AppState.bakedInApiUrl);
      expect(AppState().hasOverride, isFalse);
    });
  });

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

  group('where the app looks, and in what order', () {
    test('a remembered address is tried before anything else', () {
      final candidates =
          AppState.directCandidates(stored: 'http://10.0.0.9:8000', desktop: false);
      expect(candidates.first, 'http://10.0.0.9:8000');
    });

    test('a phone never wastes a probe on itself', () {
      // Loopback on a phone is the phone. The backend is never there.
      final candidates = AppState.directCandidates(stored: null, desktop: false);
      expect(candidates, [AppState.bakedInApiUrl]);
    });

    test('a desktop checks its own machine, because that is where it usually is',
        () {
      // The laptop running `docker compose up` in a terminal is the case the
      // desktop app has to get right with no configuration at all.
      final candidates = AppState.directCandidates(stored: null, desktop: true);
      expect(candidates, containsAll(ServerDiscovery.sameMachine));
    });

    test('a hosted deployment still wins over something running locally', () {
      // Otherwise a developer with a stray backend on 8000 would be silently
      // signed in to the wrong instance.
      final candidates = AppState.directCandidates(stored: null, desktop: true);
      expect(candidates.indexOf(AppState.bakedInApiUrl),
          lessThan(candidates.indexOf(ServerDiscovery.sameMachine.first)));
    });

    test('the same-machine addresses use the documented backend port', () {
      for (final address in ServerDiscovery.sameMachine) {
        expect(Uri.parse(address).port, ServerDiscovery.defaultPort);
      }
    });

    test('a sweep cannot find a server on the machine doing the sweeping', () {
      // This is why the loopback entries exist: the sweep deliberately skips
      // every address the machine holds, which on a desktop is where the
      // server is. If this ever stops being true, the entries are redundant.
      expect(ServerDiscovery.candidatesFor(['192.168.1.20']),
          isNot(contains('192.168.1.20')));
    });
  });
}
