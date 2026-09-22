import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Finding the GeoFatali server without being asked for an address.
///
/// The app derives its own address on the wifi, takes the /24 that address
/// sits in, and asks every host on it whether it is a GeoFatali server. The
/// first one that answers correctly wins and is remembered, so this runs once
/// and subsequent launches go straight to the sign-in form.
///
/// Why a subnet sweep rather than mDNS: it needs nothing of the server. mDNS
/// would be tidier, but it requires the backend to advertise itself and the
/// phone to hold a multicast lock, and plenty of routers drop multicast
/// entirely. A sweep of 254 addresses with a short timeout finishes in a few
/// seconds and works on any network that routes at all.
///
/// The limits, stated plainly: it only covers the /24 the phone is on. A
/// larger network, a server on a different subnet, or one behind a router
/// will not be found, and those cases go through Settings.
class ServerDiscovery {
  ServerDiscovery({
    http.Client? httpClient,
    this.port = defaultPort,
    this.probeTimeout = const Duration(milliseconds: 600),
    this.concurrency = 32,
    Future<List<String>> Function()? localAddresses,
  })  : _http = httpClient ?? http.Client(),
        _localAddresses = localAddresses ?? _realLocalAddresses;

  /// The port the backend documents and the compose file publishes.
  static const int defaultPort = 8000;

  final http.Client _http;
  final int port;
  final Duration probeTimeout;
  final int concurrency;
  final Future<List<String>> Function() _localAddresses;

  /// This device's own IPv4 addresses on real interfaces.
  static Future<List<String>> _realLocalAddresses() async {
    try {
      final interfaces = await NetworkInterface.list(
        type: InternetAddressType.IPv4,
        includeLoopback: false,
        includeLinkLocal: false,
      );
      return [
        for (final interface in interfaces)
          for (final address in interface.addresses) address.address,
      ];
    } on Object {
      // Some platforms refuse to enumerate interfaces. Nothing to scan then.
      return const [];
    }
  }

  /// Every address to try, given the addresses this device holds.
  ///
  /// Only private ranges are swept. Sweeping a public range would mean
  /// spraying requests at addresses that are not the user's to probe.
  static List<String> candidatesFor(List<String> localAddresses) {
    final seen = <String>{};
    final candidates = <String>[];
    // Every address this device holds is excluded, not just the one whose
    // subnet is being swept: a phone with two interfaces on one network would
    // otherwise end up probing itself through the other one.
    final own = localAddresses.toSet();
    for (final local in localAddresses) {
      final parts = local.split('.');
      if (parts.length != 4) continue;
      if (!_isPrivateIPv4(parts)) continue;
      final prefix = '${parts[0]}.${parts[1]}.${parts[2]}';
      for (var host = 1; host <= 254; host++) {
        final address = '$prefix.$host';
        if (own.contains(address)) continue; // the phone is not the server
        if (seen.add(address)) candidates.add(address);
      }
    }
    return candidates;
  }

  static bool _isPrivateIPv4(List<String> parts) {
    final first = int.tryParse(parts[0]);
    final second = int.tryParse(parts[1]);
    if (first == null || second == null) return false;
    if (first == 10) return true;
    if (first == 192 && second == 168) return true;
    if (first == 172 && second >= 16 && second <= 31) return true;
    return false;
  }

  /// Is there a GeoFatali server at this address?
  ///
  /// Something answering on the port is not enough — a printer, a router admin
  /// page or another service would all respond. It has to return the health
  /// document with an engine version in it.
  Future<bool> isGeoFatali(String baseUrl) async {
    try {
      final response = await _http
          .get(Uri.parse('$baseUrl/health'))
          .timeout(probeTimeout);
      if (response.statusCode != 200) return false;
      final body = jsonDecode(response.body);
      return body is Map && body['engine_version'] is String;
    } on Object {
      return false;
    }
  }

  /// Sweep the local network. Returns the first server found, or null.
  ///
  /// [onProgress] reports how many addresses have been tried, so the UI can
  /// show something moving rather than an unexplained pause.
  Future<String?> find({
    void Function(int tried, int total)? onProgress,
    Duration overall = const Duration(seconds: 20),
  }) async {
    final candidates = candidatesFor(await _localAddresses());
    if (candidates.isEmpty) return null;

    final deadline = DateTime.now().add(overall);
    var tried = 0;

    for (var start = 0; start < candidates.length; start += concurrency) {
      if (DateTime.now().isAfter(deadline)) return null;
      final batch = candidates.skip(start).take(concurrency).toList();
      final results = await Future.wait([
        for (final address in batch)
          isGeoFatali('http://$address:$port')
              .then((found) => found ? address : null),
      ]);
      tried += batch.length;
      onProgress?.call(tried, candidates.length);
      for (final address in results) {
        if (address != null) return 'http://$address:$port';
      }
    }
    return null;
  }

  void close() => _http.close();
}
