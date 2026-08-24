import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../models/models.dart';

/// Reminder kontrak yang segera berakhir (GET /employees/contracts/expiring).
class ContractsTab extends StatefulWidget {
  const ContractsTab({super.key});

  @override
  State<ContractsTab> createState() => _ContractsTabState();
}

class _ContractsTabState extends State<ContractsTab> {
  static const _windowOptions = [30, 60, 90];
  int _withinDays = 60;
  late Future<List<ExpiringContract>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<ExpiringContract>> _load() async {
    final data = await ApiClient.instance
        .get('/employees/contracts/expiring', {'within_days': '$_withinDays'}) as List<dynamic>;
    return [for (final row in data) ExpiringContract.fromMap(row as Map<String, dynamic>)];
  }

  Color _daysColor(int days) {
    if (days <= 14) return Colors.red;
    if (days <= 45) return Colors.orange;
    return Colors.amber.shade700;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: DropdownButtonFormField<int>(
            value: _withinDays,
            decoration: const InputDecoration(labelText: 'Rentang peringatan'),
            items: [
              for (final d in _windowOptions)
                DropdownMenuItem(value: d, child: Text('≤ $d hari')),
            ],
            onChanged: (v) => setState(() {
              _withinDays = v!;
              _future = _load();
            }),
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () async {
              setState(() => _future = _load());
              await _future;
            },
            child: FutureBuilder<List<ExpiringContract>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return ListView(children: [
                    Padding(
                        padding: const EdgeInsets.all(24),
                        child: Text('Gagal memuat: ${snapshot.error}')),
                  ]);
                }
                final rows = snapshot.data ?? [];
                if (rows.isEmpty) {
                  return ListView(children: const [
                    Padding(
                      padding: EdgeInsets.all(24),
                      child: Center(child: Text('Tidak ada kontrak mendekati akhir.')),
                    ),
                  ]);
                }
                return ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: rows.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final c = rows[i];
                    return Card(
                      elevation: 0,
                      margin: EdgeInsets.zero,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      child: ListTile(
                        title: Text(c.employeeName),
                        subtitle: Text('${c.contractNo} · berakhir ${c.endDate}'),
                        trailing: Badge(
                          backgroundColor: _daysColor(c.daysLeft),
                          label: Text('${c.daysLeft} hr'),
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}
