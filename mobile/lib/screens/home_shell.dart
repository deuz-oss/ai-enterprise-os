import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import 'attendance_tab.dart';
import 'contracts_tab.dart';
import 'dashboard_tab.dart';
import 'login_screen.dart';
import 'payroll_tab.dart';

class _TabSpec {
  _TabSpec(this.label, this.icon, this.allowedRoles, this.builder);
  final String label;
  final IconData icon;
  final Set<String> allowedRoles;
  final WidgetBuilder builder;
}

/// Kerangka utama: bottom navigation yang disaring sesuai role pengguna.
/// Admin melewati semua pembatasan role di backend, jadi lihat semua tab.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  List<_TabSpec> get _tabs {
    const all = {'admin', 'operations', 'hr', 'finance', 'management', 'business_dev', 'recruiter'};
    return [
      _TabSpec('Beranda', Icons.dashboard_outlined, all, (_) => const DashboardTab()),
      _TabSpec(
        'Absensi',
        Icons.fact_check_outlined,
        {'admin', 'operations', 'management'},
        (_) => const AttendanceTab(),
      ),
      _TabSpec(
        'Payrol',
        Icons.payments_outlined,
        {'admin', 'operations', 'finance', 'management'},
        (_) => const PayrollTab(),
      ),
      _TabSpec(
        'Kontrak',
        Icons.history_edu_outlined,
        {'admin', 'hr', 'management'},
        (_) => const ContractsTab(),
      ),
    ];
  }

  Future<void> _logout() async {
    await ApiClient.instance.clearSession();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  void _showProfileSheet() {
    final user = ApiClient.instance.user ?? <String, dynamic>{};
    final account = UserAccount.fromMap(user);
    showModalBottomSheet<void>(
      context: context,
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(account.fullName, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 4),
              Text('${account.email} · role: ${account.role}'),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                icon: const Icon(Icons.logout),
                label: const Text('Keluar'),
                onPressed: () {
                  Navigator.of(context).pop();
                  _logout();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tabs = _tabs;
    if (_index >= tabs.length) _index = 0;
    final user = ApiClient.instance.user ?? <String, dynamic>{};

    return Scaffold(
      appBar: AppBar(
        title: Text((user['full_name'] as String?) ?? 'AEOS'),
        actions: [
          IconButton(icon: const Icon(Icons.account_circle_outlined), onPressed: _showProfileSheet),
        ],
      ),
      body: Builder(builder: (context) => tabs[_index].builder(context)),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [
          for (final t in tabs) NavigationDestination(icon: Icon(t.icon), label: t.label),
        ],
      ),
    );
  }
}
