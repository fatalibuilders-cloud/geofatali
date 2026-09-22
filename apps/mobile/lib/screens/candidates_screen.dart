import 'package:flutter/material.dart';

import '../main.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';
import 'steps_screen.dart';

/// Screen the foundation options for this site.
///
/// What comes back is a list of candidates, never one approved answer. Each
/// carries the criteria it passed, the ones a person has to look at, and the
/// data that is missing — and the construction sequence for building it here.
class CandidatesScreen extends StatefulWidget {
  const CandidatesScreen({super.key, required this.project});

  final Project project;

  @override
  State<CandidatesScreen> createState() => _CandidatesScreenState();
}

class _CandidatesScreenState extends State<CandidatesScreen> {
  final _load = TextEditingController(text: '400');
  final _allowable = TextEditingController(text: '180');
  final _width = TextEditingController(text: '1.5');
  final _settlement = TextEditingController(text: '20');
  final _spacing = TextEditingController(text: '4.5');
  final _competent = TextEditingController(text: '1.5');
  final _water = TextEditingController();
  final _uplift = TextEditingController();

  bool _expansive = false;
  bool _collapsible = false;
  bool _aggressive = false;
  bool _organic = false;
  bool _busy = false;
  List<FoundationCandidate>? _candidates;
  CalculationResult? _result;

  @override
  void dispose() {
    for (final c in [
      _load, _allowable, _width, _settlement, _spacing, _competent, _water, _uplift
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _screen() async {
    setState(() {
      _busy = true;
      _candidates = null;
    });
    try {
      final (result, candidates) =
          await AppScope.of(context).api.foundationOptions(widget.project.id, {
        'sector': widget.project.sector,
        'standard': widget.project.designStandard,
        if (double.tryParse(_load.text) != null)
          'service_load_kn': double.parse(_load.text),
        if (double.tryParse(_allowable.text) != null)
          'net_allowable_kpa': double.parse(_allowable.text),
        if (double.tryParse(_width.text) != null)
          'required_footing_width_m': double.parse(_width.text),
        if (double.tryParse(_allowable.text) != null &&
            double.tryParse(_load.text) != null &&
            double.tryParse(_width.text) != null)
          'utilisation': (double.parse(_load.text) /
                  (double.parse(_width.text) * double.parse(_width.text))) /
              double.parse(_allowable.text),
        if (double.tryParse(_settlement.text) != null)
          'total_settlement_mm': double.parse(_settlement.text),
        if (double.tryParse(_spacing.text) != null)
          'column_spacing_m': double.parse(_spacing.text),
        if (double.tryParse(_competent.text) != null)
          'competent_stratum_depth_m': double.parse(_competent.text),
        if (double.tryParse(_uplift.text) != null)
          'uplift_kn': double.parse(_uplift.text),
        'findings': {
          'expansive_clay': _expansive,
          if (_expansive) 'swell_potential': 'HIGH',
          'collapsible_soil': _collapsible,
          'aggressive_ground': _aggressive,
          'organic_or_peat': _organic,
          if (double.tryParse(_water.text) != null)
            'groundwater_depth_m': double.parse(_water.text),
          if (double.tryParse(_water.text) != null &&
              double.parse(_water.text) < 2.0)
            'high_water_table': true,
        },
      });
      if (mounted) {
        setState(() {
          _candidates = candidates;
          _result = result;
        });
      }
    } on Object catch (error) {
      if (mounted) await showApiError(context, error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Foundation options')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
        children: [
          const SectionHeader(
            title: 'THE NUMBERS',
            subtitle: 'What the calculations and the investigation have told you so far.',
          ),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _load,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Column load', suffixText: 'kN'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                controller: _allowable,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration:
                    const InputDecoration(labelText: 'Net allowable', suffixText: 'kPa'),
              ),
            ),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _width,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration:
                    const InputDecoration(labelText: 'Footing width', suffixText: 'm'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                controller: _spacing,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration:
                    const InputDecoration(labelText: 'Column spacing', suffixText: 'm'),
              ),
            ),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _settlement,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration:
                    const InputDecoration(labelText: 'Settlement', suffixText: 'mm'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                controller: _competent,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                    labelText: 'Competent stratum at', suffixText: 'm'),
              ),
            ),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _water,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration:
                    const InputDecoration(labelText: 'Water table', suffixText: 'm'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                controller: _uplift,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Uplift', suffixText: 'kN'),
              ),
            ),
          ]),
          const SizedBox(height: 22),
          const SectionHeader(
            title: 'WHAT DID YOU FIND?',
            subtitle: 'These change the ranking and add steps to the construction '
                'sequence — expansive clay puts a removal step before excavation.',
          ),
          _Toggle(
            value: _expansive,
            onChanged: (v) => setState(() => _expansive = v),
            title: 'Expansive (black cotton) clay',
            subtitle: 'Swells wet, shrinks dry, moves foundations seasonally.',
          ),
          _Toggle(
            value: _collapsible,
            onChanged: (v) => setState(() => _collapsible = v),
            title: 'Collapsible volcanic soil',
            subtitle: 'Stands up dry, loses strength suddenly when wetted.',
          ),
          _Toggle(
            value: _aggressive,
            onChanged: (v) => setState(() => _aggressive = v),
            title: 'Aggressive ground chemistry',
            subtitle: 'Sulphates or chlorides attacking buried concrete.',
          ),
          _Toggle(
            value: _organic,
            onChanged: (v) => setState(() => _organic = v),
            title: 'Organic soil or peat',
            subtitle: 'Compresses for decades. Removed, never built on.',
          ),
          const SizedBox(height: 22),
          FilledButton(
            onPressed: _busy ? null : _screen,
            child: _busy
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Text('Screen the options'),
          ),
          if (_candidates != null) ...[
            const SizedBox(height: 26),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: GeoTheme.warning.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'These are candidate options, not a foundation design. Choosing '
                'between them, sizing the chosen system and detailing it are '
                'engineering decisions for a qualified engineer.',
                style: TextStyle(fontSize: 12, height: 1.45, color: GeoTheme.warning),
              ),
            ),
            const SizedBox(height: 14),
            for (final candidate in _candidates!) ...[
              _CandidateCard(
                candidate: candidate,
                project: widget.project,
              ),
              const SizedBox(height: 10),
            ],
            if (_result != null && _result!.warnings.isNotEmpty) ...[
              const SizedBox(height: 8),
              WarningList(warnings: _result!.warnings),
            ],
          ],
        ],
      ),
    );
  }
}

class _Toggle extends StatelessWidget {
  const _Toggle({
    required this.value,
    required this.onChanged,
    required this.title,
    required this.subtitle,
  });

  final bool value;
  final ValueChanged<bool> onChanged;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => SwitchListTile(
        value: value,
        onChanged: onChanged,
        contentPadding: EdgeInsets.zero,
        title: Text(title, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
        subtitle: Text(subtitle,
            style: const TextStyle(fontSize: 11.5, height: 1.3, color: GeoTheme.inkSoft)),
      );
}

class _CandidateCard extends StatelessWidget {
  const _CandidateCard({required this.candidate, required this.project});

  final FoundationCandidate candidate;
  final Project project;

  Color get _statusColour => switch (candidate.status) {
        'PRELIMINARY_CANDIDATE' => GeoTheme.pass,
        'CANDIDATE_WITH_CONDITIONS' => GeoTheme.warning,
        'NOT_RECOMMENDED' => GeoTheme.critical,
        _ => GeoTheme.info,
      };

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(candidate.label,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _statusColour.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(candidate.statusLabel,
                      style: TextStyle(
                          fontSize: 10.5, fontWeight: FontWeight.w700, color: _statusColour)),
                ),
              ],
            ),
            const SizedBox(height: 10),
            for (final criterion in candidate.criteria)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 112,
                      child: Text(criterion.name,
                          style: const TextStyle(fontSize: 11.5, color: GeoTheme.inkSoft)),
                    ),
                    SizedBox(
                      width: 62,
                      child: Text(
                        criterion.verdict,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: GeoTheme.severity(criterion.verdict),
                        ),
                      ),
                    ),
                    Expanded(
                      child: Text(criterion.evidence,
                          style: const TextStyle(fontSize: 11.5, height: 1.35)),
                    ),
                  ],
                ),
              ),
            if (candidate.rationale.isNotEmpty) ...[
              const SizedBox(height: 6),
              for (final line in candidate.rationale)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text('— $line',
                      style: const TextStyle(
                          fontSize: 12, height: 1.4, color: GeoTheme.navy)),
                ),
            ],
            if (candidate.conditions.isNotEmpty) ...[
              const SizedBox(height: 8),
              for (final line in candidate.conditions)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text('Condition: $line',
                      style: const TextStyle(
                          fontSize: 11.5, height: 1.4, color: GeoTheme.clay)),
                ),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => StepsScreen(candidate: candidate),
                    )),
                    icon: const Icon(Icons.format_list_numbered, size: 17),
                    label: Text('How to build it (${candidate.steps.length})'),
                  ),
                ),
                if (candidate.id != null) ...[
                  const SizedBox(width: 8),
                  IconButton.filledTonal(
                    tooltip: 'Record this as the chosen system',
                    onPressed: () async {
                      try {
                        await AppScope.of(context)
                            .api
                            .selectFoundation(project.id, candidate.id!);
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('${candidate.label} recorded as chosen')),
                          );
                        }
                      } on Object catch (error) {
                        if (context.mounted) await showApiError(context, error);
                      }
                    },
                    icon: const Icon(Icons.check, size: 18),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}
