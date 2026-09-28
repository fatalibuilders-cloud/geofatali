import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geofatali/main.dart';
import 'package:geofatali/state/app_state.dart';

/// Every screen past the first is reached with Navigator.push, and every one
/// of them reads the API client off AppScope. If AppScope is not above the
/// Navigator, all of them fail — and they fail in the release build only,
/// because the check that caught it was an assert.
void main() {
  testWidgets('a pushed route can still reach the app state', (tester) async {
    await tester.pumpWidget(const GeoFataliApp());
    await tester.pump();

    final navigator = tester.state<NavigatorState>(find.byType(Navigator));
    AppState? reached;
    Object? failure;

    unawaited(navigator.push(MaterialPageRoute<void>(
      builder: (context) {
        try {
          reached = AppScope.of(context);
        } on Object catch (error) {
          failure = error;
        }
        return const Scaffold();
      },
    )));
    await tester.pumpAndSettle();

    expect(failure, isNull, reason: 'AppScope must be above the Navigator');
    expect(reached, isNotNull);
  });

  testWidgets('the scope is above MaterialApp, not inside its home',
      (tester) async {
    await tester.pumpWidget(const GeoFataliApp());
    await tester.pump();

    expect(
      find.ancestor(of: find.byType(MaterialApp), matching: find.byType(AppScope)),
      findsOneWidget,
    );
  });

  testWidgets('missing it says what is wrong instead of crashing on a null',
      (tester) async {
    Object? error;
    await tester.pumpWidget(MaterialApp(
      home: Builder(builder: (context) {
        try {
          AppScope.of(context);
        } on Object catch (e) {
          error = e;
        }
        return const Scaffold();
      }),
    ));
    expect(error, isA<FlutterError>());
    expect('$error', contains('above MaterialApp'));
  });
}

/// Pushing a route returns a future that completes when it is popped; nothing
/// here waits for that.
void unawaited(Future<void> future) {}
