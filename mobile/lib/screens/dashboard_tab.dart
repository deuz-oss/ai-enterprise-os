import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../models/models.dart';

/// Beranda: angka ringkasan dari GET /overview.
class DashboardTab extends StatefulWidget {
  const DashboardTab({super.key});

  @override
  State<DashboardTab> createState() => _DashboardTabState();
}

class _DashboardTabState extends State<DashboardTab> {
  late Future<OverviewStats> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<OverviewStats> _load() async {
    final data = await ApiClient.instance.get('/overview') as Map<String, dynamic>;
    return OverviewStats.fromMap(data);
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async {
        setState(() => _future = _load());
        await _future;
      },
      child: FutureBuilder<OverviewStats>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return ListView(children: [
              Padding(
                padding: const EdgeInsets.all(24),
                child: Text('Gagal memuat: ${snapshot.error}'),
              ),
            ]);
          }
          final s = snapshot.data!;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text('Ringkasan', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.6,
                children: [
                  _StatCard(icon: Icons.person_search_outlined, label: 'Lead', value: s.leadsTotal),
                  _StatCard(icon: Icons.emoji_events_outlined, label: 'Lead Menang', value: s.leadsWon),
                  _StatCard(icon: Icons.business_outlined, label: 'Klien', value: s.clients),
                  _StatCard(icon: Icons.work_outline, label: 'Job Order Terbuka', value: s.jobOrdersOpen),
                  _StatCard(icon: Icons.group_outlined, label: 'Kandidat', value: s.candidatesTotal),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 22, color: scheme.primary),
            const Spacer(),
            Text('$value', style: Theme.of(context).textTheme.headlineMedium),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}
