# AEOS Mobile (Flutter)

Aplikasi mobile internal AI Enterprise OS untuk staf: beranda ringkasan,
approval absensi klien, slip gaji per run payrol, dan reminder kontrak
mendekati akhir. Tab ditampilkan sesuai role pengguna.

## Fitur v1

| Tab | Isi | Role |
|-----|-----|------|
| Beranda | Angka ringkasan dari `GET /overview` | semua |
| Absensi | Setujui/batalkan persetujuan absensi & lembur | admin, operations, management |
| Payrol | Daftar run → slip gaji (read-only) | admin, operations, finance, management |
| Kontrak | Kontrak yang segera berakhir (30/60/90 hari) | admin, hr, management |

## Menjalankan

Backend harus dapat dijangkau dari perangkat. Default API URL:
`http://10.0.2.2:8000/api/v1` (loopback host dari Android emulator).
URL bisa diubah langsung di layar login.

```bash
cd mobile
flutter create . --org id.aeos --platforms=android,ios   # generate folder platform
flutter pub get
flutter run
```

Untuk build rilis:

```bash
flutter build apk            # APK debug/release
flutter build appbundle      # untuk Play Store
```

## Catatan

- Token JWT disimpan via `shared_preferences` — untuk produksi pertimbangkan
  migrasi ke `flutter_secure_storage` (Keychain/Keystore).
- URL API juga bisa dibake saat build: `flutter build apk --dart-define=AEOS_API_URL=https://api.example.com/api/v1`.
