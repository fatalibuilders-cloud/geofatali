import 'package:flutter/material.dart';

import '../theme.dart';

/// The GeoFatali mark: two stacked strata seen in section.
///
/// Taken from the brand starter rather than the generic Material layers icon,
/// and reworked to scale properly — the original was drawn at a fixed 64px
/// with hard-coded insets, so it distorted at any other size. Here every
/// coordinate is a fraction of the box and the stroke scales with it, so the
/// same mark works at 28px in an app bar and at 96px on a splash.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 64, this.color});

  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: size,
        height: size,
        child: CustomPaint(
          painter: _MarkPainter(color ?? GeoTheme.navy),
          isComplex: false,
        ),
      );
}

class _MarkPainter extends CustomPainter {
  const _MarkPainter(this.color);

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.shortestSide;
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = s * 0.078
      ..strokeJoin = StrokeJoin.miter
      ..isAntiAlias = true;

    final cx = size.width / 2;

    // Upper stratum.
    final upper = Path()
      ..moveTo(cx, s * 0.09)
      ..lineTo(size.width - s * 0.11, s * 0.39)
      ..lineTo(cx, s * 0.69)
      ..lineTo(s * 0.11, s * 0.39)
      ..close();

    // Lower stratum, offset so the two read as layers rather than one shape.
    final lower = Path()
      ..moveTo(cx, s * 0.39)
      ..lineTo(size.width - s * 0.11, s * 0.69)
      ..lineTo(cx, s * 0.91)
      ..lineTo(s * 0.11, s * 0.61)
      ..close();

    canvas.drawPath(upper, paint);
    canvas.drawPath(lower, paint);
  }

  @override
  bool shouldRepaint(covariant _MarkPainter oldDelegate) =>
      oldDelegate.color != color;
}
