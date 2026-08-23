"""Parameter tarif & aturan penagihan, dipisah dari logika kode.

Angka di bawah adalah default yang dipakai saat membuat invoice; nilai
final tetap disimpan per invoice sehingga riwayat tidak berubah ketika
regulasi berubah. Verifikasi ulang terhadap regulasi terbaru (PPN 12%
PMK 131/2024, PPh 23) sebelum pemakaian produksi.
"""

# PPN standar atas (payrol + fee).
DEFAULT_PPN_RATE = 0.11

# PPh 23 atas jasa (fee management) — dipotong pihak pembayar.
DEFAULT_PPH23_RATE = 0.02

# Jatuh tempo invoice default sejak tanggal terbit.
DEFAULT_DUE_DAYS = 30

# Bucket laporan aging (hari terlambat).
AGING_BUCKETS = [("current", 0), ("1-30", 30), ("31-60", 60), (">60", None)]
