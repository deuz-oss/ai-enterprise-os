/// Konfigurasi global aplikasi mobile.
library;

/// URL API default.
///
/// - Android emulator: `http://10.0.2.2:8000/api/v1` (loopback host)
/// - iOS simulator / perangkat di jaringan yang sama: `http://<IP-LAN>:8000/api/v1`
const String kDefaultApiUrl = String.fromEnvironment(
  'AEOS_API_URL',
  defaultValue: 'http://10.0.2.2:8000/api/v1',
);
