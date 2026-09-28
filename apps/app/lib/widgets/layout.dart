import 'package:flutter/material.dart';

import '../theme.dart';

/// One build, two shapes: a phone held in one hand, and a window on a monitor.
///
/// Nothing here adds features to the desktop version. The difference between
/// the two is width, and width is a typographic problem before it is a layout
/// one — a line of text stops being readable somewhere past ninety characters,
/// and a form field a foot wide is worse than one that is not. So content is
/// held to a column of a sensible width and the rest of a large window is
/// allowed to stay empty, which is what desktop software that respects its
/// reader does.
///
/// The breakpoint is on width alone, not on the platform. A Flutter desktop
/// window dragged narrow should look like the phone layout, because at that
/// width the phone layout is the correct one; a tablet or a foldable gets the
/// wide layout for the same reason. Asking `Platform.isWindows` would get both
/// of those wrong.
abstract final class Layout {
  /// Below this the phone layout is used, at or above it the wide one.
  ///
  /// 760 rather than a rounder number: it is just above the point at which a
  /// [ContentWidth.reading] column plus its gutters stops fitting, so the
  /// switch happens exactly when centring starts to do something.
  static const double wideBreakpoint = 760;

  static bool isWide(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= wideBreakpoint;
}

/// How wide a given kind of content is allowed to get.
abstract final class ContentWidth {
  /// Single-column forms: sign in, a new project, a borehole.
  static const double form = 560;

  /// Prose and results — the honesty notes, warnings, construction steps.
  static const double reading = 820;

  /// Card lists and anything tabular, which can take more room usefully.
  static const double list = 1080;
}

/// Holds its child to a readable column and centres it horizontally.
///
/// Used at the [Scaffold.body] level rather than inside each list, so the
/// scroll view itself is what gets narrowed. That puts the scrollbar at the
/// edge of the content instead of stranding it against the window frame, and
/// it costs nothing on a phone, where the constraint is never reached.
class CenteredPane extends StatelessWidget {
  const CenteredPane({
    super.key,
    required this.child,
    this.maxWidth = ContentWidth.reading,
  });

  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: child,
      ),
    );
  }
}

/// A primary action that is a floating button on a phone and a real button in
/// the app bar on a wide window.
///
/// A floating action button is a phone idiom. On a desktop it lands in the
/// bottom-right corner of a window that may be a metre from where the user is
/// looking, and it covers content. The same action belongs in the app bar,
/// next to everything else that acts on the screen.
///
/// This returns the app-bar form; [asFloatingButton] returns the other. A
/// screen asks for whichever the current width calls for.
class PrimaryAction {
  const PrimaryAction({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;

  Widget asAppBarButton() => Padding(
        padding: const EdgeInsets.only(right: 8),
        child: TextButton.icon(
          onPressed: onPressed,
          icon: Icon(icon, size: 18),
          label: Text(label),
          style: TextButton.styleFrom(
            foregroundColor: Colors.white,
            backgroundColor: Colors.white.withValues(alpha: 0.14),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          ),
        ),
      );

  Widget asFloatingButton() => FloatingActionButton.extended(
        onPressed: onPressed,
        backgroundColor: GeoTheme.navy,
        foregroundColor: Colors.white,
        icon: Icon(icon),
        label: Text(label),
      );
}
