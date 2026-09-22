import 'package:flutter/material.dart';

import '../models/models.dart';
import '../theme.dart';

/// The banner that every preliminary output carries.
///
/// It is not decoration. Nothing this app produces is a foundation design, and
/// the user should never have to go looking for that fact.
class PreliminaryBanner extends StatelessWidget {
  const PreliminaryBanner({super.key, this.approved = false});

  final bool approved;

  @override
  Widget build(BuildContext context) {
    final colour = approved ? GeoTheme.pass : GeoTheme.warning;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: colour.withValues(alpha: 0.10),
        border: Border(left: BorderSide(color: colour, width: 4)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(approved ? Icons.verified_outlined : Icons.info_outline,
              size: 18, color: colour),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              approved
                  ? 'Reviewed and signed by a registered engineer.'
                  : 'Preliminary — engineer review required. This is not a '
                      'foundation design and does not certify anything as safe.',
              style: TextStyle(fontSize: 12.5, height: 1.35, color: colour.withValues(alpha: 0.95)),
            ),
          ),
        ],
      ),
    );
  }
}

/// Where a value came from. Shown next to every stored geotechnical value.
class ProvenanceChip extends StatelessWidget {
  const ProvenanceChip({super.key, required this.source, this.confidence});

  final String source;
  final double? confidence;

  static const _measured = {'LABORATORY', 'FIELD'};

  @override
  Widget build(BuildContext context) {
    final measured = _measured.contains(source);
    final colour = measured
        ? GeoTheme.pass
        : (source == 'AI' ? GeoTheme.clay : GeoTheme.inkSoft);
    final label = switch (source) {
      'LABORATORY' => 'Lab',
      'FIELD' => 'Field',
      'ENGINEER' => 'Engineer',
      'ESTIMATED' => 'Correlated',
      'IMPORTED' => 'Imported',
      'USER' => 'Entered',
      'AI' => 'AI — visual only',
      _ => source,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: colour.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: colour.withValues(alpha: 0.35)),
      ),
      child: Text(
        confidence == null
            ? label
            : '$label · ${(confidence! * 100).round()}%',
        style: TextStyle(fontSize: 11, color: colour, fontWeight: FontWeight.w600),
      ),
    );
  }
}

/// A list of engine warnings, in severity order, never collapsed away.
class WarningList extends StatelessWidget {
  const WarningList({super.key, required this.warnings});

  final List<EngineWarning> warnings;

  @override
  Widget build(BuildContext context) {
    if (warnings.isEmpty) return const SizedBox.shrink();
    const order = {'CRITICAL': 0, 'WARNING': 1, 'INFO': 2};
    final sorted = [...warnings]..sort(
        (a, b) => (order[a.severity] ?? 3).compareTo(order[b.severity] ?? 3));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final w in sorted)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Icon(
                    w.severity == 'CRITICAL'
                        ? Icons.error_outline
                        : w.severity == 'WARNING'
                            ? Icons.warning_amber_outlined
                            : Icons.info_outline,
                    size: 16,
                    color: GeoTheme.severity(w.severity),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    w.message,
                    style: const TextStyle(fontSize: 12.5, height: 1.4),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

/// A labelled figure — the unit is never separated from the number.
class Figure extends StatelessWidget {
  const Figure({super.key, required this.label, required this.value, this.unit});

  final String label;
  final String value;
  final String? unit;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: const TextStyle(
                fontSize: 11, color: GeoTheme.inkSoft, letterSpacing: 0.2)),
        const SizedBox(height: 2),
        RichText(
          text: TextSpan(
            style: GeoTheme.numeric.copyWith(fontSize: 18, color: GeoTheme.ink),
            children: [
              TextSpan(text: value),
              if (unit != null)
                TextSpan(
                  text: ' $unit',
                  style: const TextStyle(
                      fontSize: 12, fontWeight: FontWeight.w500, color: GeoTheme.inkSoft),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

/// A section heading with an optional explanatory line under it.
class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.title, this.subtitle});

  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: const TextStyle(
                fontSize: 13, fontWeight: FontWeight.w700, letterSpacing: 0.3)),
        if (subtitle != null) ...[
          const SizedBox(height: 3),
          Text(subtitle!,
              style: const TextStyle(fontSize: 12, color: GeoTheme.inkSoft, height: 1.35)),
        ],
        const SizedBox(height: 10),
      ],
    );
  }
}

/// Shows an API failure as something the user can act on.
Future<void> showApiError(BuildContext context, Object error) async {
  final message = error is ApiException ? error.message : error.toString();
  if (!context.mounted) return;
  await showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      icon: const Icon(Icons.error_outline, color: GeoTheme.critical),
      title: const Text('That did not work'),
      content: SingleChildScrollView(
        child: Text(message, style: const TextStyle(fontSize: 13.5, height: 1.4)),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    ),
  );
}
