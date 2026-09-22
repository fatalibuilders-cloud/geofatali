import 'package:flutter/material.dart';

import '../main.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Where this install talks to.
///
/// The address is compiled into the build, so nobody has to think about it.
/// It is editable here because the backend is self-hosted and someone running
/// their own instance must be able to point at it — an advanced setting, not
/// something in front of a first-time user.
class _ServerCard extends StatefulWidget {
  const _ServerCard();

  @override
  State<_ServerCard> createState() => _ServerCardState();
}

class _ServerCardState extends State<_ServerCard> {
  bool _editing = false;
  bool _busy = false;
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      await AppScope.of(context).setBaseUrl(_controller.text);
      if (mounted) {
        setState(() => _editing = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Connected. Sign in to continue.')),
        );
      }
    } on Object catch (error) {
      if (mounted) await showApiError(context, error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SectionHeader(
              title: 'SERVER',
              subtitle: 'Only change this if you run your own GeoFatali backend.',
            ),
            Row(
              children: [
                Expanded(
                  child: Text(state.baseUrl,
                      style: const TextStyle(fontSize: 13)),
                ),
                if (state.hasOverride)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(
                      color: GeoTheme.clay.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text('Custom',
                        style: TextStyle(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w700,
                            color: GeoTheme.clay)),
                  ),
              ],
            ),
            if (_editing) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _controller,
                autofocus: true,
                autocorrect: false,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(
                  hintText: '192.168.1.24:8000',
                  helperText: 'A private address with no port gets 8000.',
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: FilledButton(
                      onPressed: _busy ? null : _save,
                      child: Text(_busy ? 'Checking…' : 'Connect'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: _busy ? null : () => setState(() => _editing = false),
                    child: const Text('Cancel'),
                  ),
                ],
              ),
            ] else ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  OutlinedButton.icon(
                    onPressed: () => setState(() {
                      _controller.text = state.baseUrl;
                      _editing = true;
                    }),
                    icon: const Icon(Icons.dns_outlined, size: 18),
                    label: const Text('Use my own server'),
                  ),
                  if (state.hasOverride) ...[
                    const SizedBox(width: 8),
                    TextButton(
                      onPressed: () => state.clearBaseUrl(),
                      child: const Text('Reset'),
                    ),
                  ],
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final account = state.account;
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionHeader(title: 'ACCOUNT'),
                  Text(account?.email ?? '—',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  Text(
                    account == null
                        ? ''
                        : account.canApprove
                            ? 'Engineer${account.registrationNo == null ? '' : ' · ${account.registrationNo}'} '
                                '— you can sign assessments off'
                            : 'Role: ${account.role} — you cannot approve an assessment',
                    style: const TextStyle(fontSize: 12.5, color: GeoTheme.inkSoft, height: 1.4),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          const _ServerCard(),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionHeader(
                    title: 'WHAT THIS APP IS',
                    subtitle: 'Read this before relying on anything it produces.',
                  ),
                  const Text(
                    'GeoFatali runs published geotechnical calculations on data you '
                    'enter, and tells you what is missing when it cannot. Every result '
                    'records its method, its inputs, the design standard and the engine '
                    'version, so it can be checked and reproduced.\n\n'
                    'It is not a site investigation. It is not a foundation design. It '
                    'does not certify any structure as safe. A photograph cannot '
                    'establish bearing capacity and this app never claims otherwise — '
                    'visual classification is labelled as such, and a value that was '
                    'correlated rather than measured says so wherever it appears.\n\n'
                    'Final geotechnical and structural design must be carried out and '
                    'sealed by an engineer registered in the jurisdiction where you are '
                    'building.',
                    style: TextStyle(fontSize: 12.5, color: GeoTheme.inkSoft, height: 1.5),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: () async {
              await state.signOut();
              if (context.mounted) Navigator.of(context).pop();
            },
            style: OutlinedButton.styleFrom(
              foregroundColor: GeoTheme.critical,
              side: const BorderSide(color: GeoTheme.critical),
              minimumSize: const Size.fromHeight(46),
            ),
            icon: const Icon(Icons.logout, size: 18),
            label: const Text('Sign out'),
          ),
          const SizedBox(height: 24),
          const Center(
            child: Text('GeoFatali · a Fatalibuilders product',
                style: TextStyle(fontSize: 11, color: GeoTheme.inkSoft)),
          ),
        ],
      ),
    );
  }
}
