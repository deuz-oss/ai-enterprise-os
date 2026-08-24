import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../models/models.dart';

/// Daftar run payrol + slip gaji per run (read-only di mobile).
class PayrollTab extends StatefulWidget {
  const PayrollTab({super.key});

  @override
  State<PayrollTab> createState() => _PayrollTabState();
}

class _PayrollTabState extends State<PayrollTab> {
  late Future<List<PayrollRunRow>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<PayrollRunRow>> _load() async {
    final data = await ApiClient.instance.get('/payroll/runs') as List<dynamic>;
    return [for (final row in data) PayrollRunRow.fromMap(row as Map<String, dynamic>)];
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async {
        setState(() => _future = _load());
        await _future;
      },
      child: FutureBuilder<List<PayrollRunRow>>(
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
          final runs = snapshot.data ?? [];
          if (runs.isEmpty) {
            return ListView(children: const [
              Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: Text('Belum ada run payrol.')),
              ),
            ]);
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: runs.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (context, i) {
              final r = runs[i];
              return Card(
                elevation: 0,
                margin: EdgeInsets.zero,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                child: ListTile(
                  leading: Icon(
                    r.isFinal ? Icons.lock_outline : Icons.edit_note_outlined,
                    color: r.isFinal ? Colors.green : Colors.orange,
                  ),
                  title: Text('${r.year}-${r.month.toString().padLeft(2, '0')}'),
                  subtitle: Text(r.isFinal ? 'Final' : 'Draft'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => _SlipsScreen(run: r),
                  )),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _SlipsScreen extends StatefulWidget {
  const _SlipsScreen({required this.run});
  final PayrollRunRow run;

  @override
  State<_SlipsScreen> createState() => _SlipsScreenState();
}

class _SlipsScreenState extends State<_SlipsScreen> {
  late Future<List<PayslipRow>> _slips;
  Map<String, String> _names = {};

  String get _period =>
      '${widget.run.year}-${widget.run.month.toString().padLeft(2, '0')}';

  @override
  void initState() {
    super.initState();
    _slips = _load();
    _loadNames();
  }

  Future<List<PayslipRow>> _load() async {
    final data =
        await ApiClient.instance.get('/payroll/runs/${widget.run.id}/slips') as List<dynamic>;
    return [for (final row in data) PayslipRow.fromMap(row as Map<String, dynamic>)];
  }

  Future<void> _loadNames() async {
    try {
      final data = await ApiClient.instance.get('/employees') as List<dynamic>;
      setState(() {
        _names = {
          for (final e in data)
            (e as Map<String, dynamic>)['id'] as String: (e['full_name'] ?? '-') as String,
        };
      });
    } on ApiException {
      // Nama tetap fallback ke ID bila gagal dimuat.
    }
  }

  String _rupiah(num value) {
    final s = value.round().toString();
    final buf = StringBuffer();
    for (var i = 0; i < s.length; i++) {
      buf.write(s[i]);
      final sisa = s.length - i - 1;
      if (sisa > 0 && sisa % 3 == 0) buf.write('.');
    }
    return 'Rp$buf';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Slip Gaji $_period')),
      body: FutureBuilder<List<PayslipRow>>(
        future: _slips,
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
          final slips = snapshot.data ?? [];
          if (slips.isEmpty) {
            return const Center(child: Text('Belum ada slip untuk run ini.'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: slips.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (context, i) {
              final s = slips[i];
              return Card(
                elevation: 0,
                margin: EdgeInsets.zero,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _names[s.employeeId] ?? s.employeeId,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 6),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('Bruto: ${_rupiah(s.gross)}'),
                          if (s.overtimeAmount > 0)
                            Text('Lembur: ${_rupiah(s.overtimeAmount)}'),
                        ],
                      ),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('PPh21: -${_rupiah(s.taxPph21)}',
                              style: const TextStyle(color: Colors.red)),
                          Text(
                            'Diterima: ${_rupiah(s.netPay)}',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
