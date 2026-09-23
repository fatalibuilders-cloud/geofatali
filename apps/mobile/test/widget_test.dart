import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geofatali/main.dart';
import 'package:geofatali/models/models.dart';
import 'package:geofatali/screens/sign_in_screen.dart';
import 'package:geofatali/screens/steps_screen.dart';
import 'package:geofatali/state/app_state.dart';
import 'package:geofatali/theme.dart';
import 'package:geofatali/widgets/common.dart';

Widget _wrap(Widget child, {ServerConnection? connection}) {
  final state = AppState();
  if (connection != null) state.setConnectionForTest(connection);
  return MaterialApp(
    theme: GeoTheme.build(),
    home: AppScope(state: state, child: child),
  );
}

void main() {
  testWidgets('the first screen asks for an email, not a server address',
      (tester) async {
    await tester.pumpWidget(_wrap(const SignInScreen()));
    await tester.pump();

    expect(find.text('GeoFatali'), findsOneWidget);
    expect(find.text('Sign in'), findsWidgets);
    expect(find.widgetWithText(TextField, 'Email'), findsOneWidget);
    expect(find.widgetWithText(TextField, 'Password'), findsOneWidget);

    // The thing this change was about: no IP address in front of a new user.
    expect(find.textContaining('WHERE IS YOUR SERVER'), findsNothing);
    expect(find.textContaining('192.168'), findsNothing);
    expect(find.textContaining('server'), findsNothing);

    // The honesty line stays on the first screen, not buried in an about page.
    expect(find.textContaining('not a site investigation'), findsOneWidget);
    expect(find.textContaining('cannot establish bearing capacity'), findsOneWidget);
  });

  testWidgets('sign in needs a filled form AND a server', (tester) async {
    await tester.pumpWidget(
        _wrap(const SignInScreen(), connection: ServerConnection.connected));
    await tester.pump();

    FilledButton button() =>
        tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Sign in'));
    expect(button().onPressed, isNull, reason: 'empty form');

    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'a@b.com');
    await tester.enterText(
        find.widgetWithText(TextField, 'Password'), 'a-long-enough-passphrase');
    await tester.pump();

    expect(button().onPressed, isNotNull);
  });

  testWidgets('sign in is held back until the app can actually connect',
      (tester) async {
    await tester.pumpWidget(
        _wrap(const SignInScreen(), connection: ServerConnection.notFound));
    await tester.pump();

    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'a@b.com');
    await tester.enterText(
        find.widgetWithText(TextField, 'Password'), 'a-long-enough-passphrase');
    await tester.pump();

    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Sign in'))
          .onPressed,
      isNull,
    );
    expect(find.textContaining('Cannot connect right now'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Retry'), findsOneWidget);
  });

  testWidgets('while getting ready it shows a spinner, not an explanation',
      (tester) async {
    await tester.pumpWidget(
        _wrap(const SignInScreen(), connection: ServerConnection.searching));
    await tester.pump();
    expect(find.textContaining('Getting ready'), findsOneWidget);
  });

  testWidgets('when connected, nothing about connecting is shown at all',
      (tester) async {
    await tester.pumpWidget(
        _wrap(const SignInScreen(), connection: ServerConnection.connected));
    await tester.pump();
    expect(find.textContaining('Getting ready'), findsNothing);
    expect(find.textContaining('Cannot connect'), findsNothing);
  });

  testWidgets('the word server appears nowhere a user can see it',
      (tester) async {
    // The app finds the backend itself. Servers, addresses and ports are the
    // app's problem and are never put in front of the person using it.
    for (final connection in ServerConnection.values) {
      await tester.pumpWidget(_wrap(const SignInScreen(), connection: connection));
      await tester.pump();

      final visible = tester
          .widgetList<Text>(find.byType(Text))
          .map((t) => (t.data ?? '').toLowerCase())
          .join(' ');
      expect(visible, isNot(contains('server')), reason: '$connection');
      expect(visible, isNot(contains('address')), reason: '$connection');
      expect(visible, isNot(contains('192.168')), reason: '$connection');
      expect(visible, isNot(contains('port')), reason: '$connection');
      expect(visible, isNot(contains('network')), reason: '$connection');
    }
  });

  testWidgets('creating an account asks for a name and warns about the role',
      (tester) async {
    await tester.pumpWidget(_wrap(const SignInScreen()));
    await tester.pump();

    await tester.tap(find.widgetWithText(TextButton, 'Create an account'));
    await tester.pump();

    expect(find.widgetWithText(TextField, 'Your name'), findsOneWidget);
    expect(find.textContaining('cannot be claimed here'), findsOneWidget);
  });

  testWidgets('the preliminary banner says what the output is not', (tester) async {
    await tester.pumpWidget(_wrap(const Scaffold(body: PreliminaryBanner())));
    expect(find.textContaining('Preliminary'), findsOneWidget);
    expect(find.textContaining('not a foundation design'), findsOneWidget);
  });

  testWidgets('an approved banner replaces it rather than sitting alongside',
      (tester) async {
    await tester.pumpWidget(
        _wrap(const Scaffold(body: PreliminaryBanner(approved: true))));
    expect(find.textContaining('Reviewed and signed'), findsOneWidget);
    expect(find.textContaining('Preliminary'), findsNothing);
  });

  testWidgets('a provenance chip distinguishes measured from observed',
      (tester) async {
    await tester.pumpWidget(_wrap(const Scaffold(
      body: Column(children: [
        ProvenanceChip(source: 'LABORATORY'),
        ProvenanceChip(source: 'AI', confidence: 0.81),
        ProvenanceChip(source: 'ESTIMATED'),
      ]),
    )));
    expect(find.text('Lab'), findsOneWidget);
    expect(find.text('AI — visual only · 81%'), findsOneWidget);
    expect(find.text('Correlated'), findsOneWidget);
  });

  testWidgets('warnings are shown critical-first and never collapsed away',
      (tester) async {
    await tester.pumpWidget(_wrap(const Scaffold(
      body: WarningList(warnings: [
        EngineWarning(severity: 'INFO', code: 'A', message: 'Just so you know.'),
        EngineWarning(severity: 'CRITICAL', code: 'B', message: 'Cannot proceed.'),
        EngineWarning(severity: 'WARNING', code: 'C', message: 'Worth checking.'),
      ]),
    )));
    final texts = tester.widgetList<Text>(find.byType(Text)).map((t) => t.data).toList();
    expect(texts.indexOf('Cannot proceed.'), lessThan(texts.indexOf('Worth checking.')));
    expect(texts.indexOf('Worth checking.'), lessThan(texts.indexOf('Just so you know.')));
  });

  testWidgets('construction steps show hold points and what triggered them',
      (tester) async {
    const candidate = FoundationCandidate(
      foundationType: 'strip',
      label: 'Strip footing',
      status: 'CANDIDATE_WITH_CONDITIONS',
      criteria: [],
      rationale: [],
      conditions: [],
      missingData: [],
      relativeCost: 'low',
      steps: [
        ConstructionStep(
          order: 1,
          title: 'Remove or isolate the expansive clay',
          detail: 'Excavate it out under the footprint.',
          holdPoint: true,
          verify: 'Trial pit records across the footprint.',
          triggeredBy: 'Expansive clay identified in the investigation',
        ),
        ConstructionStep(
          order: 2,
          title: 'Set out and confirm levels',
          detail: 'Set out from the approved drawings.',
          holdPoint: false,
        ),
      ],
    );

    await tester.pumpWidget(_wrap(const StepsScreen(candidate: candidate)));
    await tester.pump();

    expect(find.text('2 steps · 1 hold points'), findsOneWidget);
    expect(find.text('HOLD POINT'), findsOneWidget);
    expect(find.textContaining('Added because of this site'), findsOneWidget);
    expect(find.textContaining('Trial pit records'), findsOneWidget);
  });
}
