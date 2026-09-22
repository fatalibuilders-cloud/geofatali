import 'package:flutter/material.dart';

import '../main.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Run a bearing capacity calculation against this project.
///
/// The form makes the analysis type an explicit choice rather than a hidden
/// default, because drained and undrained are different questions with
/// different answers, and a clay usually needs both.
class BearingCapacityScreen extends StatefulWidget {
  const BearingCapacityScreen({super.key, required this.project});

  final Project project;

  @override
  State<BearingCapacityScreen> createState() => _BearingCapacityScreenState();
}

class _BearingCapacityScreenState extends State<BearingCapacityScreen> {
  final _unitWeight = TextEditingController(text: '18');
  final _cohesion = TextEditingController();
  final _friction = TextEditingController();
  final _width = TextEditingController(text: '2.0');
  final _depth = TextEditingController(text: '1.5');
  final _water = TextEditingController();

  String _analysis = 'drained';
  String _method = 'vesic';
  String _shape = 'square';
  String _source = 'USER';
  bool _busy = false;
  CalculationResult? _result;

  @override
  void dispose() {
    for (final c in [_unitWeight, _cohesion, _friction, _width, _depth, _water]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _run() async {
    setState(() {
      _busy = true;
      _result = null;
    });
    try {
      final result = await AppScope.of(context).api.bearingCapacity(widget.project.id, {
        'soil': {
          'unit_weight_kn_m3': double.tryParse(_unitWeight.text) ?? 18,
          if (double.tryParse(_cohesion.text) != null)
            'cohesion_kpa': double.parse(_cohesion.text),
          if (_analysis == 'drained' && double.tryParse(_friction.text) != null)
            'friction_angle_deg': double.parse(_friction.text),
          'analysis': _analysis,
          'cohesion_source': _source,
          'friction_source': _source,
        },
        'foundation': {
          'width_m': double.tryParse(_width.text) ?? 2.0,
          'depth_m': double.tryParse(_depth.text) ?? 1.5,
          'shape': _shape,
        },
        'groundwater': {
          if (double.tryParse(_water.text) != null)
            'groundwater_depth_m': double.parse(_water.text),
        },
        'method': _method,
        'standard': widget.project.designStandard,
      });
      if (mounted) setState(() => _result = result);
    } on Object catch (error) {
      if (mounted) await showApiError(context, error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final undrained = _analysis == 'undrained';
    return Scaffold(
      appBar: AppBar(title: const Text('Bearing capacity')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
        children: [
          const SectionHeader(
            title: 'ANALYSIS',
            subtitle: 'Drained uses c′ and φ′ for the long term. Undrained uses Cu with '
                'φ = 0 for the short term, which is what governs a clay loaded quickly.',
          ),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'drained', label: Text('Drained')),
              ButtonSegment(value: 'undrained', label: Text('Undrained')),
            ],
            selected: {_analysis},
            onSelectionChanged: (v) => setState(() => _analysis = v.first),
          ),
          const SizedBox(height: 22),
          const SectionHeader(title: 'SOIL'),
          TextField(
            controller: _unitWeight,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
                labelText: 'Unit weight', suffixText: 'kN/m³'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _cohesion,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: undrained ? 'Undrained shear strength Cu' : 'Cohesion c′',
              suffixText: 'kPa',
            ),
          ),
          if (!undrained) ...[
            const SizedBox(height: 10),
            TextField(
              controller: _friction,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration:
                  const InputDecoration(labelText: 'Friction angle φ′', suffixText: '°'),
            ),
          ],
          const SizedBox(height: 14),
          const Text('Where did these come from?',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            children: [
              for (final option in const [
                ('LABORATORY', 'Laboratory'),
                ('FIELD', 'Field'),
                ('ESTIMATED', 'Correlated'),
                ('USER', 'Entered'),
              ])
                ChoiceChip(
                  label: Text(option.$2, style: const TextStyle(fontSize: 12)),
                  selected: _source == option.$1,
                  onSelected: (_) => setState(() => _source = option.$1),
                ),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            'A correlated parameter keeps the result preliminary, and the report says so.',
            style: TextStyle(fontSize: 11.5, color: GeoTheme.inkSoft, height: 1.35),
          ),
          const SizedBox(height: 22),
          const SectionHeader(title: 'FOOTING'),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _width,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Width B', suffixText: 'm'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _depth,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Depth D', suffixText: 'm'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _shape,
            decoration: const InputDecoration(labelText: 'Shape'),
            items: const [
              DropdownMenuItem(value: 'square', child: Text('Square pad')),
              DropdownMenuItem(value: 'strip', child: Text('Strip footing')),
              DropdownMenuItem(value: 'circular', child: Text('Circular')),
              DropdownMenuItem(value: 'rectangular', child: Text('Rectangular')),
            ],
            onChanged: (v) => setState(() => _shape = v!),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _water,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Groundwater depth (optional)',
              suffixText: 'm',
              helperText: 'Water at founding level roughly halves the self-weight term.',
            ),
          ),
          const SizedBox(height: 22),
          const SectionHeader(
            title: 'METHOD',
            subtitle: 'Each author supplies every factor in the calculation. Methods are '
                'never mixed, and the one you pick is recorded with the result.',
          ),
          DropdownButtonFormField<String>(
            initialValue: _method,
            items: const [
              DropdownMenuItem(value: 'vesic', child: Text('Vesic (1973)')),
              DropdownMenuItem(value: 'hansen', child: Text('Brinch Hansen (1970)')),
              DropdownMenuItem(value: 'meyerhof', child: Text('Meyerhof (1963)')),
              DropdownMenuItem(value: 'terzaghi', child: Text('Terzaghi (1943)')),
            ],
            onChanged: (v) => setState(() => _method = v!),
          ),
          const SizedBox(height: 26),
          FilledButton(
            onPressed: _busy ? null : _run,
            child: _busy
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Text('Calculate'),
          ),
          if (_result != null) ...[
            const SizedBox(height: 24),
            _ResultCard(result: _result!),
          ],
        ],
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result});

  final CalculationResult result;

  @override
  Widget build(BuildContext context) {
    if (result.isRefusal) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.block_outlined, color: GeoTheme.critical, size: 20),
                  const SizedBox(width: 8),
                  Text('Not enough data',
                      style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: GeoTheme.critical.withValues(alpha: 0.95))),
                ],
              ),
              const SizedBox(height: 6),
              const Text(
                'The engine will not guess a missing soil parameter. This refusal is '
                'stored with the project, so the gap is on the record.',
                style: TextStyle(fontSize: 12.5, color: GeoTheme.inkSoft, height: 1.4),
              ),
              const SizedBox(height: 14),
              WarningList(warnings: result.warnings),
            ],
          ),
        ),
      );
    }

    final terms = (result.results['terms_kpa'] as Map?)?.cast<String, dynamic>();
    final factors = (result.results['bearing_factors'] as Map?)?.cast<String, dynamic>();
    final water = (result.results['water_table'] as Map?)?.cast<String, dynamic>();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Figure(
                    label: 'NET ALLOWABLE',
                    value: (result.netAllowableKpa ?? 0).toStringAsFixed(0),
                    unit: 'kPa',
                  ),
                ),
                Expanded(
                  child: Figure(
                    label: 'ULTIMATE',
                    value: (result.ultimateKpa ?? 0).toStringAsFixed(0),
                    unit: 'kPa',
                  ),
                ),
                Expanded(
                  child: Figure(
                    label: 'FACTOR OF SAFETY',
                    value: '${result.results['factor_of_safety'] ?? ''}',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 12),
            if (terms != null) ...[
              const Text('Where it comes from',
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              for (final entry in terms.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 3),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          switch (entry.key) {
                            'cohesion' => 'Cohesion term  c·Nc',
                            'surcharge' => 'Surcharge term  q·Nq',
                            _ => 'Self-weight term  ½γB·Nγ',
                          },
                          style: const TextStyle(fontSize: 12, color: GeoTheme.inkSoft),
                        ),
                      ),
                      Text('${entry.value} kPa',
                          style: GeoTheme.numeric.copyWith(fontSize: 12)),
                    ],
                  ),
                ),
              const SizedBox(height: 10),
            ],
            if (factors != null)
              Text(
                'Nc ${factors['Nc']}   Nq ${factors['Nq']}   Nγ ${factors['Ngamma']}'
                '   ·   ${factors['method']}',
                style: GeoTheme.numeric.copyWith(fontSize: 11.5, color: GeoTheme.inkSoft),
              ),
            if (water != null && water['explanation'] != null) ...[
              const SizedBox(height: 10),
              Text(water['explanation'] as String,
                  style: const TextStyle(
                      fontSize: 11.5, color: GeoTheme.info, height: 1.4)),
            ],
            if (result.warnings.isNotEmpty) ...[
              const SizedBox(height: 14),
              const Divider(height: 1),
              const SizedBox(height: 12),
              WarningList(warnings: result.warnings),
            ],
            const SizedBox(height: 8),
            Text(
              'Stored against this project · ${result.method} · engine '
              'v${result.engineVersion ?? ''}',
              style: const TextStyle(fontSize: 11, color: GeoTheme.inkSoft),
            ),
          ],
        ),
      ),
    );
  }
}
