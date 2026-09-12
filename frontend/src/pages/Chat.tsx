import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { api } from "../api/client";
import {
  BellOff,
  ClipboardList,
  CornerUpLeft,
  FileText,
  Hash,
  Lock,
  MessageCircle,
  Megaphone,
  Paperclip,
  Pin,
  PinOff,
  X,
} from "lucide-react";
import { PageHeader } from "../components/workspace";
import { promptToast } from "../components/ui";

// Index dasar arbitrer yang besar untuk `firstItemIndex` Virtuoso -- pola
// resmi mereka untuk "reverse infinite scroll" (chat): begitu halaman
// histori lebih lama di-prepend, index ini dikurangi sebanyak pesan yang
// baru ditambahkan, supaya Virtuoso tahu item-item itu geser ke belakang
// tanpa harus menghitung ulang/geser posisi scroll secara manual.
const VIRTUOSO_START_INDEX = 1_000_000;

type NotifyLevel = "all" | "mentions" | "none";

interface ChannelRow {
  id: string;
  name: string;
  slug: string;
  channel_type: string;
  member_count: number;
  last_message_preview: string;
  unread_count: number;
  mention_count: number;
  notify_level: NotifyLevel;
}

interface ChatFileMeta {
  id: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  url: string;
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
  files: ChatFileMeta[];
  is_pinned: boolean;
  pinned_at: string | null;
}

const EMOJI_REACTIONS = ["👍", "❤️", "🎉", "😂", "🙏", "🔥"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Chat() {
  const qc = useQueryClient();
  const [activeChannel, setActiveChannel] = useState<string | null>(null);
  const [threadParent, setThreadParent] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const virtuosoRef = useRef<VirtuosoHandle>(null);

  const { data: channels } = useQuery({
    queryKey: ["chat-channels"],
    queryFn: () => api.get<ChannelRow[]>("/chat/channels"),
    refetchInterval: 4000,
  });

  // Cursor pagination ala Mattermost (before_id + X-Has-More, lihat
  // backend/app/modules/chat/service.py::list_messages) lewat useInfiniteQuery:
  // page pertama (pageParam=undefined) = pesan terbaru; page berikutnya =
  // histori lebih lama. Halaman disimpan urutan fetch (baru->lama), jadi
  // di-reverse saat dirender agar tampil lama->baru seperti biasa.
  const messagesQueryKey = ["chat-messages", activeChannel, threadParent] as const;

  const {
    data: messagePages,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: messagesQueryKey,
    queryFn: async ({ pageParam }: { pageParam?: string }) => {
      const qs = new URLSearchParams();
      if (threadParent) qs.set("parent_id", threadParent);
      if (pageParam) qs.set("before_id", pageParam);
      const { data, hasMore } = await api.getCursor<MessageRow>(
        `/chat/channels/${activeChannel}/messages?${qs.toString()}`
      );
      return { items: data, hasMore };
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.hasMore && lastPage.items.length > 0 ? lastPage.items[0].id : undefined,
    enabled: Boolean(activeChannel),
    // SENGAJA tanpa refetchInterval/invalidateQueries("chat-messages") --
    // refetch polos akan meminta ulang page pertama (pageParam=undefined =
    // "N pesan terbaru"), yang JENDELANYA BERGESER begitu ada pesan baru
    // masuk. Page kedua dst tetap pakai before_id LAMA (di-cache, tidak
    // ikut refetch) -- pesan yang dulu jadi batas page pertama jadi
    // "terlempar" ke celah antara dua page dan LENYAP dari tampilan.
    // Regresi nyata: ketahuan lewat uji manual di browser (kirim pesan
    // baru sambil sudah scroll ke histori lama -> satu pesan lama hilang).
    // Solusi: pesan baru di-merge langsung ke cache (append/patch by id),
    // TIDAK PERNAH mem-fetch ulang "N terbaru" dan membuang isi page
    // pertama yang sudah ada -- lihat `mergeLatestIntoCache` dkk di bawah.
  });

  const messages = useMemo(
    () => [...(messagePages?.pages ?? [])].reverse().flatMap((p) => p.items),
    [messagePages]
  );

  type MessagesData = typeof messagePages;

  function appendMessageToCache(m: MessageRow) {
    qc.setQueryData<MessagesData>(messagesQueryKey, (old) => {
      if (!old) return old;
      const pages = [...old.pages];
      const first = pages[0] ?? { items: [], hasMore: false };
      if (first.items.some((x) => x.id === m.id)) return old;
      pages[0] = { ...first, items: [...first.items, m] };
      return { ...old, pages };
    });
  }

  function patchMessageInCache(id: string, updater: (m: MessageRow) => MessageRow) {
    qc.setQueryData<MessagesData>(messagesQueryKey, (old) => {
      if (!old) return old;
      return {
        ...old,
        pages: old.pages.map((p) => ({
          ...p,
          items: p.items.map((m) => (m.id === id ? updater(m) : m)),
        })),
      };
    });
  }

  function removeMessageFromCache(id: string) {
    qc.setQueryData<MessagesData>(messagesQueryKey, (old) => {
      if (!old) return old;
      return { ...old, pages: old.pages.map((p) => ({ ...p, items: p.items.filter((m) => m.id !== id) })) };
    });
  }

  // Ambil ulang "N pesan terbaru" tapi MERGE ke page pertama yang sudah
  // ada (tambah/timpa by id), TIDAK PERNAH mengganti isi page pertama
  // seutuhnya -- jadi jendelanya boleh melebar, tidak pernah membuang
  // pesan lama yang sudah ter-load dan membuat celah di sambungan
  // dengan page berikutnya (before_id page itu tetap valid apa adanya).
  async function mergeLatestIntoCache() {
    if (!activeChannel) return;
    const qs = new URLSearchParams();
    if (threadParent) qs.set("parent_id", threadParent);
    const { data: fresh } = await api.getCursor<MessageRow>(
      `/chat/channels/${activeChannel}/messages?${qs.toString()}`
    );
    qc.setQueryData<MessagesData>(messagesQueryKey, (old) => {
      if (!old) return old;
      const pages = [...old.pages];
      const first = pages[0] ?? { items: [], hasMore: false };
      const byId = new Map(first.items.map((m) => [m.id, m]));
      for (const m of fresh) byId.set(m.id, m);
      const merged = [
        ...first.items.map((m) => byId.get(m.id)!),
        ...fresh.filter((m) => !first.items.some((x) => x.id === m.id)),
      ];
      pages[0] = { ...first, items: merged };
      return { ...old, pages };
    });
  }

  // Fallback polling ringan (WS tetap jalur utama) -- pakai merge yang
  // sama, bukan refetchInterval bawaan useInfiniteQuery, supaya tidak
  // kena bug celah di atas.
  useEffect(() => {
    if (!activeChannel) return;
    const id = setInterval(() => {
      mergeLatestIntoCache();
    }, 4000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChannel, threadParent]);

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
      api.post<MessageRow>(`/chat/channels/${activeChannel}/messages`, payload),
    onSuccess: (newMessage) => {
      // Append langsung (bukan refetch/invalidate) -- kita sudah punya
      // objek pesan lengkap dari response, tidak perlu tanya ulang server
      // dan berisiko kena bug jendela-geser di atas.
      appendMessageToCache(newMessage);
      qc.invalidateQueries({ queryKey: ["chat-channels"] });
      if (inputRef.current) inputRef.current.value = "";
      setPendingFiles([]);
    },
  });

  // Lampiran: upload langsung saat file dipilih (alur ala Mattermost --
  // POST /files dulu, id-nya baru disertakan ke POST /messages sebagai
  // file_ids), supaya UI bisa tampilkan progres unggah sebelum "Kirim".
  const [pendingFiles, setPendingFiles] = useState<ChatFileMeta[]>([]);
  const [uploadingCount, setUploadingCount] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadFile = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.upload<ChatFileMeta>(`/chat/channels/${activeChannel}/files`, formData);
    },
    onSuccess: (meta) => setPendingFiles((prev) => [...prev, meta]),
  });

  async function handleFilesSelected(fileList: FileList | null) {
    if (!fileList || !activeChannel) return;
    const files = Array.from(fileList);
    setUploadingCount((n) => n + files.length);
    for (const file of files) {
      try {
        await uploadFile.mutateAsync(file);
      } catch {
        // error sudah tampil lewat state uploadFile.isError; lanjut file berikutnya
      } finally {
        setUploadingCount((n) => n - 1);
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removePendingFile(id: string) {
    setPendingFiles((prev) => prev.filter((f) => f.id !== id));
  }

  const addReaction = useMutation({
    mutationFn: ({ messageId, emoji }: { messageId: string; emoji: string }) =>
      api.post<{ message_id: string; emoji: string; active: boolean }>(
        `/chat/messages/${messageId}/react`,
        { emoji }
      ),
    onSuccess: (result) => {
      patchMessageInCache(result.message_id, (m) => {
        const current = m.reactions[result.emoji] ?? 0;
        const nextCount = result.active ? current + 1 : Math.max(0, current - 1);
        const reactions = { ...m.reactions };
        if (nextCount > 0) reactions[result.emoji] = nextCount;
        else delete reactions[result.emoji];
        return { ...m, reactions };
      });
    },
  });

  const deleteMessage = useMutation({
    mutationFn: (messageId: string) => api.delete(`/chat/messages/${messageId}`),
    onSuccess: (_data, messageId) => removeMessageFromCache(messageId),
  });

  const editMessage = useMutation({
    mutationFn: ({ messageId, content }: { messageId: string; content: string }) =>
      api.patch<MessageRow>(`/chat/messages/${messageId}`, { content }),
    onSuccess: (updated) => patchMessageInCache(updated.id, () => updated),
  });

  const markRead = useMutation({
    mutationFn: (channelId: string) => api.post(`/chat/channels/${channelId}/read-all`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-channels"] }),
  });

  // Pinned posts
  const [showPinned, setShowPinned] = useState(false);
  const pinnedPosts = useQuery({
    queryKey: ["chat-pinned", activeChannel],
    queryFn: () => api.get<MessageRow[]>(`/chat/channels/${activeChannel}/pinned`),
    enabled: showPinned && Boolean(activeChannel),
  });
  const togglePin = useMutation({
    mutationFn: (messageId: string) =>
      api.post<{ message_id: string; is_pinned: boolean }>(`/chat/messages/${messageId}/pin`, {}),
    onSuccess: (result) => {
      patchMessageInCache(result.message_id, (m) => ({ ...m, is_pinned: result.is_pinned }));
      qc.invalidateQueries({ queryKey: ["chat-pinned", activeChannel] });
    },
  });

  // Preferensi notifikasi per channel (notify_level: all | mentions | none)
  const setNotifyLevel = useMutation({
    mutationFn: ({ channelId, level }: { channelId: string; level: NotifyLevel }) =>
      api.put(`/chat/channels/${channelId}/notify-level`, { level }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-channels"] }),
  });

  const handleAction = useMutation({
    mutationFn: ({ messageId, actionId }: { messageId: string; actionId: string }) =>
      api.post(`/chat/messages/${messageId}/actions/${actionId}`, {}),
    onSuccess: () => {
      // Aksi kartu memicu balasan sistem baru (async) -- merge, bukan
      // refetch mentah, supaya tidak menabrak bug jendela-geser.
      mergeLatestIntoCache();
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
    onSuccess: () => mergeLatestIntoCache(),
  });

  // `firstItemIndex` ala pola resmi Virtuoso untuk chat: berkurang sebanyak
  // jumlah pesan yang baru di-prepend setiap kali halaman histori lebih
  // lama termuat, supaya Virtuoso mempertahankan posisi baca tanpa hitung
  // manual scrollTop/scrollHeight (beda dari pendekatan DOM manual sebelum
  // virtualisasi ini).
  const [firstItemIndex, setFirstItemIndex] = useState(VIRTUOSO_START_INDEX);
  const loadedPageCountRef = useRef(0);

  useEffect(() => {
    setFirstItemIndex(VIRTUOSO_START_INDEX);
    loadedPageCountRef.current = 0;
  }, [activeChannel, threadParent]);

  useEffect(() => {
    const pageCount = messagePages?.pages.length ?? 0;
    if (pageCount > loadedPageCountRef.current && loadedPageCountRef.current > 0) {
      const olderPage = messagePages!.pages[messagePages!.pages.length - 1];
      setFirstItemIndex((idx) => idx - olderPage.items.length);
    }
    loadedPageCountRef.current = pageCount;
  }, [messagePages]);

  function handleStartReached() {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  }

  // Membuka channel = "melihat" — reset unread/mention counter di server
  // (model counter ala Mattermost, lihat backend/app/modules/chat/service.py).
  useEffect(() => {
    if (!activeChannel) return;
    markRead.mutate(activeChannel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChannel]);

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
      ws.onmessage = (evt) => {
        qc.invalidateQueries({ queryKey: ["chat-channels"] });
        let eventChannelId: string | null = null;
        try {
          eventChannelId = (JSON.parse(evt.data) as { channel_id?: string }).channel_id ?? null;
        } catch {
          // payload tak terduga — tetap refetch pesan channel aktif
        }
        if (!eventChannelId || eventChannelId === activeChannel) {
          // Merge, BUKAN invalidate/refetch mentah -- lihat catatan panjang
          // di dekat definisi useInfiniteQuery soal bug jendela-geser.
          mergeLatestIntoCache();
          // Channel aktif sedang dilihat — jangan biarkan unread menumpuk
          // untuk pesan yang masuk saat channel ini terbuka.
          if (activeChannel) markRead.mutate(activeChannel);
        }
      };
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
    if (!activeChannel || (!content && pendingFiles.length === 0)) return;
    sendMessage.mutate({
      content,
      parent_id: threadParent || undefined,
      file_ids: pendingFiles.map((f) => f.id),
    });
  }

  function renderMessage(m: MessageRow) {
    return (
      <div className="px-4 py-1">
        <div className="group rounded px-2 py-1.5 transition-colors hover:bg-[var(--hover)]">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-xs font-medium" style={{ color: "var(--text-muted)" }}>
              {m.sender_id.slice(0, 8)}… · {new Date(m.created_at).toLocaleString("id-ID")}
              {m.edited_at && <span className="ml-1 italic">diedit</span>}
              {m.is_pinned && (
                <span className="ml-1.5 inline-flex items-center gap-0.5" style={{ color: "var(--accent)" }}>
                  <Pin className="h-3 w-3" /> disematkan
                </span>
              )}
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

          {m.content && (
            <p className="mt-0.5 whitespace-pre-wrap break-words text-sm" style={{ color: "var(--text)" }}>
              {m.content}
            </p>
          )}
          {m.files.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-2">
              {m.files.map((f) =>
                f.mime_type.startsWith("image/") ? (
                  <a key={f.id} href={f.url} target="_blank" rel="noreferrer">
                    <img
                      src={f.url}
                      alt={f.file_name}
                      className="max-h-48 rounded-md object-cover"
                      style={{ border: "1px solid var(--border)" }}
                    />
                  </a>
                ) : (
                  <a
                    key={f.id}
                    href={f.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs hover:opacity-80"
                    style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
                  >
                    <FileText className="h-3.5 w-3.5 shrink-0" />
                    <span className="max-w-[12rem] truncate" style={{ color: "var(--text)" }}>
                      {f.file_name}
                    </span>
                    <span style={{ color: "var(--text-muted)" }}>{formatFileSize(f.file_size)}</span>
                  </a>
                )
              )}
            </div>
          )}
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
            <button
              onClick={() => togglePin.mutate(m.id)}
              className="ml-auto text-[11px] hover:opacity-80"
              style={{ color: "var(--text-muted)" }}
              title={m.is_pinned ? "Lepas sematan" : "Sematkan pesan"}
            >
              {m.is_pinned ? <PinOff className="h-3 w-3" /> : <Pin className="h-3 w-3" />}
            </button>
            {m.is_own && (
              <>
                <button
                  onClick={() =>
                    promptToast(
                      "Edit pesan:",
                      (next) => editMessage.mutate({ messageId: m.id, content: next }),
                      { defaultValue: m.content }
                    )
                  }
                  className="text-[11px] hover:opacity-80"
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
      </div>
    );
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
                  {ch.notify_level === "none" && (
                    <span title="Dibisukan">
                      <BellOff className="h-3 w-3 shrink-0" />
                    </span>
                  )}
                </span>
                {ch.mention_count > 0 ? (
                  <span
                    className="ml-1 shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-bold text-[var(--accent-contrast)]"
                    style={{ backgroundColor: "var(--accent)" }}
                    title="Ada mention untuk Anda"
                  >
                    @{ch.mention_count}
                  </span>
                ) : (
                  ch.unread_count > 0 && (
                    <span
                      className="ml-1 shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                      style={{ backgroundColor: "var(--hover)", color: "var(--text-muted)" }}
                    >
                      {ch.unread_count}
                    </span>
                  )
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
                <>
                  <button
                    onClick={() => setShowDigest((v) => !v)}
                    className="btn-secondary flex items-center gap-1 py-0.5 text-xs"
                    title="Digest harian: approval menunggu, SLA, kontrak, invoice"
                  >
                    <ClipboardList className="h-3 w-3" /> Digest
                  </button>
                  <button
                    onClick={() => setShowPinned((v) => !v)}
                    className="btn-secondary flex items-center gap-1 py-0.5 text-xs"
                    title="Pesan yang disematkan di channel ini"
                  >
                    <Pin className="h-3 w-3" /> Disematkan
                  </button>
                </>
              )}
              {activeChannel && !threadParent && activeMeta && (
                <select
                  value={activeMeta.notify_level}
                  onChange={(e) =>
                    setNotifyLevel.mutate({
                      channelId: activeChannel,
                      level: e.target.value as NotifyLevel,
                    })
                  }
                  className="input py-0.5 text-xs"
                  title="Preferensi notifikasi channel ini"
                >
                  <option value="all">🔔 Semua pesan</option>
                  <option value="mentions">@ Hanya mention</option>
                  <option value="none">🔕 Bisukan</option>
                </select>
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

          {showPinned && !threadParent && (
            <div className="max-h-52 overflow-y-auto border-b px-4 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}>
              <p className="mb-1 flex items-center justify-between text-xs font-semibold" style={{ color: "var(--text)" }}>
                <span className="flex items-center gap-1.5">
                  <Pin className="h-3.5 w-3.5" /> Pesan disematkan
                </span>
                <button onClick={() => setShowPinned(false)} style={{ color: "var(--accent)" }}>tutup</button>
              </p>
              {pinnedPosts.isLoading && <p className="text-xs" style={{ color: "var(--text-muted)" }}>Memuat…</p>}
              {(pinnedPosts.data ?? []).map((m) => (
                <div key={m.id} className="flex items-start justify-between gap-2 py-1 text-xs" style={{ color: "var(--text)" }}>
                  <span className="truncate">{m.content || "(lampiran tanpa teks)"}</span>
                  <button
                    onClick={() => togglePin.mutate(m.id)}
                    className="shrink-0 hover:opacity-80"
                    style={{ color: "var(--text-muted)" }}
                    title="Lepas sematan"
                  >
                    <PinOff className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {pinnedPosts.data && pinnedPosts.data.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada pesan yang disematkan.</p>
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

          <div className="flex-1" style={{ minHeight: 0 }}>
            {messages.length === 0 ? (
              <p className="py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                Belum ada pesan. Mulai percakapan!
              </p>
            ) : (
              <Virtuoso
                key={`${activeChannel}:${threadParent ?? "root"}`}
                ref={virtuosoRef}
                style={{ height: "100%" }}
                data={messages}
                firstItemIndex={firstItemIndex}
                initialTopMostItemIndex={messages.length - 1}
                startReached={handleStartReached}
                followOutput={(isAtBottom) => (isAtBottom ? "smooth" : false)}
                alignToBottom
                computeItemKey={(_index, m) => m.id}
                components={{
                  Header: () => (
                    <>
                      {isFetchingNextPage && (
                        <p className="py-1 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                          Memuat pesan lebih lama…
                        </p>
                      )}
                      {!isFetchingNextPage && hasNextPage === false && (
                        <p className="py-2 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                          — Awal percakapan —
                        </p>
                      )}
                    </>
                  ),
                  Footer: () => <div style={{ height: 8 }} />,
                }}
                itemContent={(_index, m) => renderMessage(m)}
              />
            )}
          </div>

          <form
            onSubmit={(e) => {
              handleSend(e);
              setMentionQuery(null);
            }}
            className="relative flex flex-col gap-2 px-4 py-3"
            style={{ borderTop: "1px solid var(--border)" }}
          >
            {(pendingFiles.length > 0 || uploadingCount > 0) && (
              <div className="flex flex-wrap gap-1.5">
                {pendingFiles.map((f) => (
                  <span
                    key={f.id}
                    className="flex items-center gap-1 rounded px-2 py-1 text-xs"
                    style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
                  >
                    <FileText className="h-3 w-3 shrink-0" />
                    <span className="max-w-[10rem] truncate">{f.file_name}</span>
                    <button
                      type="button"
                      onClick={() => removePendingFile(f.id)}
                      className="shrink-0 hover:opacity-70"
                      title="Batalkan lampiran"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                {uploadingCount > 0 && (
                  <span className="flex items-center px-2 py-1 text-xs" style={{ color: "var(--text-muted)" }}>
                    Mengunggah {uploadingCount} file…
                  </span>
                )}
              </div>
            )}
            <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              disabled={!activeChannel}
              onChange={(e) => handleFilesSelected(e.target.files)}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={!activeChannel}
              className="btn-secondary px-2.5"
              title="Lampirkan file"
            >
              <Paperclip className="h-4 w-4" />
            </button>
            <div className="relative flex-1">
              <input
                ref={inputRef}
                name="content"
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
            <button
              disabled={!activeChannel || sendMessage.isPending || uploadingCount > 0}
              className="btn"
            >
              Kirim
            </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
