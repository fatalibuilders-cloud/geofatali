import 'package:flutter/material.dart';

import '../main.dart';
import '../models/models.dart';
import '../theme.dart';
import 'new_project_screen.dart';
import 'project_screen.dart';
import 'settings_screen.dart';

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({super.key});

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  late Future<List<Project>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<Project>> _load() => AppScope.of(context).api.projects();

  void _refresh() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final account = AppScope.of(context).account;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Projects'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () async {
              await Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const SettingsScreen(),
              ));
              if (mounted) _refresh();
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final created = await Navigator.of(context).push<bool>(
            MaterialPageRoute(builder: (_) => const NewProjectScreen()),
          );
          if (created == true) _refresh();
        },
        backgroundColor: GeoTheme.navy,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('New project'),
      ),
      body: RefreshIndicator(
        onRefresh: () async => _refresh(),
        child: FutureBuilder<List<Project>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return _ErrorState(error: snapshot.error!, onRetry: _refresh);
            }
            final projects = snapshot.data ?? [];
            if (projects.isEmpty) {
              return ListView(
                children: [
                  const SizedBox(height: 80),
                  Icon(Icons.layers_outlined, size: 48, color: GeoTheme.line),
                  const SizedBox(height: 16),
                  const Center(
                    child: Text('No projects yet',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  ),
                  const SizedBox(height: 8),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 48),
                    child: Text(
                      'A project holds one site: its boreholes, the soil logged in '
                      'them, the calculations run on it and the reports issued.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 13, color: GeoTheme.inkSoft, height: 1.4),
                    ),
                  ),
                ],
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
              itemCount: projects.length + 1,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                if (index == projects.length) {
                  return Padding(
                    padding: const EdgeInsets.only(top: 16),
                    child: Text(
                      'Signed in as ${account?.email ?? ''}'
                      '${account != null && account.canApprove ? ' · engineer' : ''}',
                      style: const TextStyle(fontSize: 11.5, color: GeoTheme.inkSoft),
                      textAlign: TextAlign.center,
                    ),
                  );
                }
                return _ProjectCard(
                  project: projects[index],
                  onOpen: () async {
                    await Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => ProjectScreen(project: projects[index]),
                    ));
                    if (mounted) _refresh();
                  },
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({required this.project, required this.onOpen});

  final Project project;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onOpen,
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(project.name,
                        style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700)),
                  ),
                  const Icon(Icons.chevron_right, color: GeoTheme.inkSoft),
                ],
              ),
              if (project.location.isNotEmpty) ...[
                const SizedBox(height: 3),
                Text(project.location,
                    style: const TextStyle(fontSize: 12.5, color: GeoTheme.inkSoft)),
              ],
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  _Tag(text: _sectorLabel(project.sector)),
                  _Tag(text: project.designStandard.toUpperCase()),
                  if (project.floors != null) _Tag(text: '${project.floors} storeys'),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _sectorLabel(String id) =>
      id.replaceAll('_', ' ').replaceFirstMapped(
          RegExp(r'^\w'), (m) => m.group(0)!.toUpperCase());
}

class _Tag extends StatelessWidget {
  const _Tag({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: GeoTheme.surface,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: GeoTheme.line),
        ),
        child: Text(text,
            style: const TextStyle(fontSize: 11, color: GeoTheme.inkSoft, fontWeight: FontWeight.w600)),
      );
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final message = error is ApiException ? (error as ApiException).message : '$error';
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 60),
        const Icon(Icons.cloud_off_outlined, size: 44, color: GeoTheme.inkSoft),
        const SizedBox(height: 16),
        Text(message,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 13.5, height: 1.45)),
        const SizedBox(height: 20),
        Center(
          child: OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text('Try again'),
          ),
        ),
      ],
    );
  }
}
