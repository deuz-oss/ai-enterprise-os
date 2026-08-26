import 'dart:io';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

import '../api/api_client.dart';

/// Absensi diri via mobile (Fase 8 lanjutan): clock-in/out wajib disertai
/// selfie kamera + koordinat GPS. Endpoint: POST /me/attendance/clock-{in,out}.
class SelfAttendanceScreen extends StatefulWidget {
  const SelfAttendanceScreen({super.key});

  @override
  State<SelfAttendanceScreen> createState() => _SelfAttendanceScreenState();
}

enum _ClockStep { idle, locating, camera, uploading }

class _SelfAttendanceScreenState extends State<SelfAttendanceScreen> {
  _ClockStep _step = _ClockStep.idle;
  String? _message;
  Position? _position;
  bool _isClockIn = true;

  Future<void> _startClock({required bool clockIn}) async {
    setState(() {
      _isClockIn = clockIn;
      _step = _ClockStep.locating;
      _message = null;
    });

    // 1) Izin lokasi + ambil posisi GPS
    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      setState(() {
        _step = _ClockStep.idle;
        _message = 'Izin lokasi ditolak — absensi butuh bukti GPS.';
      });
      return;
    }
    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
      );
      setState(() {
        _position = position;
        _step = _ClockStep.camera;
      });
    } catch (_) {
      setState(() {
        _step = _ClockStep.idle;
        _message = 'Gagal mengambil posisi GPS. Coba ke area terbuka.';
      });
      return;
    }

    // 2) Foto selfie via kamera
    try {
      final picked = await ImagePicker().pickImage(
        source: ImageSource.camera,
        preferredCameraDevice: CameraDevice.front,
        imageQuality: 70,
      );
      if (!mounted) return;
      if (picked == null) {
        setState(() => _step = _ClockStep.idle);
        return;
      }
      await _upload(File(picked.path));
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _step = _ClockStep.idle;
        _message = 'Kamera tidak tersedia atau izin ditolak.';
      });
    }
  }

  Future<void> _upload(File photo) async {
    setState(() => _step = _ClockStep.uploading);
    final pos = _position!;
    final direction = _isClockIn ? 'in' : 'out';
    try {
      final result = await ApiClient.instance.postMultipart(
        '/me/attendance/clock-$direction',
        [
          await http.MultipartFile.fromPath('file', photo.path,
              filename: 'selfie.jpg'),
        ],
        fields: {
          'latitude': pos.latitude.toStringAsFixed(6),
          'longitude': pos.longitude.toStringAsFixed(6),
        },
      ) as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        _step = _ClockStep.idle;
        _message =
            'Clock-$direction tercatat pukul ${result['time'].toString().substring(11, 16)} · ${result['status']}';
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _step = _ClockStep.idle;
        _message = e.message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final busy = _step != _ClockStep.idle;
    return Scaffold(
      appBar: AppBar(title: const Text('Absensi Saya')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              elevation: 0,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Bukti absensi',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 4),
                    const Text(
                      'Setiap clock-in/out mengirim selfie kamera depan dan '
                      'koordinat GPS sebagai bukti kehadiran. Rekap harian '
                      'divalidasi HR/Ops sebelum masuk payrol.',
                    ),
                    if (_position != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          'GPS: ${_position!.latitude.toStringAsFixed(5)}, '
                          '${_position!.longitude.toStringAsFixed(5)}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              icon: const Icon(Icons.login),
              label: const Text('Clock In'),
              onPressed: busy ? null : () => _startClock(clockIn: true),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              icon: const Icon(Icons.logout),
              label: const Text('Clock Out'),
              onPressed: busy ? null : () => _startClock(clockIn: false),
            ),
            const SizedBox(height: 16),
            if (_step == _ClockStep.locating) const LinearProgressIndicator(),
            if (_step == _ClockStep.uploading) ...[
              const LinearProgressIndicator(),
              const SizedBox(height: 8),
              const Text('Mengunggah bukti absensi…', textAlign: TextAlign.center),
            ],
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(_message!, textAlign: TextAlign.center),
              ),
          ],
        ),
      ),
    );
  }
}
