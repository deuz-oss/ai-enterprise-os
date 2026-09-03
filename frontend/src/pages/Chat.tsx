import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { ClipboardList, CornerUpLeft, Hash, Lock, MessageCircle, Megaphone } from "lucide-react";
import { PageHeader } from "../components/workspace";

interface ChannelRow {
  id: string;
  name: string;
  slug: string;
  channel_type: string;
  member_count: number;
  last_message_preview: string;
  unread_count: number;
}

interface MessageRow {
  id: string;
  sender_id: string;
  content: string;
  parent_id: string | null;
  edited_at: string | null;
  created_at: string;
  reactions: Record<string, number>;
  is_own: boolean;
  message_type?: string;
  card_data?: { title: string; body?: string; type?: string } | null;
  actions?: { id: string; label: string; style?: string }[] | null;
}

const EMOJI_REACTIONS = ["👍", "❤️", "🎉", "😂", "🙏", "🔥"];

export default function Chat() {
  const qc = useQueryClient();
  const [activeChannel, setActiveChannel] = useState<string | null>(null);
  const [threadParent, setThreadParent] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { data: channels } = useQuery({
    queryKey: ["chat-channels"],
    queryFn: () => api.get<ChannelRow[]>("/chat/channels"),
    refetchInterval: 4000,
  });

  const { data: messages } = useQuery({
    queryKey: ["chat-messages", activeChannel, threadParent],
    queryFn: () =>
      api.get<MessageRow[]>(
        `/chat/channels/${activeChannel}/messages${threadParent ? `?parent_id=${threadParent}` : ""}`
      ),
    enabled: Boolean(activeChannel),
    refetchInterval: 2500,
  });

  const { data: searchResults } = useQuery({
    queryKey: ["chat-search", searchQuery, activeChannel],
    queryFn: () =>
      api.get<MessageRow[]>(
        `/chat/search?q=${encodeURIComponent(searchQuery)}${activeChannel ? `&channel_id=${activeChannel}` : ""}`
      ),
    enabled: searchQuery.trim().length >= 2,
  });

  const { data: mentionResults } = useQuery({
    queryKey: ["mention-search", mentionQuery],
    queryFn: () => api.get<{ id: string; full_name: string; email: string }[]>(`/chat/users/search?q=${encodeURIComponent(mentionQuery || "")}`),
    enabled: mentionQuery !== null,
  });

  const createChannel = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/chat/channels", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-channels"] }),
  });

  const sendMessage = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.post(`/chat/channels/${activeChannel}/messages`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat-messages"] });
      qc.invalidateQueries({ queryKey: ["chat-channels"] });
      if (inputRef.current) inputRef.current.value = "";
    },
  });

  const addReaction = useMutation({
    mutationFn: ({ messageId, emoji }: { messageId: string; emoji: string }) =>
      api.post(`/chat/messages/${messageId}/react`, { emoji }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-messages"] }),
  });

  const deleteMessage = useMutation({
    mutationFn: (messageId: string) => api.delete(`/chat/messages/${messageId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-messages"] }),
  });

  const editMessage = useMutation({
    mutationFn: ({ messageId, content }: { messageId: string; content: string }) =>
      api.patch(`/chat/messages/${messageId}`, { content }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-messages"] }),
  });

  const markRead = useMutation({
    mutationFn: (channelId: string) => api.post(`/chat/channels/${channelId}/read-all`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-channels"] }),
  });

  const handleAction = useMutation({
    mutationFn: ({ messageId, actionId }: { messageId: string; actionId: string }) =>
      api.post(`/chat/messages/${messageId}/actions/${actionId}`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat-messages"] });
      qc.invalidateQueries({ queryKey: ["chat-channels"] });
    },
  });

  // Fase 12: AI kolaborasi — digest harian & rangkuman thread
  const [showDigest, setShowDigest] = useState(false);
  const digest = useQuery({
    queryKey: ["chat-digest"],
    queryFn: () =>
      api.get<{ date: string; items: { type: string; detail: string; refs: string[] }[] }>(
        "/chat/digest"
      ),
    enabled: showDigest,
  });
  const summarize = useMutation({
    mutationFn: (messageId: string) => api.post(`/chat/messages/${messageId}/summarize`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-messages"] }),
  });

  // Scroll to bottom on new messages
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  // WebSocket real-time (PRD §9.4) — polling tetap sebagai fallback.
  useEffect(() => {
    if (!activeChannel) return;
    const base = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? "/api/v1";
    const token = localStorage.getItem("aeos_token") ?? "";
    if (!token) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = base.startsWith("http") ? new URL(base).host : window.location.host;
    const wsUrl = `${proto}//${host}/api/v1/chat/ws?token=${encodeURIComponent(token)}`;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = () => qc.invalidateQueries({ queryKey: ["chat-messages"] });
    } catch {
      // abaikan — polling yang menangani
    }
    return () => {
      try {
        ws?.close();
      } catch {}
    };
  }, [activeChannel]);

  function handleSend(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const content = String(form.get("content") || "").trim();
    if (!content || !activeChannel) return;
    sendMessage.mutate({ content, parent_id: threadParent || undefined });
  }

  const activeMeta = channels?.find((c) => c.id === activeChannel);
  const channelName = activeMeta?.name ?? "Pilih channel";

  return (
    <div className="space-y-4">
      <PageHeader
        icon={MessageCircle}
        title="Chat Workspace"
        subtitle="Gratis di semua paket — channel proyek ter-scope per penempatan"
      />

      <div className="flex gap-4" style={{ height: "64vh" }}>
        {/* Channel list */}
        <div
          className="flex w-64 shrink-0 flex-col overflow-hidden rounded-md"
          style={{ border: "1px solid var(--border)", backgroundColor: "var(--sidebar)" }}
        >
          <div
            className="flex items-center justify-between px-3 py-2"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Channel
            </span>
          </div>

          <form
            className="flex gap-1 p-2"
            style={{ borderBottom: "1px solid var(--border)" }}
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const name = String(form.get("name") || "").trim();
              if (!name) return;
              createChannel.mutate({ name });
              e.currentTarget.reset();
            }}
          >
            <input name="name" required placeholder="Channel baru ..." className="input flex-1 py-1 text-xs" />
            <button className="btn-secondary px-2 py-1 text-xs">+</button>
          </form>

          <div className="flex-1 overflow-y-auto">
            {(channels ?? []).map((ch) => (
              <button
                key={ch.id}
                onClick={() => {
                  setActiveChannel(ch.id);
                  setThreadParent(null);
                }}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--hover)]"
                style={{
                  backgroundColor: activeChannel === ch.id ? "var(--hover)" : "transparent",
                  color: activeChannel === ch.id ? "var(--text)" : "var(--text-muted)",
                }}
              >
                <span className="flex min-w-0 items-center gap-1.5 truncate">
                  {ch.channel_type === "private" ? (
                    <Lock className="h-3.5 w-3.5 shrink-0" />
                  ) : ch.channel_type === "broadcast" ? (
                    <Megaphone className="h-3.5 w-3.5 shrink-0" />
                  ) : (
                    <Hash className="h-3.5 w-3.5 shrink-0" />
                  )}
                  <span className="truncate">{ch.name}</span>
                </span>
                {ch.unread_count > 0 && (
                  <span className="ml-1 shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ backgroundColor: "var(--accent)" }}>
                    {ch.unread_count}
                  </span>
                )}
              </button>
            ))}
            {channels?.length === 0 && (
              <p className="px-3 py-6 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                Belum ada channel.
              </p>
            )}
          </div>
        </div>

        {/* Message area */}
        <div className="flex flex-1 flex-col overflow-hidden rounded-md" style={{ border: "1px solid var(--border)" }}>
          <div
            className="flex items-center justify-between gap-2 px-4 py-2"
            style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
          >
            <span className="flex items-center gap-1.5 truncate font-medium" style={{ color: "var(--text)" }}>
              {threadParent && <CornerUpLeft className="h-3.5 w-3.5 shrink-0" />}
              {threadParent ? "Thread Balasan" : channelName}
            </span>
            <div className="flex items-center gap-1.5">
              <input
                placeholder="Cari..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input w-28 py-1 text-xs"
              />
              {threadParent ? (
                <>
                  <button
                    onClick={() => summarize.mutate(threadParent)}
                    disabled={summarize.isPending}
                    className="btn-secondary flex items-center gap-1 py-0.5 text-xs"
                    title="Rangkum thread jadi poin keputusan/tugas (@AEOS)"
                  >
                    <CornerUpLeft className="h-3 w-3" /> Rangkum
                  </button>
                  <button onClick={() => setThreadParent(null)} className="btn-secondary py-0.5 text-xs">
                    Kembali
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setShowDigest((v) => !v)}
                  className="btn-secondary flex items-center gap-1 py-0.5 text-xs"
                  title="Digest harian: approval menunggu, SLA, kontrak, invoice"
                >
                  <ClipboardList className="h-3 w-3" /> Digest
                </button>
              )}
              {activeChannel && (
                <button onClick={() => markRead.mutate(activeChannel!)} className="btn-secondary py-0.5 text-xs">
                  Tandai dibaca
                </button>
              )}
            </div>
          </div>
          {searchQuery.trim().length >= 2 && searchResults && (
            <div className="max-h-40 overflow-y-auto border-b px-2 py-1" style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}>
              <p className="px-2 py-1 text-xs" style={{ color: "var(--text-muted)" }}>
                Hasil cari "{searchQuery}" — {searchResults.length} pesan
                <button onClick={() => setSearchQuery("")} className="ml-2" style={{ color: "var(--accent)" }}>
                  tutup
                </button>
              </p>
              {searchResults.map((m: MessageRow) => (
                <div key={m.id} className="truncate px-2 py-1 text-xs" style={{ color: "var(--text)" }}>
                  {m.content.slice(0, 80)}
                </div>
              ))}
              {searchResults.length === 0 && (
                <p className="px-2 py-2 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                  Tidak ada hasil.
                </p>
              )}
            </div>
          )}

          {showDigest && !threadParent && (
            <div className="max-h-52 overflow-y-auto border-b px-4 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}>
              <p className="mb-1 flex items-center justify-between text-xs font-semibold" style={{ color: "var(--text)" }}>
                <span className="flex items-center gap-1.5">
                  <ClipboardList className="h-3.5 w-3.5" /> Digest harian {digest.data?.date ? `· ${digest.data.date}` : ""}
                </span>
                <button onClick={() => setShowDigest(false)} style={{ color: "var(--accent)" }}>tutup</button>
              </p>
              {digest.isLoading && <p className="text-xs" style={{ color: "var(--text-muted)" }}>Menyusun…</p>}
              {(digest.data?.items ?? []).map((it, i) => (
                <div key={i} className="py-0.5 text-xs" style={{ color: "var(--text)" }}>
                  • {it.detail}
                  {it.refs.length > 0 && (
                    <span style={{ color: "var(--text-muted)" }}> — {it.refs.join(", ")}</span>
                  )}
                </div>
              ))}
              {digest.data && digest.data.items.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Tidak ada item penting hari ini.</p>
              )}
            </div>
          )}

          <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto px-4 py-3">
            {(messages ?? []).map((m) => (
              <div
                key={m.id}
                className="group rounded px-2 py-1.5 transition-colors hover:bg-[var(--hover)]"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                    {m.sender_id.slice(0, 8)}… · {new Date(m.created_at).toLocaleString("id-ID")}
                    {m.edited_at && <span className="ml-1 italic">diedit</span>}
                  </span>
                  {m.is_own && !threadParent && (
                    <button
                      onClick={() => setThreadParent(m.id)}
                      className="shrink-0 text-[11px] hover:opacity-80"
                      style={{ color: "var(--accent)" }}
                    >
                      Balas
                    </button>
                  )}
                </div>

                <p className="mt-0.5 whitespace-pre-wrap break-words text-sm" style={{ color: "var(--text)" }}>
                  {m.content}
                </p>
                {m.message_type === "card" && m.card_data && (
                  <div
                    className="mt-2 rounded-md p-3"
                    style={{
                      border: "1px solid var(--border)",
                      backgroundColor: "var(--bg-elevated)",
                    }}
                  >
                    <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>
                      {m.card_data.title}
                    </p>
                    {m.card_data.body && (
                      <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                        {m.card_data.body}
                      </p>
                    )}
                    {m.actions && m.actions.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {m.actions.map((a) => (
                          <button
                            key={a.id}
                            onClick={() => handleAction.mutate({ messageId: m.id, actionId: a.id })}
                            className="rounded px-2.5 py-1 text-xs font-medium"
                            style={{
                              backgroundColor: a.style === "primary" ? "var(--accent)" : "var(--bg-elevated)",
                              color: a.style === "primary" ? "white" : "var(--text)",
                              border: "1px solid var(--border)",
                            }}
                          >
                            {a.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-1 flex flex-wrap items-center gap-1">
                  {Object.entries(m.reactions).map(([emoji, count]) => (
                    <button
                      key={emoji}
                      onClick={() => addReaction.mutate({ messageId: m.id, emoji })}
                      className="rounded-full px-1.5 py-0.5 text-xs"
                      style={{ border: "1px solid var(--border)" }}
                    >
                      {emoji} {count}
                    </button>
                  ))}
                  {EMOJI_REACTIONS.map((emoji) => (
                    <button
                      key={emoji}
                      onClick={() => addReaction.mutate({ messageId: m.id, emoji })}
                      className="rounded px-1 py-0.5 text-xs hover:bg-[var(--hover)]"
                      title={`React ${emoji}`}
                    >
                      {emoji}
                    </button>
                  ))}
                  {m.is_own && (
                    <>
                      <button
                        onClick={() => {
                          const next = window.prompt("Edit pesan:", m.content);
                          if (next !== null) editMessage.mutate({ messageId: m.id, content: next });
                        }}
                        className="ml-auto text-[11px] hover:opacity-80"
                        style={{ color: "var(--text-muted)" }}
                      >
                        edit
                      </button>
                      <button
                        onClick={() => deleteMessage.mutate(m.id)}
                        className="text-[11px] text-rose-400 hover:text-rose-600"
                      >
                        hapus
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
            {messages?.length === 0 && (
              <p className="py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                Belum ada pesan. Mulai percakapan!
              </p>
            )}
          </div>

          <form
            onSubmit={(e) => {
              handleSend(e);
              setMentionQuery(null);
            }}
            className="relative flex gap-2 px-4 py-3"
            style={{ borderTop: "1px solid var(--border)" }}
          >
            <div className="relative flex-1">
              <input
                ref={inputRef}
                name="content"
                required
                placeholder={activeChannel ? (threadParent ? "Balas di thread..." : "Tulis pesan... (@ untuk mention, @AEOS untuk bertanya, / untuk perintah)") : "Pilih channel dulu"}
                disabled={!activeChannel}
                className="input w-full"
                onChange={(e) => {
                  const val = e.target.value;
                  const atIdx = val.lastIndexOf("@");
                  if (atIdx >= 0) {
                    const after = val.slice(atIdx + 1).split(/\s/)[0];
                    if (/^[a-zA-Z0-9._-]*$/.test(after)) setMentionQuery(after);
                    else setMentionQuery(null);
                  } else setMentionQuery(null);
                }}
              />
              {mentionQuery !== null && (mentionResults ?? []).length > 0 && (
                <div
                  className="absolute bottom-full left-0 right-0 mb-1 max-h-36 overflow-y-auto rounded-md shadow-lg"
                  style={{ backgroundColor: "var(--bg-elevated)", border: "1px solid var(--border)" }}
                >
                  {(mentionResults ?? []).map((u: { id: string; full_name: string; email: string }) => (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => {
                        const cur = inputRef.current?.value || "";
                        const atIdx = cur.lastIndexOf("@");
                        const next = cur.slice(0, atIdx + 1) + u.full_name + " ";
                        if (inputRef.current) inputRef.current.value = next;
                        setMentionQuery(null);
                        inputRef.current?.focus();
                      }}
                      className="flex w-full items-center justify-between px-3 py-1.5 text-left text-xs hover:bg-[var(--hover)]"
                    >
                      <span>{u.full_name}</span>
                      <span style={{ color: "var(--text-muted)" }}>{u.email}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button disabled={!activeChannel || sendMessage.isPending} className="btn">
              Kirim
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
