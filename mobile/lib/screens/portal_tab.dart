import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import 'self_attendance_screen.dart';

/// Portal self-service karyawan: profil, jatah cuti, slip gaji,
/// pengajuan cuti/izin, dan notifikasi — konsumsi endpoint /me/*.
class PortalTab extends StatefulWidget {
  const PortalTab({super.key});

  @override
  State<PortalTab> createState() => _PortalTabState();
}

class _PortalTabState extends State<PortalTab> {
  late Future<List<dynamic>> _future;
  final List<String> _leaveTypes = const [
    'cuti_tahunan',
    'izin',
    'sakit',
    'cuti_tak_berbayar',
  ];
  String _selectedType = 'cuti_tahunan';
  DateTime _startDate = DateTime.now();
  DateTime _endDate = DateTime.now().add(const Duration(days: 1));
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _future = _loadAll();
  }

  /// [profil, balance, slips, leaves, notifications] — diparalel.
  Future<List<dynamic>> _loadAll() async {
    final results = await Future.wait<dynamic>([
      ApiClient.instance.get('/me/profile'),
      ApiClient.instance.get('/me/leave-balance'),
      ApiClient.instance.get('/me/payslips'),
      ApiClient.instance.get('/me/leave-requests'),
      ApiClient.instance.get('/me/notifications'),
    ]);
    return results;
  }

  Future<void> _reload() async {
    setState(() => _future = _loadAll());
    await _future;
  }

  String get _typeLabel => switch (_selectedType) {
        'cuti_tahunan' => 'Cuti Tahunan',
        'izin' => 'Izin',
        'sakit' => 'Sakit',
        _ => 'Cuti Tak Berbayar',
      };

  Future<void> _pickDate({required bool isStart}) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: isStart ? _startDate : _endDate,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked == null) return;
    setState(() {
      if (isStart) {
        _startDate = picked;
        if (_endDate.isBefore(picked)) _endDate = picked.add(const Duration(days: 1));
      } else {
        _endDate = picked;
      }
    });
  }

  Future<void> _submitLeave() async {
    setState(() => _submitting = true);
    try {
      await ApiClient.instance.post('/me/leave-requests', {
        'leave_type': _selectedType,
        'start_date': _startDate.toIso8601String().substring(0, 10),
        'end_date': _endDate.toIso8601String().substring(0, 10),
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Pengajuan terkirim, menunggu keputusan HR')),
      );
      await _reload();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Gagal: ${e.message}')));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _cancelLeave(MyLeaveRequest leave) async {
    try {
      await ApiClient.instance.post('/me/leave-requests/${leave.id}/cancel');
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Pengajuan dibatalkan')));
      await _reload();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Gagal: ${e.message}')));
    }
  }

  Future<void> _markRead(AppNotification n) async {
    try {
      await ApiClient.instance.post('/me/notifications/${n.id}/read');
      await _reload();
    } on ApiException catch (_) {
      // diam: penandaan dibaca tidak kritikal
    }
  }

  String _rupiah(num value) {
    final s = value.round().toString().replaceAllMapped(
          RegExp(r'(\d)(?=(\d{3})+(?!\d))'),
          (m) => '${m[1]}.',
        );
    return 'Rp$s';
  }

  String _monthName(int month) => const [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
      ][month - 1];

  Color _statusColor(String status) => switch (status) {
        'disetujui' => Colors.green,
        'ditolak' => Colors.red,
        'dibatalkan' => Colors.grey,
        _ => Colors.orange,
      };

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _reload,
      child: FutureBuilder<List<dynamic>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return ListView(children: [
              Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  'Gagal memuat portal: ${snapshot.error}\n\n'
                  'Pastikan akun Anda sudah ditautkan ke data karyawan oleh HR.',
                ),
              ),
            ]);
          }
          final data = snapshot.data!;
          final profile = PortalProfile.fromMap(data[0] as Map<String, dynamic>);
          final balance = data[1] == null
              ? null
              : LeaveBalanceInfo.fromMap(data[1] as Map<String, dynamic>);
          final slips = [
            for (final row in data[2] as List<dynamic>)
              MyPayslip.fromMap(row as Map<String, dynamic>)
          ];
          final leaves = [
            for (final row in data[3] as List<dynamic>)
              MyLeaveRequest.fromMap(row as Map<String, dynamic>)
          ];
          final notifications = [
            for (final row in data[4] as List<dynamic>)
              AppNotification.fromMap(row as Map<String, dynamic>)
          ];

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _profileCard(profile),
              const SizedBox(height: 12),
              _selfAttendanceCard(),
              const SizedBox(height: 12),
              _balanceCard(balance),
              const SizedBox(height: 12),
              _requestLeaveCard(),
              const SizedBox(height: 12),
              _leavesCard(leaves),
              const SizedBox(height: 12),
              _payslipsCard(slips),
              const SizedBox(height: 12),
              _notificationsCard(notifications),
            ],
          );
        },
      ),
    );
  }

  Widget _profileCard(PortalProfile profile) => Card(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(profile.fullName, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text('${profile.employeeNo} · ${profile.status}'),
              if (profile.joinDate != null)
                Text('Masuk sejak ${profile.joinDate}'),
            ],
          ),
        ),
      );

  Widget _selfAttendanceCard() => Card(
        elevation: 0,
        color: Theme.of(context).colorScheme.secondaryContainer,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        child: ListTile(
          leading: const Icon(Icons.fingerprint),
          title: const Text('Absensi Saya'),
          subtitle: const Text('Clock-in/out dengan bukti GPS + selfie'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const SelfAttendanceScreen()),
          ),
        ),
      );

  Widget _balanceCard(LeaveBalanceInfo? balance) => Card(
        elevation: 0,
        color: Theme.of(context).colorScheme.primaryContainer,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        child: ListTile(
          leading: const Icon(Icons.beach_access),
          title: const Text('Sisa Cuti Tahunan'),
          subtitle: balance == null
              ? const Text('Belum diatur HR — pengajuan tetap bisa diajukan')
              : Text(
                  '${balance.remaining} dari ${balance.totalDays} hari '
                  '(terpakai ${balance.usedDays}) · periode ${balance.year}',
                ),
        ),
      );

  Widget _requestLeaveCard() => Card(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Ajukan Cuti / Izin', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _selectedType,
                decoration: const InputDecoration(labelText: 'Jenis', border: OutlineInputBorder()),
                items: [
                  for (final t in _leaveTypes)
                    DropdownMenuItem(value: t, child: Text(t)),
                ],
                onChanged: (v) => setState(() => _selectedType = v!),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.calendar_today_outlined, size: 18),
                      label: Text(_startDate.toString().substring(0, 10)),
                      onPressed: () => _pickDate(isStart: true),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.calendar_today_outlined, size: 18),
                      label: Text(_endDate.toString().substring(0, 10)),
                      onPressed: () => _pickDate(isStart: false),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  icon: const Icon(Icons.send_outlined),
                  label: Text(_submitting ? 'Mengirim...' : 'Ajukan $_typeLabel'),
                  onPressed: _submitting ? null : _submitLeave,
                ),
              ),
            ],
          ),
        ),
      );

  Widget _leavesCard(List<MyLeaveRequest> leaves) => Card(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Pengajuan Saya', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              if (leaves.isEmpty)
                const Text('Belum ada pengajuan cuti/izin.', style: TextStyle(color: Colors.grey)),
              for (final leave in leaves)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  title: Text('${leave.leaveType} · ${leave.startDate} s.d. ${leave.endDate}'),
                  subtitle: leave.decisionNote != null ? Text(leave.decisionNote!) : null,
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Chip(
                        label: Text(leave.status, style: const TextStyle(fontSize: 11)),
                        visualDensity: VisualDensity.compact,
                        backgroundColor: _statusColor(leave.status).withOpacity(0.15),
                      ),
                      if (leave.isPending)
                        IconButton(
                          icon: const Icon(Icons.close, size: 18),
                          tooltip: 'Batalkan',
                          onPressed: () => _cancelLeave(leave),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      );

  Widget _payslipsCard(List<MyPayslip> slips) => Card(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Slip Gaji', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              if (slips.isEmpty)
                const Text('Belum ada slip yang difinalisasi.',
                    style: TextStyle(color: Colors.grey)),
              for (final slip in slips)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  leading: const Icon(Icons.receipt_long_outlined),
                  title: Text('${_monthName(slip.month)} ${slip.year}'),
                  subtitle: Text(
                    'Bruto ${_rupiah(slip.gross)} · PPh21 -${_rupiah(slip.taxPph21)}'
                    + (slip.overtimeHours > 0 ? ' · lembur ${slip.overtimeHours} jam' : ''),
                  ),
                  trailing: Text(
                    _rupiah(slip.netPay),
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                ),
            ],
          ),
        ),
      );

  Widget _notificationsCard(List<AppNotification> notifications) => Card(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Notifikasi', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              if (notifications.isEmpty)
                const Text('Belum ada notifikasi.', style: TextStyle(color: Colors.grey)),
              for (final n in notifications)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  leading: Icon(
                    n.isUnread ? Icons.notifications_active_outlined : Icons.notifications_none,
                    color: n.isUnread ? Theme.of(context).colorScheme.primary : Colors.grey,
                  ),
                  title: Text(n.title),
                  subtitle: n.body != null ? Text(n.body!) : null,
                  trailing: n.isUnread
                      ? IconButton(
                          icon: const Icon(Icons.done_all, size: 18),
                          tooltip: 'Tandai dibaca',
                          onPressed: () => _markRead(n),
                        )
                      : null,
                ),
            ],
          ),
        ),
      );
}
