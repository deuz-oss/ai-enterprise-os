import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';

/// Klien HTTP sederhana dengan JWT persisten (shared_preferences).
///
/// 401 otomatis menghapus token — sama seperti perilaku web.
class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient._();
  static final ApiClient instance = ApiClient._();

  static const _tokenKey = 'aeos_token';
  static const _userKey = 'aeos_user';
  static const _urlKey = 'aeos_api_url';

  http.Client _http = http.Client();
  String _baseUrl = kDefaultApiUrl;
  String? _token;
  Map<String, dynamic>? _user;

  String get baseUrl => _baseUrl;
  String? get token => _token;
  Map<String, dynamic>? get user => _user;
  bool get isLoggedIn => _token != null;
  String get role => (_user?['role'] as String?) ?? '';

  Future<void> loadSession() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString(_urlKey) ?? _baseUrl;
    _token = prefs.getString(_tokenKey);
    final rawUser = prefs.getString(_userKey);
    if (rawUser != null) {
      _user = jsonDecode(rawUser) as Map<String, dynamic>;
    }
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url.endsWith('/api/v1') ? url : '$url/api/v1';
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_urlKey, _baseUrl);
  }

  Future<void> saveSession(String token, Map<String, dynamic> user) async {
    _token = token;
    _user = user;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
    await prefs.setString(_userKey, jsonEncode(user));
  }

  Future<void> clearSession() async {
    _token = null;
    _user = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_userKey);
  }

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final clean = path.startsWith('/') ? path.substring(1) : path;
    return Uri.parse('$_baseUrl/$clean').replace(queryParameters: query);
  }

  Map<String, String> _headers() => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  Future<dynamic> _send(
    Future<http.Response> Function() fn,
  ) async {
    try {
      final resp = await fn();
      if (resp.statusCode == 204) return null;
      final body = jsonDecode(utf8.decode(resp.bodyBytes));
      if (resp.statusCode >= 400) {
        String detail = resp.reasonPhrase ?? 'Terjadi kesalahan';
        if (body is Map && body['detail'] != null) detail = body['detail'].toString();
        if (resp.statusCode == 401) await clearSession();
        throw ApiException(detail, statusCode: resp.statusCode);
      }
      return body;
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Tidak dapat terhubung ke server ($_baseUrl)');
    }
  }

  Future<dynamic> get(String path, [Map<String, dynamic>? query]) =>
      _send(() => _http.get(_uri(path, query), headers: _headers()));

  Future<dynamic> post(String path, [Map<String, dynamic>? body]) => _send(
      () => _http.post(_uri(path), headers: _headers(), body: jsonEncode(body ?? {})));

  Future<dynamic> patch(String path, Map<String, dynamic> body) =>
      _send(() => _http.patch(_uri(path), headers: _headers(), body: jsonEncode(body)));

  /// POST multipart (unggah file + field), mis. absensi GPS+selfie.
  Future<dynamic> postMultipart(
    String path,
    List<http.MultipartFile> files, {
    Map<String, String> fields = const {},
  }) {
    return _send(() async {
      final req = http.MultipartRequest('POST', _uri(path))
        ..files.addAll(files)
        ..fields.addAll(fields);
      final token = _token;
      if (token != null) req.headers['Authorization'] = 'Bearer $token';
      final streamed = await _http.send(req);
      return http.Response.fromStream(streamed);
    });
  }
}
