import 'package:flutter/material.dart';

import '../main.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';
import 'bearing_capacity_screen.dart';
import 'borehole_screen.dart';
import 'candidates_screen.dart';

/// One site: its ground record, its calculation history, its foundation options.
class ProjectScreen extends StatefulWidget {
  const ProjectScreen({super.key, required this.project});

  final Project project;

  @override
  State<ProjectScreen> createState() => _ProjectScreenState();
}

class _ProjectScreenState extends State<ProjectScreen> {
  int _tab = 0;
  int _reloadToken = 0;

  void _reload() => setState(() => _reloadToken++);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.project.name, overflow: TextOverflow.ellipsis),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(30),
          child: Padding(
            padding: const EdgeInsets.only(left: 16, bottom: 10),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                [
                  widget.project.location,
                  widget.project.designStandard.toUpperCase(),
                ].where((p) => p.isNotEmpty).join('  ·  '),
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ),
          ),
        ),
      ),
      body: Column(
        children: [
          const PreliminaryBanner(),
          Expanded(
            child: IndexedStack(
              index: _tab,
              children: [
                _GroundTab(project: widget.project, key: ValueKey('ground$_reloadToken')),
                _CalculationsTab(
                    project: widget.project, key: ValueKey('calc$_reloadToken')),
                _ReportsTab(project: widget.project, key: ValueKey('report$_reloadToken')),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (index) => setState(() => _tab = index),
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.layers_outlined), label: 'Ground'),
          NavigationDestination(
              icon: Icon(Icons.calculate_outlined), label: 'Calculations'),
          NavigationDestination(
              icon: Icon(Icons.description_outlined), label: 'Report'),
        ],
      ),
      floatingActionButton: _tab == 0
          ? FloatingActionButton.extended(
              onPressed: () => _addBorehole(context),
              backgroundColor: GeoTheme.navy,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.add),
              label: const Text('Borehole'),
            )
          : null,
    );
  }

  Future<void> _addBorehole(BuildContext context) async {
    final code = TextEditingController();
    final depth = TextEditingController();
    final water = TextEditingController();
    var observed = false;

    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.fromLTRB(
              16, 16, 16, MediaQuery.of(context).viewInsets.bottom + 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionHeader(
                title: 'NEW BOREHOLE',
                subtitle: 'A location on site. Its code has to be unique in this project.',
              ),
              TextField(
                controller: code,
                autofocus: true,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(labelText: 'Code', hintText: 'BH-01'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: depth,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Total depth (m)'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: water,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Groundwater depth (m)'),
              ),
              CheckboxListTile(
                value: observed,
                onChanged: (v) => setSheetState(() => observed = v ?? false),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                title: const Text('Water level was observed', style: TextStyle(fontSize: 13.5)),
                subtitle: const Text(
                  'Observed and estimated are different facts, and the report says which.',
                  style: TextStyle(fontSize: 11.5, height: 1.3),
                ),
              ),
              const SizedBox(height: 10),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Add borehole'),
              ),
            ],
          ),
        ),
      ),
    );

    if (confirmed != true || code.text.trim().isEmpty) return;
    if (!context.mounted) return;
    try {
      await AppScope.of(context).api.createBorehole(widget.project.id, {
        'code': code.text.trim(),
        if (double.tryParse(depth.text) != null) 'total_depth_m': double.parse(depth.text),
        if (double.tryParse(water.text) != null)
          'groundwater_depth_m': double.parse(water.text),
        'groundwater_observed': observed,
      });
      _reload();
    } on Object catch (error) {
      if (context.mounted) await showApiError(context, error);
    }
  }
}

class _GroundTab extends StatelessWidget {
  const _GroundTab({super.key, required this.project});

  final Project project;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Borehole>>(
      future: AppScope.of(context).api.boreholes(project.id),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return _Message(text: '${snapshot.error}');
        }
        final boreholes = snapshot.data ?? [];
        if (boreholes.isEmpty) {
          return const _Message(
            text: 'No boreholes yet.\n\n'
                'Everything this app calculates rests on what is actually in the '
                'ground. Add a borehole or trial pit and log what you found in it.',
          );
        }
        return ListView.separated(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
          itemCount: boreholes.length,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (context, index) {
            final borehole = boreholes[index];
            return Card(
              child: ListTile(
                title: Text(borehole.code,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(
                  [
                    if (borehole.totalDepthM != null)
                      '${borehole.totalDepthM!.toStringAsFixed(1)} m deep',
                    if (borehole.groundwaterDepthM != null)
                      'water at ${borehole.groundwaterDepthM!.toStringAsFixed(1)} m'
                          '${borehole.groundwaterObserved ? '' : ' (estimated)'}',
                  ].join(' · '),
                  style: const TextStyle(fontSize: 12.5),
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => BoreholeScreen(project: project, borehole: borehole),
                )),
              ),
            );
          },
        );
      },
    );
  }
}

class _CalculationsTab extends StatefulWidget {
  const _CalculationsTab({super.key, required this.project});

  final Project project;

  @override
  State<_CalculationsTab> createState() => _CalculationsTabState();
}

class _CalculationsTabState extends State<_CalculationsTab> {
  late Future<List<CalculationResult>> _future;

  @override
  void initState() {
    super.initState();
    _future = AppScope.of(context).api.calculations(widget.project.id);
  }

  void _reload() =>
      setState(() => _future = AppScope.of(context).api.calculations(widget.project.id));

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () async {
                    await Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => BearingCapacityScreen(project: widget.project),
                    ));
                    if (mounted) _reload();
                  },
                  icon: const Icon(Icons.speed_outlined, size: 18),
                  label: const Text('Bearing capacity'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () async {
                    await Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => CandidatesScreen(project: widget.project),
                    ));
                    if (mounted) _reload();
                  },
                  icon: const Icon(Icons.foundation_outlined, size: 18),
                  label: const Text('Foundations'),
                ),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: FutureBuilder<List<CalculationResult>>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              final calculations = snapshot.data ?? [];
              if (calculations.isEmpty) {
                return const _Message(
                  text: 'No calculations yet.\n\n'
                      'Every run is kept — including the ones that come back saying '
                      'what data is missing. Re-running never replaces an earlier result.',
                );
              }
              return ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: calculations.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, index) =>
                    _CalculationCard(calculation: calculations[index]),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _CalculationCard extends StatelessWidget {
  const _CalculationCard({required this.calculation});

  final CalculationResult calculation;

  @override
  Widget build(BuildContext context) {
    final refused = calculation.isRefusal;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    calculation.calculationType.replaceAll('_', ' '),
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: (refused ? GeoTheme.critical : GeoTheme.pass)
                        .withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    refused ? 'Insufficient data' : 'Calculated',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: refused ? GeoTheme.critical : GeoTheme.pass,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '${calculation.method} · ${calculation.standard ?? ''} · engine '
              'v${calculation.engineVersion ?? ''}',
              style: const TextStyle(fontSize: 11.5, color: GeoTheme.inkSoft),
            ),
            if (!refused && calculation.netAllowableKpa != null) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: Figure(
                      label: 'NET ALLOWABLE',
                      value: calculation.netAllowableKpa!.toStringAsFixed(0),
                      unit: 'kPa',
                    ),
                  ),
                  if (calculation.ultimateKpa != null)
                    Expanded(
                      child: Figure(
                        label: 'ULTIMATE',
                        value: calculation.ultimateKpa!.toStringAsFixed(0),
                        unit: 'kPa',
                      ),
                    ),
                ],
              ),
            ],
            if (calculation.warnings.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Divider(height: 1),
              const SizedBox(height: 10),
              WarningList(warnings: calculation.warnings),
            ],
          ],
        ),
      ),
    );
  }
}

class _ReportsTab extends StatefulWidget {
  const _ReportsTab({super.key, required this.project});

  final Project project;

  @override
  State<_ReportsTab> createState() => _ReportsTabState();
}

class _ReportsTabState extends State<_ReportsTab> {
  late Future<List<Map<String, dynamic>>> _future;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _future = AppScope.of(context).api.reports(widget.project.id);
  }

  Future<void> _generate() async {
    setState(() => _busy = true);
    try {
      await AppScope.of(context).api.generateReport(widget.project.id);
      if (mounted) {
        setState(() => _future = AppScope.of(context).api.reports(widget.project.id));
      }
    } on Object catch (error) {
      if (mounted) await showApiError(context, error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: FilledButton.icon(
            onPressed: _busy ? null : _generate,
            icon: const Icon(Icons.post_add_outlined, size: 18),
            label: Text(_busy ? 'Assembling…' : 'Issue a report'),
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: _future,
            builder: (context, snapshot) {
              final reports = snapshot.data ?? [];
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (reports.isEmpty) {
                return const _Message(
                  text: 'No reports issued yet.\n\n'
                      'A report gathers everything stored on this project — the ground '
                      'record, the calculations, the foundation candidates and every '
                      'warning raised — into one document. Issuing again creates a new '
                      'revision rather than replacing the last one.',
                );
              }
              return ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: reports.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, index) {
                  final report = reports[index];
                  final banner = report['banner'] as String? ?? '';
                  final approved = !banner.contains('PRELIMINARY');
                  return Card(
                    child: ListTile(
                      leading: Icon(
                        approved ? Icons.verified_outlined : Icons.description_outlined,
                        color: approved ? GeoTheme.pass : GeoTheme.warning,
                      ),
                      title: Text('Revision ${report['revision']}',
                          style: const TextStyle(fontWeight: FontWeight.w700)),
                      subtitle: Text(banner,
                          style: const TextStyle(fontSize: 11.5, height: 1.3)),
                    ),
                  );
                },
              );
            },
          ),
        ),
      ],
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 40),
          child: Text(
            text,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 13, color: GeoTheme.inkSoft, height: 1.5),
          ),
        ),
      );
}
