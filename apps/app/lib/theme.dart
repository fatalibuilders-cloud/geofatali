import 'package:flutter/material.dart';

/// The visual language.
///
/// Spec section 60: this must feel like professional engineering software, not
/// a chat app. That means a restrained palette, real data density, monospaced
/// numbers so columns of depths and pressures line up, and enough contrast to
/// be readable on a phone in daylight on a building site — which is where it
/// will actually be used.
class GeoTheme {
  static const Color navy = Color(0xFF12324A);
  static const Color navyDark = Color(0xFF0B2233);
  static const Color clay = Color(0xFFB4652A);
  static const Color surface = Color(0xFFF6F7F9);
  static const Color line = Color(0xFFD8DEE5);
  static const Color ink = Color(0xFF1A2430);
  static const Color inkSoft = Color(0xFF5A6875);

  /// Severity colours, used identically everywhere a warning appears.
  static const Color critical = Color(0xFFB3261E);
  static const Color warning = Color(0xFFB26A00);
  static const Color info = Color(0xFF2B5F8A);
  static const Color pass = Color(0xFF1E6B45);

  static Color severity(String value) => switch (value.toUpperCase()) {
        'CRITICAL' || 'FAIL' => critical,
        'WARNING' || 'REVIEW' => warning,
        'PASS' => pass,
        _ => info,
      };

  static ThemeData build() {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: navy,
        primary: navy,
        secondary: clay,
        surface: Colors.white,
      ),
    );
    return base.copyWith(
      scaffoldBackgroundColor: surface,
      appBarTheme: const AppBarTheme(
        backgroundColor: navy,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: line),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: line),
        ),
        isDense: true,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
      ),
      textTheme: base.textTheme.apply(bodyColor: ink, displayColor: ink),
      dividerTheme: const DividerThemeData(color: line, space: 1, thickness: 1),
    );
  }

  /// For numbers that belong in a column: depths, pressures, blow counts.
  static const TextStyle numeric = TextStyle(
    fontFeatures: [FontFeature.tabularFigures()],
    fontWeight: FontWeight.w600,
  );
}
