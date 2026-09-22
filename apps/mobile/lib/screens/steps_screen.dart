import 'package:flutter/material.dart';

import '../models/models.dart';
import '../theme.dart';

/// What to actually do on site, in order.
///
/// This is the screen a site agent uses standing in the excavation. Hold points
/// are where work stops for inspection, and steps that exist because of what
/// the investigation found here say what triggered them — the sequence is
/// assembled for this ground, not a generic checklist.
class StepsScreen extends StatelessWidget {
  const StepsScreen({super.key, required this.candidate});

  final FoundationCandidate candidate;

  @override
  Widget build(BuildContext context) {
    final holds = candidate.steps.where((s) => s.holdPoint).length;
    return Scaffold(
      appBar: AppBar(title: Text(candidate.label)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: GeoTheme.navy.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${candidate.steps.length} steps · $holds hold points',
                    style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                const Text(
                  'A hold point is where work stops until an engineer has inspected. '
                  'This is a construction sequence, not a design.',
                  style: TextStyle(fontSize: 11.5, height: 1.4, color: GeoTheme.inkSoft),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          for (final step in candidate.steps) _StepTile(step: step),
        ],
      ),
    );
  }
}

class _StepTile extends StatelessWidget {
  const _StepTile({required this.step});

  final ConstructionStep step;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 26,
                    height: 26,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: step.holdPoint
                          ? GeoTheme.critical.withValues(alpha: 0.12)
                          : GeoTheme.navy.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text('${step.order}',
                        style: GeoTheme.numeric.copyWith(
                          fontSize: 12,
                          color: step.holdPoint ? GeoTheme.critical : GeoTheme.navy,
                        )),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(step.title,
                            style: const TextStyle(
                                fontSize: 14, fontWeight: FontWeight.w700, height: 1.3)),
                        if (step.holdPoint) ...[
                          const SizedBox(height: 4),
                          Container(
                            padding:
                                const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: GeoTheme.critical.withValues(alpha: 0.10),
                              borderRadius: BorderRadius.circular(3),
                            ),
                            child: const Text('HOLD POINT',
                                style: TextStyle(
                                    fontSize: 9.5,
                                    letterSpacing: 0.6,
                                    fontWeight: FontWeight.w800,
                                    color: GeoTheme.critical)),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(step.detail,
                  style: const TextStyle(fontSize: 12.5, height: 1.5, color: GeoTheme.ink)),
              if (step.verify != null) ...[
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: GeoTheme.surface,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.check_circle_outline,
                          size: 15, color: GeoTheme.pass),
                      const SizedBox(width: 7),
                      Expanded(
                        child: Text(step.verify!,
                            style: const TextStyle(
                                fontSize: 11.5, height: 1.4, color: GeoTheme.inkSoft)),
                      ),
                    ],
                  ),
                ),
              ],
              if (step.triggeredBy != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Icon(Icons.arrow_right_alt, size: 15, color: GeoTheme.clay),
                    const SizedBox(width: 5),
                    Expanded(
                      child: Text(
                        'Added because of this site: ${step.triggeredBy}',
                        style: const TextStyle(
                            fontSize: 11, color: GeoTheme.clay, height: 1.35),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
