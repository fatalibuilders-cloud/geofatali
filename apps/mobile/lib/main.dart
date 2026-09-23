import 'package:flutter/material.dart';

import 'screens/projects_screen.dart';
import 'screens/sign_in_screen.dart';
import 'state/app_state.dart';
import 'widgets/brand_mark.dart';
import 'theme.dart';

void main() {
  runApp(const GeoFataliApp());
}

class GeoFataliApp extends StatefulWidget {
  const GeoFataliApp({super.key});

  @override
  State<GeoFataliApp> createState() => _GeoFataliAppState();
}

class _GeoFataliAppState extends State<GeoFataliApp> {
  final AppState _state = AppState();

  @override
  void initState() {
    super.initState();
    _state.restore();
  }

  @override
  void dispose() {
    _state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GeoFatali',
      debugShowCheckedModeBanner: false,
      theme: GeoTheme.build(),
      home: AppScope(
        state: _state,
        child: AnimatedBuilder(
          animation: _state,
          builder: (context, _) {
            if (!_state.ready) return const _Splash();
            // Sign in is the front door. The server address is baked into the
            // build and overridable in Settings, not asked for on launch.
            if (!_state.isSignedIn) return const SignInScreen();
            return const ProjectsScreen();
          },
        ),
      ),
    );
  }
}

/// Makes the single AppState available without pulling in a state package.
class AppScope extends InheritedWidget {
  const AppScope({super.key, required this.state, required super.child});

  final AppState state;

  static AppState of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'No AppScope above this widget');
    return scope!.state;
  }

  @override
  bool updateShouldNotify(AppScope oldWidget) => oldWidget.state != state;
}

class _Splash extends StatelessWidget {
  const _Splash();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: GeoTheme.navy,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            BrandMark(size: 56, color: Colors.white),
            SizedBox(height: 16),
            Text('GeoFatali',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.5)),
            SizedBox(height: 6),
            Text('Geotechnical & foundation engineering',
                style: TextStyle(color: Colors.white70, fontSize: 13)),
            SizedBox(height: 28),
            SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white54),
            ),
            SizedBox(height: 40),
            Text('Fatalibuilders',
                style: TextStyle(color: Colors.white38, fontSize: 11, letterSpacing: 1.5)),
          ],
        ),
      ),
    );
  }
}
