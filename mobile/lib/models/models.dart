/// Model ringan untuk data yang dipakai UI mobile.
class UserAccount {
  UserAccount({required this.id, required this.email, required this.fullName, required this.role});

  final String id;
  final String email;
  final String fullName;
  final String role;

  factory UserAccount.fromMap(Map<String, dynamic> m) => UserAccount(
        id: m['id'] as String,
        email: (m['email'] ?? '') as String,
        fullName: (m['full_name'] ?? '') as String,
        role: (m['role'] ?? '') as String,
      );
}

class OverviewStats {
  OverviewStats({
    required this.leadsTotal,
    required this.leadsWon,
    required this.clients,
    required this.jobOrdersOpen,
    required this.candidatesTotal,
  });

  final int leadsTotal;
  final int leadsWon;
  final int clients;
  final int jobOrdersOpen;
  final int candidatesTotal;

  factory OverviewStats.fromMap(Map<String, dynamic> m) {
    final leads = (m['leads'] ?? {}) as Map<String, dynamic>;
    final jo = (m['job_orders'] ?? {}) as Map<String, dynamic>;
    final candidates = (m['candidates'] ?? {}) as Map<String, dynamic>;
    return OverviewStats(
      leadsTotal: (leads['total'] ?? 0) as int,
      leadsWon: (leads['won'] ?? 0) as int,
      clients: (m['clients'] ?? 0) as int,
      jobOrdersOpen: (jo['open'] ?? 0) as int,
      candidatesTotal: (candidates['total'] ?? 0) as int,
    );
  }
}

class AttendanceRow {
  AttendanceRow({
    required this.id,
    required this.employeeId,
    required this.year,
    required this.month,
    required this.presentDays,
    required this.overtimeHours,
    required this.clientApproved,
  });

  final String id;
  final String employeeId;
  final int year;
  final int month;
  final int presentDays;
  final int overtimeHours;
  final bool clientApproved;

  factory AttendanceRow.fromMap(Map<String, dynamic> m) => AttendanceRow(
        id: m['id'] as String,
        employeeId: m['employee_id'] as String,
        year: (m['year'] ?? 0) as int,
        month: (m['month'] ?? 0) as int,
        presentDays: (m['present_days'] ?? 0) as int,
        overtimeHours: (m['overtime_hours'] ?? 0) as int,
        clientApproved: (m['client_approved'] ?? false) as bool,
      );
}

class PayrollRunRow {
  PayrollRunRow({
    required this.id,
    required this.year,
    required this.month,
    required this.status,
    required this.finalizedAt,
  });

  final String id;
  final int year;
  final int month;
  final String status;
  final String? finalizedAt;

  bool get isFinal => status == 'final';

  factory PayrollRunRow.fromMap(Map<String, dynamic> m) => PayrollRunRow(
        id: m['id'] as String,
        year: (m['year'] ?? 0) as int,
        month: (m['month'] ?? 0) as int,
        status: (m['status'] ?? 'draft') as String,
        finalizedAt: m['finalized_at'] as String?,
      );
}

class PayslipRow {
  PayslipRow({
    required this.id,
    required this.employeeId,
    required this.netPay,
    required this.gross,
    required this.taxPph21,
    required this.overtimeAmount,
  });

  final String id;
  final String employeeId;
  final num netPay;
  final num gross;
  final num taxPph21;
  final num overtimeAmount;

  factory PayslipRow.fromMap(Map<String, dynamic> m) => PayslipRow(
        id: m['id'] as String,
        employeeId: m['employee_id'] as String,
        netPay: (m['net_pay'] ?? 0) as num,
        gross: (m['gross'] ?? 0) as num,
        taxPph21: (m['tax_pph21'] ?? 0) as num,
        overtimeAmount: (m['overtime_amount'] ?? 0) as num,
      );
}

class ExpiringContract {
  ExpiringContract({
    required this.contractId,
    required this.contractNo,
    required this.employeeName,
    required this.endDate,
    required this.daysLeft,
  });

  final String contractId;
  final String contractNo;
  final String employeeName;
  final String endDate;
  final int daysLeft;

  factory ExpiringContract.fromMap(Map<String, dynamic> m) => ExpiringContract(
        contractId: m['contract_id'] as String,
        contractNo: (m['contract_no'] ?? '') as String,
        employeeName: (m['employee_name'] ?? '') as String,
        endDate: (m['end_date'] ?? '-') as String,
        daysLeft: (m['days_left'] ?? 0) as int,
      );
}
