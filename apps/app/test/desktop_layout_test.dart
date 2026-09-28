import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geofatali/models/models.dart';
import 'package:geofatali/screens/project_screen.dart';
import 'package:geofatali/screens/sign_in_screen.dart';
import 'package:geofatali/main.dart';
import 'package:geofatali/state/app_state.dart';
import 'package:geofatali/theme.dart';
import 'package:geofatali/widgets/layout.dart';

/// The desktop build is the same code as the phone build. What changes is the
/// width of the window, so that is what these tests change.
Widget _wrap(Widget child) {
  final state = AppState()..setConnectionForTest(ServerConnection.connected);
  return MaterialApp(
    theme: GeoTheme.build(),
    home: AppScope(state: state, child: child),
  );
}

Future<void> _atWidth(WidgetTester tester, double width, Widget child) async {
  tester.view.physicalSize = Size(width, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(_wrap(child));
  await tester.pump();
}

void main() {
  group('the breakpoint', () {
    testWidgets('a narrow window is laid out as a phone', (tester) async {
      late bool wide;
      await _atWidth(
        tester,
        420,
        Builder(builder: (context) {
          wide = Layout.isWide(context);
          return const SizedBox();
        }),
      );
      expect(wide, isFalse);
    });

    testWidgets('a desktop-sized window is not', (tester) async {
      late bool wide;
      await _atWidth(
        tester,
        1280,
        Builder(builder: (context) {
          wide = Layout.isWide(context);
          return const SizedBox();
        }),
      );
      expect(wide, isTrue);
    });
  });

  group('content width', () {
    testWidgets('a form is held to a column rather than stretched across a monitor',
        (tester) async {
      await _atWidth(tester, 1600, const SignInScreen());

      final field = tester.getSize(find.widgetWithText(TextField, 'Email'));
      expect(field.width, lessThanOrEqualTo(ContentWidth.form));
      expect(field.width, greaterThan(200), reason: 'still usable, not a sliver');
    });

    testWidgets('on a phone the same form fills the width it has', (tester) async {
      await _atWidth(tester, 400, const SignInScreen());

      // 400 wide minus the 24pt gutters the screen has always had.
      final field = tester.getSize(find.widgetWithText(TextField, 'Email'));
      expect(field.width, closeTo(400 - 48, 1));
    });

    testWidgets('the pane is centred, so a wide window is not left-heavy',
        (tester) async {
      await _atWidth(tester, 1600, const SignInScreen());

      final box = tester.getRect(find.byType(CenteredPane).first);
      expect(box.center.dx, closeTo(800, 1));
    });

    testWidgets('a pane never narrows content below what it was given',
        (tester) async {
      await _atWidth(
        tester,
        300,
        const CenteredPane(
          maxWidth: ContentWidth.form,
          child: SizedBox.expand(key: Key('pane-child')),
        ),
      );
      expect(tester.getSize(find.byKey(const Key('pane-child'))).width, 300);
    });
  });

  group('primary actions', () {
    test('an action can be rendered either way from one definition', () {
      var pressed = 0;
      final action = PrimaryAction(
        label: 'New project',
        icon: Icons.add,
        onPressed: () => pressed++,
      );
      expect(action.asAppBarButton(), isA<Widget>());
      expect(action.asFloatingButton(), isA<FloatingActionButton>());
      expect(pressed, 0, reason: 'building a button must not invoke it');
    });

    testWidgets('a floating button is a phone idiom and stays on the phone',
        (tester) async {
      final action = PrimaryAction(
        label: 'New project',
        icon: Icons.add,
        onPressed: () {},
      );
      await _atWidth(
        tester,
        1280,
        Scaffold(appBar: AppBar(actions: [action.asAppBarButton()])),
      );
      expect(find.byType(FloatingActionButton), findsNothing);
      expect(find.widgetWithText(TextButton, 'New project'), findsOneWidget);
    });
  });

  group('navigating a project', () {
    final project = Project(
      id: 'p1',
      name: 'Nyali site',
      sector: 'buildings_low_rise',
      designStandard: 'eurocode',
      country: 'Kenya',
      administrativeArea: 'Mombasa',
      status: 'draft',
      updatedAt: DateTime.utc(2026, 1, 1),
    );

    testWidgets('a phone gets the bottom bar its thumb can reach',
        (tester) async {
      await _atWidth(tester, 400, ProjectScreen(project: project));
      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.byType(NavigationRail), findsNothing);
    });

    testWidgets('a window gets a rail instead, beside the content',
        (tester) async {
      // The bottom of a monitor is the furthest point from both the content
      // and the reader's eye, which is the wrong place for navigation.
      await _atWidth(tester, 1280, ProjectScreen(project: project));
      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
    });

    testWidgets('the same three destinations either way', (tester) async {
      for (final width in [400.0, 1280.0]) {
        await _atWidth(tester, width, ProjectScreen(project: project));
        for (final label in ['Ground', 'Calculations', 'Report']) {
          expect(find.text(label), findsOneWidget, reason: 'at $width');
        }
      }
    });
  });
}
