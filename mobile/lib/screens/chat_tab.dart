import 'package:flutter/material.dart';
import '../api/api_client.dart';

/// Chat tab — PRD v3.0 mobile hanya butuh HP (tanpa Talent).
/// Polling GET /chat/channels + GET /chat/channels/{id}/messages.
class ChatTab extends StatefulWidget {
  const ChatTab({super.key});
  @override
  State<ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends State<ChatTab> {
  List<dynamic> _channels = [];
  List<dynamic> _messages = [];
  String? _selectedChannelId;
  bool _loading = true;
  final _msgCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadChannels();
  }

  Future<void> _loadChannels() async {
    setState(() => _loading = true);
    try {
      final res = await ApiClient.instance.get('/chat/channels');
      final data = res is List ? res : (res['items'] ?? res['channels'] ?? []);
      setState(() => _channels = List<dynamic>.from(data as List));
    } catch (_) {
      // fallback empty — backend mungkin belum seed
    }
    setState(() => _loading = false);
  }

  Future<void> _loadMessages(String channelId) async {
    setState(() => _selectedChannelId = channelId);
    try {
      final res = await ApiClient.instance.get('/chat/channels/$channelId/messages');
      final data = res is List ? res : (res['items'] ?? res['messages'] ?? []);
      setState(() => _messages = List<dynamic>.from(data as List));
    } catch (_) {
      setState(() => _messages = []);
    }
  }

  Future<void> _send() async {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty || _selectedChannelId == null) return;
    try {
      await ApiClient.instance.post('/chat/channels/$_selectedChannelId/messages', body: {'content': text});
      _msgCtrl.clear();
      await _loadMessages(_selectedChannelId!);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Gagal kirim: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_selectedChannelId == null) {
      return RefreshIndicator(
        onRefresh: _loadChannels,
        child: _channels.isEmpty
            ? ListView(children: const [SizedBox(height: 80), Center(child: Text('Belum ada channel'))])
            : ListView.separated(
                itemCount: _channels.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (_, i) {
                  final ch = _channels[i] as Map;
                  return ListTile(
                    leading: const Icon(Icons.tag),
                    title: Text(ch['name'] ?? ch['slug'] ?? 'channel'),
                    subtitle: Text(ch['description'] ?? '', maxLines: 1),
                    onTap: () => _loadMessages(ch['id'] as String),
                  );
                },
              ),
      );
    }
    return Column(
      children: [
        AppBar(
          leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => setState(() => _selectedChannelId = null)),
          title: const Text('Pesan'),
          actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: () => _loadMessages(_selectedChannelId!))],
        ),
        Expanded(
          child: _messages.isEmpty
              ? const Center(child: Text('Belum ada pesan'))
              : ListView.builder(
                  reverse: true,
                  itemCount: _messages.length,
                  itemBuilder: (_, i) {
                    final m = _messages[_messages.length - 1 - i] as Map;
                    return ListTile(
                      title: Text(m['content'] ?? ''),
                      subtitle: Text(m['sender_name'] ?? m['sender_id'] ?? ''),
                    );
                  },
                ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Row(
              children: [
                Expanded(child: TextField(controller: _msgCtrl, decoration: const InputDecoration(hintText: 'Tulis pesan...', border: OutlineInputBorder()), onSubmitted: (_) => _send())),
                const SizedBox(width: 8),
                IconButton.filled(icon: const Icon(Icons.send), onPressed: _send),
              ],
            ),
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _msgCtrl.dispose();
    super.dispose();
  }
}
