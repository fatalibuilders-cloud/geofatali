import 'package:flutter/material.dart';

import '../main.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Point the app at a server.
///
/// GeoFatali's backend is self-hosted, so this is the first screen and not a
/// setting buried three levels down. A contractor running their own instance
/// and an engineer testing against a laptop on the site wifi both start here.
class ServerSetupScreen extends StatefulWidget {
  const ServerSetupScreen({super.key});

  @override
  State<ServerSetupScreen> createState() => _ServerSetupScreenState();
}

class _ServerSetupScreenState extends State<ServerSetupScreen> {
  final _controller = TextEditingController();
  bool _busy = false;
  String? _status;

  @override
  void didChangeDependencies() {
    // Not initState: an inherited widget cannot be read before initState has
    // finished. This is the correct place, and it also picks up a later change.
    super.didChangeDependencies();
    if (_controller.text.isEmpty) {
      _controller.text = AppScope.of(context).baseUrl ?? '';
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    setState(() {
      _busy = true;
      _status = null;
    });
    try {
      await AppScope.of(context).setBaseUrl(_controller.text);
      if (mounted) setState(() => _status = 'Connected.');
    } on Object catch (error) {
      if (mounted) await showApiError(context, error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 48, 20, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.layers_outlined, size: 40, color: GeoTheme.navy),
              const SizedBox(height: 14),
              const Text('GeoFatali',
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              const Text(
                'Geotechnical and foundation engineering, from the ground up.',
                style: TextStyle(fontSize: 14, color: GeoTheme.inkSoft, height: 1.4),
              ),
              const SizedBox(height: 32),
              const SectionHeader(
                title: 'WHERE IS YOUR SERVER?',
                subtitle:
                    'GeoFatali stores your projects on a server you control. Enter the '
                    'address of your instance — a laptop on the same wifi, or a hosted one.',
              ),
              TextField(
                controller: _controller,
                autocorrect: false,
                keyboardType: TextInputType.url,
                textInputAction: TextInputAction.go,
                onSubmitted: (_) => _connect(),
                decoration: const InputDecoration(
                  hintText: '192.168.1.24:8000',
                  prefixIcon: Icon(Icons.dns_outlined, size: 20),
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'A private address gets http, anything public gets https. '
                'You can change this later in Settings.',
                style: TextStyle(fontSize: 12, color: GeoTheme.inkSoft, height: 1.35),
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: _busy ? null : _connect,
                child: _busy
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Connect'),
              ),
              if (_status != null) ...[
                const SizedBox(height: 12),
                Text(_status!,
                    style: const TextStyle(color: GeoTheme.pass, fontSize: 13)),
              ],
              const SizedBox(height: 40),
              const _Disclaimer(),
            ],
          ),
        ),
      ),
    );
  }
}

class _Disclaimer extends StatelessWidget {
  const _Disclaimer();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: GeoTheme.line),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('What this app is',
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
          SizedBox(height: 8),
          Text(
            'A preliminary geotechnical screening tool. It runs published '
            'engineering calculations on data you enter, and it shows you what '
            'is missing when it cannot.\n\n'
            'It is not a site investigation, it is not a foundation design, and '
            'it does not certify anything as safe. A photograph cannot establish '
            'bearing capacity, and this app never claims it can. Final design '
            'must be carried out and sealed by an engineer registered where you '
            'are building.',
            style: TextStyle(fontSize: 12, color: GeoTheme.inkSoft, height: 1.45),
          ),
        ],
      ),
    );
  }
}
