import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../models/models.dart';

/// Approval absensi & lembur oleh klien — versi mobile.
class AttendanceTab extends StatefulWidget {
  const AttendanceTab({super.key});

  @override
  State<AttendanceTab> createState() => _AttendanceTabState();
}

class _AttendanceTabState extends State<AttendanceTab> {
  final List<int> _months = List.generate(12, (i) => i + 1);
  late int _year = DateTime.now().year;
  late int _month = DateTime.now().month;
  late Future<List<AttendanceRow>> _future;
  String? _employeeNamesError;

  // Cache nama karyawan: employee_id → full_name
  Map<String, String> _names = {};

  @override
  void initState() {
    super.initState();
    _future = _load();
    _loadNames();
  }

  Future<List<AttendanceRow>> _load() async {
    final data = await ApiClient.instance
        .get('/payroll/attendance', {'year': '$_year', 'month': '$_month'}) as List<dynamic>;
    return [for (final row in data) AttendanceRow.fromMap(row as Map<String, dynamic>)];
  }

  Future<void> _loadNames() async {
    try {
      final data = await ApiClient.instance.get('/employees') as List<dynamic>;
      setState(() {
        _names = {
          for (final e in data)
            (e as Map<String, dynamic>)['id'] as String:
                (e['full_name'] ?? '-') as String,
        };
        _employeeNamesError = null;
      });
    } on ApiException catch (e) {
      setState(() => _employeeNamesError = e.message);
    }
  }

  Future<void> _setApproval(AttendanceRow row, bool approved) async {
    try {
      await ApiClient.instance.patch(
        '/payroll/attendance/${row.id}/client-approval?approved=$approved',
        {},
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(approved ? 'Absensi disetujui' : 'Persetujuan dibatalkan')),
      );
      setState(() => _future = _load());
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Gagal: ${e.message}')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<int>(
                  value: _month,
                  decoration: const InputDecoration(labelText: 'Bulan'),
                  items: [
                    for (final m in _months)
                      DropdownMenuItem(value: m, child: Text('$m')),
                  ],
                  onChanged: (v) => setState(() {
                    _month = v!;
                    _future = _load();
                  }),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: DropdownButtonFormField<int>(
                  value: _year,
                  decoration: const InputDecoration(labelText: 'Tahun'),
                  items: [
                    for (final y in [_year - 1, _year, _year + 1])
                      DropdownMenuItem(value: y, child: Text('$y')),
                  ],
                  onChanged: (v) => setState(() {
                    _year = v!;
                    _future = _load();
                  }),
                ),
              ),
            ],
          ),
        ),
        if (_employeeNamesError != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text('Nama karyawan gagal dimuat ($_employeeNamesError)',
                style: Theme.of(context).textTheme.bodySmall),
          ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () async {
              await _loadNames();
              setState(() => _future = _load());
              await _future;
            },
            child: FutureBuilder<List<AttendanceRow>>(
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
                      child: Center(child: Text('Belum ada rekap absensi periode ini.')),
                    ),
                  ]);
                }
                return ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: rows.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final r = rows[i];
                    return Card(
                      elevation: 0,
                      margin: EdgeInsets.zero,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      child: ListTile(
                        title: Text(_names[r.employeeId] ?? r.employeeId),
                        subtitle: Text('Hadir ${r.presentDays} hari · Lembur ${r.overtimeHours} jam'),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              r.clientApproved ? Icons.check_circle : Icons.pending,
                              color: r.clientApproved ? Colors.green : Colors.orange,
                              size: 20,
                            ),
                            Switch(
                              value: r.clientApproved,
                              onChanged: (v) => _setApproval(r, v),
                            ),
                          ],
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
