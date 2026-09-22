import 'package:flutter/material.dart';

import '../main.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Create a project.
///
/// The sector is the most consequential field on this form and is presented
/// that way: choosing it changes which checks govern the site, which
/// foundations are even candidates, and what an adequate investigation has to
/// include. The list comes from the server so the app and the engine can never
/// disagree about what a valid sector is.
class NewProjectScreen extends StatefulWidget {
  const NewProjectScreen({super.key});

  @override
  State<NewProjectScreen> createState() => _NewProjectScreenState();
}

class _NewProjectScreenState extends State<NewProjectScreen> {
  final _name = TextEditingController();
  final _client = TextEditingController();
  final _country = TextEditingController();
  final _area = TextEditingController();
  final _floors = TextEditingController();

  late Future<(List<Sector>, List<Map<String, dynamic>>)> _reference;
  String? _sector;
  String? _standard;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _reference = _loadReference();
  }

  Future<(List<Sector>, List<Map<String, dynamic>>)> _loadReference() async {
    final api = AppScope.of(context).api;
    final sectors = await api.sectors();
    final standards = await api.standards();
    return (sectors, standards);
  }

  @override
  void dispose() {
    _name.dispose();
    _client.dispose();
    _country.dispose();
    _area.dispose();
    _floors.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    if (_name.text.trim().isEmpty || _sector == null || _standard == null) return;
    setState(() => _busy = true);
    try {
      await AppScope.of(context).api.createProject({
        'name': _name.text.trim(),
        'sector': _sector,
        'design_standard': _standard,
        if (_client.text.trim().isNotEmpty) 'client_name': _client.text.trim(),
        if (_country.text.trim().isNotEmpty) 'country': _country.text.trim(),
        if (_area.text.trim().isNotEmpty) 'administrative_area': _area.text.trim(),
        if (int.tryParse(_floors.text) != null) 'floors': int.parse(_floors.text),
      });
      if (mounted) Navigator.of(context).pop(true);
    } on Object catch (error) {
      if (mounted) await showApiError(context, error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New project')),
      body: FutureBuilder<(List<Sector>, List<Map<String, dynamic>>)>(
        future: _reference,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Padding(
              padding: const EdgeInsets.all(24),
              child: Text(
                snapshot.error is ApiException
                    ? (snapshot.error! as ApiException).message
                    : '${snapshot.error}',
                style: const TextStyle(height: 1.45),
              ),
            );
          }
          final (sectors, standards) = snapshot.data!;
          _sector ??= sectors.first.id;
          _standard ??= standards.first['id'] as String;
          final selected = sectors.firstWhere((s) => s.id == _sector);

          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
            children: [
              TextField(
                controller: _name,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(labelText: 'Project name'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _client,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(labelText: 'Client (optional)'),
              ),
              const SizedBox(height: 22),
              const SectionHeader(
                title: 'WHAT ARE YOU BUILDING?',
                subtitle:
                    'This decides which checks govern the site and which foundations '
                    'are candidates. A road is judged on subgrade strength; a dam on '
                    'seepage; a tower on uplift.',
              ),
              DropdownButtonFormField<String>(
                initialValue: _sector,
                isExpanded: true,
                items: [
                  for (final s in sectors)
                    DropdownMenuItem(value: s.id, child: Text(s.label, overflow: TextOverflow.ellipsis)),
                ],
                onChanged: (value) => setState(() => _sector = value),
              ),
              const SizedBox(height: 10),
              _SectorSummary(sector: selected),
              const SizedBox(height: 22),
              const SectionHeader(
                title: 'DESIGN STANDARD',
                subtitle: 'Sets the factors of safety, load combinations and settlement limits.',
              ),
              DropdownButtonFormField<String>(
                initialValue: _standard,
                isExpanded: true,
                items: [
                  for (final s in standards)
                    DropdownMenuItem(
                      value: s['id'] as String,
                      child: Text(s['name'] as String, overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: (value) => setState(() => _standard = value),
              ),
              const SizedBox(height: 22),
              const SectionHeader(title: 'SITE'),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _country,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(labelText: 'Country'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: TextField(
                      controller: _area,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(labelText: 'County / area'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _floors,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Storeys (optional)'),
              ),
              const SizedBox(height: 26),
              FilledButton(
                onPressed: _busy ? null : _create,
                child: _busy
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Create project'),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _SectorSummary extends StatelessWidget {
  const _SectorSummary({required this.sector});

  final Sector sector;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: GeoTheme.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(sector.summary,
              style: const TextStyle(fontSize: 12.5, height: 1.4, color: GeoTheme.inkSoft)),
          if (sector.governingChecks.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text('What governs it',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.3)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final check in sector.governingChecks)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: GeoTheme.navy.withValues(alpha: 0.06),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(check.label,
                        style: const TextStyle(fontSize: 11, color: GeoTheme.navy)),
                  ),
              ],
            ),
          ],
          if (sector.note != null) ...[
            const SizedBox(height: 10),
            Text(sector.note!,
                style: const TextStyle(
                    fontSize: 11.5, height: 1.4, color: GeoTheme.clay, fontStyle: FontStyle.italic)),
          ],
        ],
      ),
    );
  }
}
