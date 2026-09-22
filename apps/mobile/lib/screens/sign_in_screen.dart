import 'package:flutter/material.dart';

import '../main.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/common.dart';
import 'settings_screen.dart';

/// The front door: sign in, or create an account.
///
/// Nothing is asked for here except an email address and a password. The
/// server this build talks to is compiled in — putting an IP address in front
/// of someone opening an app for the first time is not a reasonable thing to
/// do, and anyone self-hosting can point the app elsewhere from Settings.
class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key});

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _name = TextEditingController();
  bool _registering = false;
  bool _busy = false;
  bool _obscure = true;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _name.dispose();
    super.dispose();
  }

  bool get _canSubmit =>
      _email.text.trim().contains('@') &&
      _password.text.length >= 8 &&
      AppScope.of(context).connection == ServerConnection.connected;

  Future<void> _submit() async {
    if (!_canSubmit) return;
    setState(() => _busy = true);
    try {
      final state = AppScope.of(context);
      if (_registering) {
        await state.signUp(
          email: _email.text.trim(),
          password: _password.text,
          name: _name.text.trim().isEmpty ? null : _name.text.trim(),
        );
      } else {
        await state.signIn(email: _email.text.trim(), password: _password.text);
      }
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
          padding: const EdgeInsets.fromLTRB(24, 56, 24, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.layers_outlined, size: 42, color: GeoTheme.navy),
              const SizedBox(height: 16),
              const Text('GeoFatali',
                  style: TextStyle(fontSize: 30, fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              const Text(
                'Geotechnical and foundation engineering, from the ground up.',
                style: TextStyle(fontSize: 14, color: GeoTheme.inkSoft, height: 1.4),
              ),
              const SizedBox(height: 28),
              const _ConnectionStatus(),
              const SizedBox(height: 24),

              Text(
                _registering ? 'Create your account' : 'Sign in',
                style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 16),

              if (_registering) ...[
                TextField(
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(
                    labelText: 'Your name',
                    prefixIcon: Icon(Icons.person_outline, size: 20),
                  ),
                ),
                const SizedBox(height: 12),
              ],

              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                autocorrect: false,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  labelText: 'Email',
                  hintText: 'you@example.com',
                  prefixIcon: Icon(Icons.mail_outline, size: 20),
                ),
              ),
              const SizedBox(height: 12),

              TextField(
                controller: _password,
                obscureText: _obscure,
                autofillHints: const [AutofillHints.password],
                textInputAction: TextInputAction.go,
                onChanged: (_) => setState(() {}),
                onSubmitted: (_) => _submit(),
                decoration: InputDecoration(
                  labelText: 'Password',
                  prefixIcon: const Icon(Icons.lock_outline, size: 20),
                  suffixIcon: IconButton(
                    tooltip: _obscure ? 'Show password' : 'Hide password',
                    icon: Icon(
                      _obscure
                          ? Icons.visibility_off_outlined
                          : Icons.visibility_outlined,
                      size: 20,
                    ),
                    onPressed: () => setState(() => _obscure = !_obscure),
                  ),
                ),
              ),

              if (_registering) ...[
                const SizedBox(height: 8),
                const Text(
                  'At least 12 characters. A long passphrase is easier to remember '
                  'and harder to guess than a short password with symbols in it.',
                  style: TextStyle(fontSize: 12, color: GeoTheme.inkSoft, height: 1.35),
                ),
              ],

              const SizedBox(height: 22),
              FilledButton(
                onPressed: (_busy || !_canSubmit) ? null : _submit,
                child: _busy
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : Text(_registering ? 'Create account' : 'Sign in'),
              ),
              const SizedBox(height: 6),
              Center(
                child: TextButton(
                  onPressed: _busy
                      ? null
                      : () => setState(() => _registering = !_registering),
                  child: Text(_registering
                      ? 'I already have an account'
                      : 'Create an account'),
                ),
              ),

              if (_registering) ...[
                const SizedBox(height: 10),
                const Text(
                  'An engineer account — the only kind that can sign an assessment '
                  'off — is granted by an administrator against a verified board '
                  'registration. It cannot be claimed here.',
                  style: TextStyle(fontSize: 11.5, color: GeoTheme.inkSoft, height: 1.4),
                ),
              ],

              const SizedBox(height: 36),
              const _WhatThisIs(),
            ],
          ),
        ),
      ),
    );
  }
}

/// What the app is doing about finding a server.
///
/// Discovery happens without being asked, but not invisibly: a sweep takes a
/// few seconds, and an unexplained pause on a sign-in screen reads as a broken
/// app. When nothing is found this is also where the way out lives.
class _ConnectionStatus extends StatelessWidget {
  const _ConnectionStatus();

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    return AnimatedBuilder(
      animation: state,
      builder: (context, _) {
        final (icon, colour, label, detail) = switch (state.connection) {
          ServerConnection.checking => (
              Icons.sync,
              GeoTheme.inkSoft,
              'Connecting…',
              null,
            ),
          ServerConnection.searching => (
              Icons.wifi_find_outlined,
              GeoTheme.info,
              'Looking for your server on this network…',
              state.scanTotal > 0
                  ? '${state.scanned} of ${state.scanTotal} addresses'
                  : null,
            ),
          ServerConnection.connected => (
              Icons.check_circle_outline,
              GeoTheme.pass,
              'Connected',
              Uri.tryParse(state.baseUrl)?.host,
            ),
          ServerConnection.notFound => (
              Icons.error_outline,
              GeoTheme.warning,
              'No server found on this network',
              'Start the backend, then search again.',
            ),
        };

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: colour.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: colour.withValues(alpha: 0.25)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 17, color: colour),
              const SizedBox(width: 9),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label,
                        style: TextStyle(
                            fontSize: 12.5,
                            fontWeight: FontWeight.w600,
                            color: colour)),
                    if (detail != null) ...[
                      const SizedBox(height: 2),
                      Text(detail,
                          style: const TextStyle(
                              fontSize: 11.5, color: GeoTheme.inkSoft)),
                    ],
                  ],
                ),
              ),
              if (state.connection == ServerConnection.notFound) ...[
                TextButton(
                  onPressed: state.rediscover,
                  style: TextButton.styleFrom(
                      visualDensity: VisualDensity.compact),
                  child: const Text('Retry'),
                ),
                TextButton(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const SettingsScreen()),
                  ),
                  style: TextButton.styleFrom(
                      visualDensity: VisualDensity.compact),
                  child: const Text('Enter it'),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

/// The honesty line, kept on the first screen.
///
/// It moved here when the server setup screen was removed. It belongs in front
/// of someone before they use the app, not buried in an about page.
class _WhatThisIs extends StatelessWidget {
  const _WhatThisIs();

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
