import 'package:flutter/material.dart';

import '../main.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// One borehole: the strata logged in it, drawn as a profile.
class BoreholeScreen extends StatefulWidget {
  const BoreholeScreen({super.key, required this.project, required this.borehole});

  final Project project;
  final Borehole borehole;

  @override
  State<BoreholeScreen> createState() => _BoreholeScreenState();
}

class _BoreholeScreenState extends State<BoreholeScreen> {
  late Future<List<SoilLayer>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<SoilLayer>> _load() =>
      AppScope.of(context).api.layers(widget.project.id, widget.borehole.id);

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.borehole.code)),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addLayer,
        backgroundColor: GeoTheme.navy,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('Log a layer'),
      ),
      body: FutureBuilder<List<SoilLayer>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final layers = snapshot.data ?? [];
          if (layers.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: 40),
                child: Text(
                  'Nothing logged yet.\n\nRecord each stratum as you meet it: '
                  'from what depth to what depth, what it is, and how you know.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13, color: GeoTheme.inkSoft, height: 1.5),
                ),
              ),
            );
          }
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
            children: [
              const SectionHeader(
                title: 'SOIL PROFILE',
                subtitle: 'Depths run downward from ground level. Each layer shows where '
                    'its classification came from.',
              ),
              _Profile(layers: layers, waterDepth: widget.borehole.groundwaterDepthM),
            ],
          );
        },
      ),
    );
  }

  Future<void> _addLayer() async {
    final top = TextEditingController();
    final bottom = TextEditingController();
    final description = TextEditingController();
    final uscs = TextEditingController();
    var source = 'FIELD';

    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(
              16, 16, 16, MediaQuery.of(context).viewInsets.bottom + 16),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeader(
                  title: 'LOG A LAYER',
                  subtitle: 'Layers may not overlap — one stratum at each depth.',
                ),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: top,
                        autofocus: true,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(labelText: 'From (m)'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: TextField(
                        controller: bottom,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(labelText: 'To (m)'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: description,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(
                      labelText: 'Description', hintText: 'BLACK COTTON CLAY'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: uscs,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(
                      labelText: 'USCS class (optional)', hintText: 'CH'),
                ),
                const SizedBox(height: 14),
                const Text('How do you know?',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  children: [
                    for (final option in const [
                      ('FIELD', 'Field'),
                      ('LABORATORY', 'Laboratory'),
                      ('ENGINEER', 'Engineer'),
                      ('USER', 'Entered'),
                    ])
                      ChoiceChip(
                        label: Text(option.$2, style: const TextStyle(fontSize: 12)),
                        selected: source == option.$1,
                        onSelected: (_) => setSheetState(() => source = option.$1),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                const Text(
                  'This is stored with the layer and printed in the report. A value '
                  'that was measured and one that was assumed are not the same evidence.',
                  style: TextStyle(fontSize: 11.5, color: GeoTheme.inkSoft, height: 1.35),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('Add layer'),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    if (confirmed != true) return;
    final topValue = double.tryParse(top.text);
    final bottomValue = double.tryParse(bottom.text);
    if (topValue == null || bottomValue == null) return;
    if (!mounted) return;
    try {
      await AppScope.of(context).api.addLayer(widget.project.id, widget.borehole.id, {
        'top_depth_m': topValue,
        'bottom_depth_m': bottomValue,
        if (description.text.trim().isNotEmpty) 'description': description.text.trim(),
        if (uscs.text.trim().isNotEmpty) 'uscs_class': uscs.text.trim().toUpperCase(),
        'classification_source': source,
      });
      _reload();
    } on Object catch (error) {
      if (mounted) await showApiError(context, error);
    }
  }
}

/// The borehole log, drawn to scale.
class _Profile extends StatelessWidget {
  const _Profile({required this.layers, this.waterDepth});

  final List<SoilLayer> layers;
  final double? waterDepth;

  static const double _pixelsPerMetre = 44;
  static const double _minHeight = 40;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final layer in layers)
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(
                  width: 52,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text('${layer.topDepthM.toStringAsFixed(2)} m',
                          style: GeoTheme.numeric
                              .copyWith(fontSize: 11, color: GeoTheme.inkSoft)),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  width: 14,
                  constraints: BoxConstraints(
                    minHeight:
                        (layer.thicknessM * _pixelsPerMetre).clamp(_minHeight, 200),
                  ),
                  decoration: BoxDecoration(
                    color: _hatch(layer),
                    border: const Border(
                      top: BorderSide(color: GeoTheme.ink, width: 1),
                      left: BorderSide(color: GeoTheme.ink),
                      right: BorderSide(color: GeoTheme.ink),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          layer.description ?? layer.uscsClass ?? 'Unnamed stratum',
                          style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${layer.thicknessM.toStringAsFixed(2)} m thick'
                          '${layer.uscsClass != null ? '  ·  ${layer.uscsClass}' : ''}',
                          style: const TextStyle(fontSize: 11.5, color: GeoTheme.inkSoft),
                        ),
                        const SizedBox(height: 6),
                        ProvenanceChip(
                          source: layer.classificationSource,
                          confidence: layer.confidence,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        Padding(
          padding: const EdgeInsets.only(left: 52 + 8),
          child: Text('${layers.last.bottomDepthM.toStringAsFixed(2)} m',
              style: GeoTheme.numeric.copyWith(fontSize: 11, color: GeoTheme.inkSoft)),
        ),
        if (waterDepth != null) ...[
          const SizedBox(height: 18),
          Row(
            children: [
              const Icon(Icons.water_drop_outlined, size: 16, color: GeoTheme.info),
              const SizedBox(width: 6),
              Text('Groundwater at ${waterDepth!.toStringAsFixed(2)} m',
                  style: const TextStyle(fontSize: 12.5, color: GeoTheme.info)),
            ],
          ),
        ],
      ],
    );
  }

  /// A colour per broad soil family, so a profile reads at a glance.
  static Color _hatch(SoilLayer layer) {
    final key = (layer.uscsClass ?? layer.description ?? '').toUpperCase();
    if (key.startsWith('CH') || key.contains('BLACK COTTON')) {
      return const Color(0xFF4A4038);
    }
    if (key.startsWith('C') || key.contains('CLAY')) return const Color(0xFF8A6A4F);
    if (key.startsWith('M') || key.contains('SILT')) return const Color(0xFFB09878);
    if (key.startsWith('S') || key.contains('SAND')) return const Color(0xFFD9C08A);
    if (key.startsWith('G') || key.contains('GRAVEL')) return const Color(0xFFA9A9A0);
    if (key.contains('ROCK')) return const Color(0xFF6E7B85);
    if (key.contains('TOPSOIL')) return const Color(0xFF6B7B4A);
    return GeoTheme.line;
  }
}
