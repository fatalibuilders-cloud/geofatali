import 'package:flutter/material.dart';

import '../main.dart';
import '../theme.dart';
import '../widgets/common.dart';

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

  Future<void> _submit() async {
    if (_email.text.trim().isEmpty || _password.text.isEmpty) return;
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
    final state = AppScope.of(context);
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 56, 20, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.layers_outlined, size: 36, color: GeoTheme.navy),
              const SizedBox(height: 14),
              Text(_registering ? 'Create an account' : 'Sign in',
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text(state.baseUrl ?? '',
                  style: const TextStyle(fontSize: 12.5, color: GeoTheme.inkSoft)),
              const SizedBox(height: 28),
              if (_registering) ...[
                TextField(
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
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
                decoration: const InputDecoration(
                  labelText: 'Email',
                  prefixIcon: Icon(Icons.mail_outline, size: 20),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _password,
                obscureText: _obscure,
                textInputAction: TextInputAction.go,
                onSubmitted: (_) => _submit(),
                decoration: InputDecoration(
                  labelText: 'Password',
                  prefixIcon: const Icon(Icons.lock_outline, size: 20),
                  suffixIcon: IconButton(
                    icon: Icon(_obscure ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                        size: 20),
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
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _busy ? null : _submit,
                child: _busy
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : Text(_registering ? 'Create account' : 'Sign in'),
              ),
              const SizedBox(height: 4),
              TextButton(
                onPressed: _busy ? null : () => setState(() => _registering = !_registering),
                child: Text(_registering
                    ? 'I already have an account'
                    : 'Create an account'),
              ),
              const Divider(height: 32),
              TextButton.icon(
                // Clearing the address drops the app back to the setup screen,
                // which the root widget rebuilds automatically.
                onPressed: _busy ? null : () => AppScope.of(context).clearBaseUrl(),
                icon: const Icon(Icons.dns_outlined, size: 18),
                label: const Text('Use a different server'),
              ),
              if (_registering) ...[
                const SizedBox(height: 16),
                const Text(
                  'An engineer account — the only kind that can sign an assessment '
                  'off — is granted by an administrator against a verified board '
                  'registration. It cannot be claimed here.',
                  style: TextStyle(fontSize: 11.5, color: GeoTheme.inkSoft, height: 1.4),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
