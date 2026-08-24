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

// ---------- Portal self-service karyawan (/me/*) ----------

class PortalProfile {
  PortalProfile({
    required this.employeeNo,
    required this.fullName,
    required this.status,
    required this.joinDate,
    required this.phone,
    this.bankName,
    this.bankAccount,
  });

  final String employeeNo;
  final String fullName;
  final String status;
  final String? joinDate;
  final String? phone;
  final String? bankName;
  final String? bankAccount;

  factory PortalProfile.fromMap(Map<String, dynamic> m) => PortalProfile(
        employeeNo: (m['employee_no'] ?? '') as String,
        fullName: (m['full_name'] ?? '') as String,
        status: (m['status'] ?? '') as String,
        joinDate: m['join_date'] as String?,
        phone: m['phone'] as String?,
        bankName: m['bank_name'] as String?,
        bankAccount: m['bank_account'] as String?,
      );
}

class LeaveBalanceInfo {
  LeaveBalanceInfo({
    required this.year,
    required this.totalDays,
    required this.usedDays,
    required this.remaining,
  });

  final int year;
  final int totalDays;
  final int usedDays;
  final int remaining;

  factory LeaveBalanceInfo.fromMap(Map<String, dynamic> m) => LeaveBalanceInfo(
        year: (m['year'] ?? 0) as int,
        totalDays: (m['total_days'] ?? 0) as int,
        usedDays: (m['used_days'] ?? 0) as int,
        remaining: (m['remaining'] ?? 0) as int,
      );
}

class MyPayslip {
  MyPayslip({
    required this.id,
    required this.year,
    required this.month,
    required this.netPay,
    required this.gross,
    required this.taxPph21,
    required this.overtimeHours,
  });

  final String id;
  final int year;
  final int month;
  final num netPay;
  final num gross;
  final num taxPph21;
  final int overtimeHours;

  factory MyPayslip.fromMap(Map<String, dynamic> m) => MyPayslip(
        id: m['id'] as String,
        year: (m['year'] ?? 0) as int,
        month: (m['month'] ?? 0) as int,
        netPay: (m['net_pay'] ?? 0) as num,
        gross: (m['gross'] ?? 0) as num,
        taxPph21: (m['tax_pph21'] ?? 0) as num,
        overtimeHours: (m['overtime_hours'] ?? 0) as int,
      );
}

class MyLeaveRequest {
  MyLeaveRequest({
    required this.id,
    required this.leaveType,
    required this.startDate,
    required this.endDate,
    required this.status,
    this.reason,
    this.decisionNote,
  });

  final String id;
  final String leaveType;
  final String startDate;
  final String endDate;
  final String status;
  final String? reason;
  final String? decisionNote;

  bool get isPending => status == 'menunggu';

  factory MyLeaveRequest.fromMap(Map<String, dynamic> m) => MyLeaveRequest(
        id: m['id'] as String,
        leaveType: (m['leave_type'] ?? '') as String,
        startDate: (m['start_date'] ?? '') as String,
        endDate: (m['end_date'] ?? '') as String,
        status: (m['status'] ?? '') as String,
        reason: m['reason'] as String?,
        decisionNote: m['decision_note'] as String?,
      );
}

class AppNotification {
  AppNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.readAt,
    required this.createdAt,
  });

  final String id;
  final String title;
  final String? body;
  final String? readAt;
  final String createdAt;

  bool get isUnread => readAt == null;

  factory AppNotification.fromMap(Map<String, dynamic> m) => AppNotification(
        id: m['id'] as String,
        title: (m['title'] ?? '') as String,
        body: m['body'] as String?,
        readAt: m['read_at'] as String?,
        createdAt: (m['created_at'] ?? '') as String,
      );
}
