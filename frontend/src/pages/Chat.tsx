import { FormEvent, KeyboardEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { api } from "../api/client";
import {
  ArrowLeft,
  AtSign,
  Bell,
  BellOff,
  ChevronDown,
  ClipboardList,
  FileText,
  Hash,
  Lock,
  Megaphone,
  MessageCircle,
  MessageSquareReply,
  Paperclip,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Search,
  SendHorizontal,
  SmilePlus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { confirmToast, promptToast } from "../components/ui";

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
  sender_name: string;
  sender_role: string | null;
  is_bot: boolean;
  reply_count: number;
  my_reactions: string[];
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

// Pesan berurutan dari pengirim yang sama dalam jendela ini digabung
// (tanpa ulang avatar/nama) -- pola Slack/Mattermost, supaya percakapan
// terbaca sebagai paragraf, bukan tumpukan kartu identik.
const GROUP_WINDOW_MS = 5 * 60 * 1000;

const NOTIFY_OPTIONS: { value: NotifyLevel; label: string; hint: string }[] = [
  { value: "all", label: "Semua pesan", hint: "Setiap pesan baru dihitung belum dibaca" },
  { value: "mentions", label: "Hanya mention", hint: "Notifikasi hanya saat Anda di-@" },
  { value: "none", label: "Bisukan", hint: "Tidak ada notifikasi dari channel ini" },
];

// Pengelompokan sidebar dari nama channel otomatis (lihat backend
// chat/service.py::ensure_*_channel) -- tanpa ini 30+ channel "JO: …"
// menenggelamkan channel diskusi & proyek dalam satu daftar datar.
const GROUPS = [
  { key: "umum", label: "Channel" },
  { key: "dm", label: "Pesan langsung" },
  { key: "proyek", label: "Proyek klien" },
  { key: "payroll", label: "Payroll" },
  { key: "jo", label: "Job order" },
] as const;
type GroupKey = (typeof GROUPS)[number]["key"];

function channelGroup(ch: ChannelRow): { key: GroupKey; display: string } {
  if (ch.channel_type === "dm") return { key: "dm", display: ch.name };
  if (ch.name.startsWith("JO: ")) return { key: "jo", display: ch.name.slice(4) };
  if (ch.name.startsWith("Proyek: ")) return { key: "proyek", display: ch.name.slice(8) };
  if (/^payroll\b/i.test(ch.name)) return { key: "payroll", display: ch.name };
  return { key: "umum", display: ch.name };
}

const AVATAR_TONES = [
  "var(--cat-crm)",
  "var(--cat-recruitment)",
  "var(--cat-workforce)",
  "var(--cat-finance)",
  "var(--cat-administration)",
];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}

function formatFull(iso: string): string {
  return new Date(iso).toLocaleString("id-ID", { dateStyle: "full", timeStyle: "short" });
}

function dayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function dayLabel(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (dayKey(d.toISOString()) === dayKey(today.toISOString())) return "Hari ini";
  if (dayKey(d.toISOString()) === dayKey(yesterday.toISOString())) return "Kemarin";
  return d.toLocaleDateString("id-ID", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: d.getFullYear() === today.getFullYear() ? undefined : "numeric",
  });
}

/** Sorot token @mention di isi pesan (tampilan saja, tanpa ubah data). */
function renderContent(text: string): ReactNode {
  const parts = text.split(/(@[\w.-]+)/g);
  return parts.map((part, i) =>
    part.startsWith("@") && part.length > 1 ? (
      <span
        key={i}
        className="rounded px-0.5 font-medium"
        style={{ backgroundColor: "var(--accent-tint)", color: "var(--accent)" }}
      >
        {part}
      </span>
    ) : (
      part
    )
  );
}

function Avatar({ name, isBot, size = 36 }: { name: string; isBot?: boolean; size?: number }) {
  if (isBot) {
    return (
      <span
        className="flex shrink-0 items-center justify-center rounded-lg"
        style={{
          width: size,
          height: size,
          backgroundColor: "var(--accent)",
          color: "var(--accent-contrast)",
        }}
        aria-hidden
      >
        <Sparkles className="h-4 w-4" />
      </span>
    );
  }
  const tone = AVATAR_TONES[hashString(name) % AVATAR_TONES.length];
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-lg text-xs font-semibold"
      style={{
        width: size,
        height: size,
        // Huruf pakai --text: warna kategori langsung di atas tint-nya
        // sendiri cuma ~2.3:1 di light mode (terukur). Warna identitas
        // tetap terbawa lewat latar + garis tepi.
        color: "var(--text)",
        backgroundColor: `color-mix(in srgb, ${tone} 22%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${tone} 35%, transparent)`,
      }}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}

function ChannelIcon({ type, className }: { type: string; className?: string }) {
  if (type === "private") return <Lock className={className} />;
  if (type === "broadcast") return <Megaphone className={className} />;
  if (type === "dm") return <AtSign className={className} />;
  return <Hash className={className} />;
}

function IconButton({
  label,
  active,
  onClick,
  children,
  disabled,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      aria-pressed={active}
      className="flex h-8 w-8 items-center justify-center rounded-md transition-colors hover:bg-[var(--hover)] disabled:opacity-40"
      style={{
        color: active ? "var(--accent)" : "var(--text-muted)",
        backgroundColor: active ? "var(--accent-tint)" : undefined,
      }}
    >
      {children}
    </button>
  );
}

/** Panel lipat di bawah header percakapan (hasil cari, disematkan, digest). */
function Drawer({
  icon,
  title,
  onClose,
  children,
}: {
  icon: ReactNode;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div
      className="max-h-60 overflow-y-auto px-4 py-3"
      style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--bg)" }}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--text)" }}>
          {icon}
          {title}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 hover:bg-[var(--hover)]"
          style={{ color: "var(--text-muted)" }}
          aria-label={`Tutup ${title}`}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      {children}
    </div>
  );
}

export default function Chat() {
  const qc = useQueryClient();
  const [activeChannel, setActiveChannel] = useState<string | null>(null);
  const [threadParent, setThreadParent] = useState<string | null>(null);
  const [threadRoot, setThreadRoot] = useState<MessageRow | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [creatingChannel, setCreatingChannel] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<GroupKey>>(new Set());
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [reactPickerFor, setReactPickerFor] = useState<string | null>(null);
  const [notifyMenuOpen, setNotifyMenuOpen] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const virtuosoRef = useRef<VirtuosoHandle>(null);

  const { data: channels, isLoading: channelsLoading } = useQuery({
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
    isLoading: messagesLoading,
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

  // Metadata tampilan per pesan: pemisah hari & penggabungan pesan
  // berurutan dari pengirim yang sama.
  const layoutMeta = useMemo(() => {
    const meta = new Map<string, { showDay: boolean; compact: boolean }>();
    messages.forEach((m, i) => {
      const prev = messages[i - 1];
      const showDay = !prev || dayKey(prev.created_at) !== dayKey(m.created_at);
      const compact =
        !showDay &&
        !!prev &&
        prev.sender_id === m.sender_id &&
        prev.message_type !== "card" &&
        m.message_type !== "card" &&
        new Date(m.created_at).getTime() - new Date(prev.created_at).getTime() < GROUP_WINDOW_MS;
      meta.set(m.id, { showDay, compact });
    });
    return meta;
  }, [messages]);

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

  const { data: searchResults, isFetching: searching } = useQuery({
    queryKey: ["chat-search", searchQuery, activeChannel],
    queryFn: () =>
      api.get<MessageRow[]>(
        `/chat/search?q=${encodeURIComponent(searchQuery)}${activeChannel ? `&channel_id=${activeChannel}` : ""}`
      ),
    enabled: searchOpen && searchQuery.trim().length >= 2,
  });

  const { data: mentionResults } = useQuery({
    queryKey: ["mention-search", mentionQuery],
    queryFn: () => api.get<{ id: string; full_name: string; email: string }[]>(`/chat/users/search?q=${encodeURIComponent(mentionQuery || "")}`),
    enabled: mentionQuery !== null,
  });
  const mentionOpen = mentionQuery !== null && (mentionResults ?? []).length > 0;

  const createChannel = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<{ id: string; name: string }>("/chat/channels", body),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["chat-channels"] });
      setCreatingChannel(false);
      openChannel(created.id);
    },
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
      if (inputRef.current) {
        inputRef.current.value = "";
        autoGrow(inputRef.current);
      }
      setPendingFiles([]);
      virtuosoRef.current?.scrollToIndex({ index: "LAST", align: "end", behavior: "smooth" });
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
        // error tampil lewat uploadFile.isError; lanjut file berikutnya
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
        const mine = new Set(m.my_reactions ?? []);
        if (result.active) mine.add(result.emoji);
        else mine.delete(result.emoji);
        return { ...m, reactions, my_reactions: [...mine] };
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
  // manual scrollTop/scrollHeight.
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

  // Buka channel/thread = langsung di pesan terbaru. Tinggi item (kartu,
  // lampiran, header "Awal dari…") baru terukur setelah render pertama,
  // jadi `initialTopMostItemIndex` saja berhenti di atas. `scrollToIndex`
  // yang dipanggil terlalu dini malah membuat Virtuoso merender NOL item
  // sampai data berubah (terukur di browser). Maka: setiap kali tinggi
  // list berubah dalam ~1,5 dtk pertama setelah channel dibuka, geser
  // elemen scroller-nya langsung ke dasar -- memicu event scroll biasa
  // sehingga Virtuoso menghitung ulang rentang item seperti normal.
  const scrollerElRef = useRef<HTMLElement | null>(null);
  const initialScrollUntilRef = useRef(0);
  useEffect(() => {
    initialScrollUntilRef.current = Date.now() + 1500;
  }, [activeChannel, threadParent]);

  function handleListHeightChanged() {
    const el = scrollerElRef.current;
    if (el && Date.now() < initialScrollUntilRef.current) el.scrollTop = el.scrollHeight;
  }

  // Callback tinggi list di atas tidak selalu terpanggil saat mount (lihat
  // catatan initialItemCount), jadi dorong juga eksplisit beberapa kali
  // selama jendela awal -- item sudah ada di DOM, scrollTop pasti berlaku.
  const hasMessages = messages.length > 0;
  useEffect(() => {
    if (!activeChannel || !hasMessages) return;
    const timers = [0, 60, 200, 500].map((ms) =>
      setTimeout(() => {
        const el = scrollerElRef.current;
        if (el && Date.now() < initialScrollUntilRef.current) el.scrollTop = el.scrollHeight;
      }, ms)
    );
    return () => timers.forEach(clearTimeout);
  }, [activeChannel, threadParent, hasMessages]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChannel]);

  // Tutup popover (reaksi / notifikasi) saat klik di luar atau Escape.
  useEffect(() => {
    if (!reactPickerFor && !notifyMenuOpen) return;
    function close(e: Event) {
      if (e instanceof globalThis.KeyboardEvent && e.key !== "Escape") return;
      if (e.type === "mousedown" && (e.target as HTMLElement).closest("[data-popover]")) return;
      setReactPickerFor(null);
      setNotifyMenuOpen(false);
    }
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [reactPickerFor, notifyMenuOpen]);

  function openChannel(id: string) {
    setActiveChannel(id);
    setThreadParent(null);
    setThreadRoot(null);
    setShowPinned(false);
    setShowDigest(false);
    setSearchOpen(false);
    setSearchQuery("");
  }

  function openThread(m: MessageRow) {
    setThreadParent(m.parent_id ?? m.id);
    setThreadRoot(m.parent_id ? null : m);
    setShowPinned(false);
    setShowDigest(false);
    setSearchOpen(false);
  }

  function closeThread() {
    setThreadParent(null);
    setThreadRoot(null);
  }

  function autoGrow(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

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

  function handleComposerKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter kirim, Shift+Enter baris baru; jangan kirim saat IME sedang
    // menyusun kata atau saat daftar mention terbuka.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && !mentionOpen) {
      e.preventDefault();
      formRef.current?.requestSubmit();
    }
    if (e.key === "Escape" && mentionQuery !== null) setMentionQuery(null);
  }

  function renderCard(m: MessageRow) {
    if (m.message_type !== "card" || !m.card_data) return null;
    return (
      <div
        className="mt-1.5 max-w-lg overflow-hidden rounded-lg"
        style={{
          border: "1px solid var(--border)",
          borderLeft: "3px solid var(--accent)",
          backgroundColor: "var(--bg-elevated)",
        }}
      >
        <div className="px-3.5 py-3">
          <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            {m.card_data.title}
          </p>
          {m.card_data.body && (
            <p className="mt-1 text-[13px] tabular-nums" style={{ color: "var(--text-muted)" }}>
              {m.card_data.body}
            </p>
          )}
        </div>
        {m.actions && m.actions.length > 0 && (
          <div
            className="flex flex-wrap gap-2 px-3.5 py-2.5"
            style={{ borderTop: "1px solid var(--border)", backgroundColor: "var(--bg)" }}
          >
            {m.actions.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => handleAction.mutate({ messageId: m.id, actionId: a.id })}
                disabled={handleAction.isPending}
                className={`${a.style === "primary" ? "btn" : "btn-secondary"} px-3 py-1.5 text-xs`}
              >
                {a.label}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  function renderMessage(m: MessageRow) {
    const meta = layoutMeta.get(m.id) ?? { showDay: false, compact: false };
    const reactionEntries = Object.entries(m.reactions);
    const mine = new Set(m.my_reactions ?? []);
    // Kartu sistem mengulang judulnya sebagai teks pesan -- jangan tampil ganda.
    const hideText =
      m.message_type === "card" && m.card_data && m.content.trim() === m.card_data.title.trim();
    const pickerOpen = reactPickerFor === m.id;

    return (
      <div>
        {meta.showDay && (
          <div className="flex items-center gap-3 px-4 pb-1 pt-4" role="separator">
            <span className="h-px flex-1" style={{ backgroundColor: "var(--border)" }} />
            <span className="text-[11px] font-semibold" style={{ color: "var(--text-muted)" }}>
              {dayLabel(m.created_at)}
            </span>
            <span className="h-px flex-1" style={{ backgroundColor: "var(--border)" }} />
          </div>
        )}
        <div
          className={`group relative flex gap-3 px-4 transition-colors hover:bg-[var(--hover)] focus-within:bg-[var(--hover)] ${
            meta.compact ? "py-0.5" : "pb-1 pt-2.5"
          }`}
        >
          <div className="w-9 shrink-0">
            {meta.compact ? (
              <span
                className="block pt-0.5 text-right text-[10px] tabular-nums opacity-0 transition-opacity group-hover:opacity-100"
                style={{ color: "var(--text-muted)" }}
                title={formatFull(m.created_at)}
              >
                {formatTime(m.created_at)}
              </span>
            ) : (
              <Avatar name={m.sender_name} isBot={m.is_bot} />
            )}
          </div>

          <div className="min-w-0 flex-1">
            {!meta.compact && (
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
                  {m.sender_name}
                </span>
                {m.is_bot && (
                  <span
                    className="rounded px-1 py-px text-[10px] font-semibold uppercase tracking-wide"
                    style={{ backgroundColor: "var(--accent-tint)", color: "var(--accent)" }}
                  >
                    AI
                  </span>
                )}
                <time
                  className="text-xs tabular-nums"
                  style={{ color: "var(--text-muted)" }}
                  dateTime={m.created_at}
                  title={formatFull(m.created_at)}
                >
                  {formatTime(m.created_at)}
                </time>
                {m.is_pinned && (
                  <span className="inline-flex items-center gap-0.5 text-xs" style={{ color: "var(--accent)" }}>
                    <Pin className="h-3 w-3" /> disematkan
                  </span>
                )}
              </div>
            )}

            {m.content && !hideText && (
              <p
                className="whitespace-pre-wrap break-words text-sm leading-relaxed"
                style={{ color: "var(--text)" }}
              >
                {renderContent(m.content)}
                {m.edited_at && (
                  <span className="ml-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                    (diedit)
                  </span>
                )}
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
                        className="max-h-56 max-w-xs rounded-lg object-cover"
                        style={{ border: "1px solid var(--border)" }}
                      />
                    </a>
                  ) : (
                    <a
                      key={f.id}
                      href={f.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex max-w-xs items-center gap-2.5 rounded-lg px-3 py-2 transition-colors hover:bg-[var(--hover)]"
                      style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
                    >
                      <span
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md"
                        style={{ backgroundColor: "var(--accent-tint)", color: "var(--accent)" }}
                      >
                        <FileText className="h-4 w-4" />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-medium" style={{ color: "var(--text)" }}>
                          {f.file_name}
                        </span>
                        <span className="block text-[11px]" style={{ color: "var(--text-muted)" }}>
                          {formatFileSize(f.file_size)}
                        </span>
                      </span>
                    </a>
                  )
                )}
              </div>
            )}

            {renderCard(m)}

            {reactionEntries.length > 0 && (
              <div className="mt-1.5 flex flex-wrap items-center gap-1">
                {reactionEntries.map(([emoji, count]) => {
                  const isMine = mine.has(emoji);
                  return (
                    <button
                      key={emoji}
                      type="button"
                      onClick={() => addReaction.mutate({ messageId: m.id, emoji })}
                      aria-pressed={isMine}
                      className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs tabular-nums transition-colors"
                      style={{
                        border: `1px solid ${isMine ? "var(--accent)" : "var(--border)"}`,
                        backgroundColor: isMine ? "var(--accent-tint)" : "var(--bg-elevated)",
                        color: isMine ? "var(--accent)" : "var(--text)",
                      }}
                    >
                      <span>{emoji}</span>
                      <span className="font-medium">{count}</span>
                    </button>
                  );
                })}
              </div>
            )}

            {!threadParent && m.reply_count > 0 && (
              <button
                type="button"
                onClick={() => openThread(m)}
                className="mt-1 flex items-center gap-1.5 rounded-md py-0.5 text-xs font-medium hover:underline"
                style={{ color: "var(--accent)" }}
              >
                <MessageSquareReply className="h-3.5 w-3.5" />
                {m.reply_count} balasan
              </button>
            )}
          </div>

          {/* Toolbar aksi -- muncul saat hover/fokus, bukan menumpuk permanen
              di bawah setiap pesan. */}
          <div
            data-popover
            className={`absolute -top-3 right-4 z-10 flex items-center gap-0.5 rounded-lg p-0.5 shadow-sm transition-opacity ${
              pickerOpen ? "opacity-100" : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
            }`}
            style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
          >
            <IconButton label="Beri reaksi" active={pickerOpen} onClick={() => setReactPickerFor(pickerOpen ? null : m.id)}>
              <SmilePlus className="h-4 w-4" />
            </IconButton>
            {!threadParent && (
              <IconButton label="Balas di thread" onClick={() => openThread(m)}>
                <MessageSquareReply className="h-4 w-4" />
              </IconButton>
            )}
            <IconButton label={m.is_pinned ? "Lepas sematan" : "Sematkan pesan"} onClick={() => togglePin.mutate(m.id)}>
              {m.is_pinned ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />}
            </IconButton>
            {m.is_own && m.message_type !== "card" && (
              <IconButton
                label="Edit pesan"
                onClick={() =>
                  promptToast("Edit pesan:", (next) => editMessage.mutate({ messageId: m.id, content: next }), {
                    defaultValue: m.content,
                  })
                }
              >
                <Pencil className="h-4 w-4" />
              </IconButton>
            )}
            {m.is_own && (
              <IconButton
                label="Hapus pesan"
                onClick={() => confirmToast("Hapus pesan ini?", () => deleteMessage.mutate(m.id))}
              >
                <Trash2 className="h-4 w-4" />
              </IconButton>
            )}
            {pickerOpen && (
              <div
                className="absolute right-0 top-full mt-1 flex gap-0.5 rounded-lg p-1 shadow-lg"
                style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
              >
                {EMOJI_REACTIONS.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    onClick={() => {
                      addReaction.mutate({ messageId: m.id, emoji });
                      setReactPickerFor(null);
                    }}
                    className="flex h-8 w-8 items-center justify-center rounded-md text-base transition-transform hover:scale-110 hover:bg-[var(--hover)]"
                    aria-label={`Reaksi ${emoji}`}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ---------- Sidebar channel ----------

  const grouped = useMemo(() => {
    const q = channelFilter.trim().toLowerCase();
    const map = new Map<GroupKey, { ch: ChannelRow; display: string }[]>();
    for (const ch of channels ?? []) {
      if (q && !ch.name.toLowerCase().includes(q)) continue;
      const g = channelGroup(ch);
      if (!map.has(g.key)) map.set(g.key, []);
      map.get(g.key)!.push({ ch, display: g.display });
    }
    return GROUPS.filter((g) => map.has(g.key)).map((g) => ({ ...g, items: map.get(g.key)! }));
  }, [channels, channelFilter]);

  function toggleGroup(key: GroupKey) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const activeMeta = channels?.find((c) => c.id === activeChannel);
  const activeDisplay = activeMeta ? channelGroup(activeMeta).display : "";
  const notifyCurrent = NOTIFY_OPTIONS.find((o) => o.value === activeMeta?.notify_level);

  return (
    <div
      className="flex h-[calc(100vh-7rem)] min-h-[480px] overflow-hidden rounded-xl"
      style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
    >
      {/* ===== Sidebar channel ===== */}
      <aside
        className={`${activeChannel ? "hidden md:flex" : "flex"} w-full shrink-0 flex-col md:w-72`}
        style={{ borderRight: "1px solid var(--border)", backgroundColor: "var(--sidebar)" }}
      >
        <div className="flex h-14 items-center justify-between px-4" style={{ borderBottom: "1px solid var(--border)" }}>
          <h1 className="flex items-center gap-2 text-base font-semibold" style={{ color: "var(--text)" }}>
            <MessageCircle className="h-[18px] w-[18px]" style={{ color: "var(--accent)" }} />
            Chat
          </h1>
          <IconButton
            label={creatingChannel ? "Batal buat channel" : "Buat channel baru"}
            active={creatingChannel}
            onClick={() => setCreatingChannel((v) => !v)}
          >
            {creatingChannel ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          </IconButton>
        </div>

        <div className="space-y-2 p-3" style={{ borderBottom: "1px solid var(--border)" }}>
          {creatingChannel && (
            <form
              className="flex gap-1.5"
              onSubmit={(e) => {
                e.preventDefault();
                const name = String(new FormData(e.currentTarget).get("name") || "").trim();
                if (name) createChannel.mutate({ name });
              }}
            >
              <input
                name="name"
                required
                autoFocus
                placeholder="Nama channel baru"
                aria-label="Nama channel baru"
                className="input flex-1 py-1.5 text-sm"
              />
              <button className="btn px-3 py-1.5 text-xs" disabled={createChannel.isPending}>
                Buat
              </button>
            </form>
          )}
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2"
              style={{ color: "var(--text-muted)" }}
            />
            <input
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              placeholder="Cari channel"
              aria-label="Cari channel"
              className="input w-full py-1.5 pl-8 text-sm"
            />
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-2" aria-label="Daftar channel">
          {channelsLoading &&
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="mx-3 my-2 h-8 animate-pulse rounded-md" style={{ backgroundColor: "var(--hover)" }} />
            ))}
          {grouped.map((group) => {
            const isCollapsed = collapsed.has(group.key) && !channelFilter;
            const groupUnread = group.items.reduce((n, { ch }) => n + ch.unread_count + ch.mention_count, 0);
            return (
              <div key={group.key} className="mb-1">
                <button
                  type="button"
                  onClick={() => toggleGroup(group.key)}
                  className="flex w-full items-center gap-1 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide hover:opacity-80"
                  style={{ color: "var(--text-muted)" }}
                  aria-expanded={!isCollapsed}
                >
                  <ChevronDown className={`h-3 w-3 transition-transform ${isCollapsed ? "-rotate-90" : ""}`} />
                  <span className="flex-1 text-left">{group.label}</span>
                  {isCollapsed && groupUnread > 0 ? (
                    <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "var(--accent)" }} />
                  ) : (
                    <span className="font-normal tabular-nums">{group.items.length}</span>
                  )}
                </button>
                {!isCollapsed &&
                  group.items.map(({ ch, display }) => {
                    const isActive = activeChannel === ch.id;
                    const hasUnread = ch.unread_count > 0 || ch.mention_count > 0;
                    return (
                      <button
                        key={ch.id}
                        type="button"
                        onClick={() => openChannel(ch.id)}
                        aria-current={isActive ? "page" : undefined}
                        className="relative mx-2 flex w-[calc(100%-1rem)] items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-[var(--hover)]"
                        style={{ backgroundColor: isActive ? "var(--accent-tint)" : undefined }}
                      >
                        <ChannelIcon
                          type={ch.channel_type}
                          className="mt-0.5 h-3.5 w-3.5 shrink-0"
                        />
                        <span className="min-w-0 flex-1">
                          <span
                            className={`flex items-center gap-1 truncate text-sm ${hasUnread || isActive ? "font-semibold" : ""}`}
                            style={{ color: isActive ? "var(--accent)" : hasUnread ? "var(--text)" : "var(--text-muted)" }}
                          >
                            <span className="truncate">{display}</span>
                            {ch.notify_level === "none" && (
                              <BellOff className="h-3 w-3 shrink-0" aria-label="Dibisukan" />
                            )}
                          </span>
                          {ch.last_message_preview && (
                            <span className="mt-0.5 block truncate text-xs" style={{ color: "var(--text-muted)" }}>
                              {ch.last_message_preview}
                            </span>
                          )}
                        </span>
                        {ch.mention_count > 0 ? (
                          <span
                            className="mt-0.5 shrink-0 rounded-full px-1.5 py-px text-[10px] font-bold tabular-nums"
                            style={{ backgroundColor: "var(--accent)", color: "var(--accent-contrast)" }}
                            title={`${ch.mention_count} mention untuk Anda`}
                          >
                            @{ch.mention_count}
                          </span>
                        ) : (
                          ch.unread_count > 0 && (
                            <span
                              className="mt-0.5 shrink-0 rounded-full px-1.5 py-px text-[10px] font-semibold tabular-nums"
                              style={{ backgroundColor: "var(--accent-tint)", color: "var(--accent)" }}
                              title={`${ch.unread_count} pesan belum dibaca`}
                            >
                              {ch.unread_count}
                            </span>
                          )
                        )}
                      </button>
                    );
                  })}
              </div>
            );
          })}
          {!channelsLoading && grouped.length === 0 && (
            <p className="px-4 py-8 text-center text-xs" style={{ color: "var(--text-muted)" }}>
              {channelFilter ? `Tidak ada channel "${channelFilter}".` : "Belum ada channel."}
            </p>
          )}
        </nav>
      </aside>

      {/* ===== Percakapan ===== */}
      <section className={`${activeChannel ? "flex" : "hidden md:flex"} min-w-0 flex-1 flex-col`}>
        {!activeChannel ? (
          <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
            <span
              className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl"
              style={{ backgroundColor: "var(--accent-tint)", color: "var(--accent)" }}
            >
              <MessageCircle className="h-7 w-7" />
            </span>
            <h2 className="text-base font-semibold" style={{ color: "var(--text)" }}>
              Pilih channel untuk mulai
            </h2>
            <p className="mt-1 max-w-sm text-sm" style={{ color: "var(--text-muted)" }}>
              Channel proyek, job order, dan payroll dibuat otomatis. Sebut <b>@AEOS</b> untuk bertanya ke AI, atau
              ketik <b>/help</b> untuk daftar perintah.
            </p>
          </div>
        ) : (
          <>
            {/* Header percakapan */}
            <header
              className="flex h-14 shrink-0 items-center gap-2 px-3 md:px-4"
              style={{ borderBottom: "1px solid var(--border)" }}
            >
              <button
                type="button"
                onClick={() => (threadParent ? closeThread() : setActiveChannel(null))}
                className={`${threadParent ? "" : "md:hidden"} flex h-8 w-8 shrink-0 items-center justify-center rounded-md hover:bg-[var(--hover)]`}
                style={{ color: "var(--text-muted)" }}
                aria-label={threadParent ? "Kembali ke channel" : "Kembali ke daftar channel"}
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 truncate text-sm font-semibold" style={{ color: "var(--text)" }}>
                  {threadParent ? (
                    <>
                      <MessageSquareReply className="h-4 w-4 shrink-0" style={{ color: "var(--accent)" }} />
                      Thread
                      <span className="truncate font-normal" style={{ color: "var(--text-muted)" }}>
                        · {activeDisplay}
                      </span>
                    </>
                  ) : (
                    <>
                      <ChannelIcon type={activeMeta?.channel_type ?? "public"} className="h-4 w-4 shrink-0" />
                      <span className="truncate" title={activeMeta?.name}>
                        {activeMeta?.name}
                      </span>
                    </>
                  )}
                </p>
                {!threadParent && activeMeta && (
                  <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>
                    {activeMeta.member_count} anggota
                    {activeMeta.notify_level !== "all" && ` · ${notifyCurrent?.label.toLowerCase()}`}
                  </p>
                )}
              </div>

              <div className="flex shrink-0 items-center gap-0.5">
                {threadParent ? (
                  <button
                    type="button"
                    onClick={() => summarize.mutate(threadParent)}
                    disabled={summarize.isPending}
                    className="btn-secondary flex items-center gap-1.5 px-2.5 py-1 text-xs"
                    title="Rangkum thread jadi poin keputusan/tugas (@AEOS)"
                  >
                    <Sparkles className="h-3.5 w-3.5" style={{ color: "var(--accent)" }} />
                    {summarize.isPending ? "Merangkum…" : "Rangkum"}
                  </button>
                ) : (
                  <>
                    <IconButton label="Cari pesan" active={searchOpen} onClick={() => setSearchOpen((v) => !v)}>
                      <Search className="h-4 w-4" />
                    </IconButton>
                    <IconButton label="Pesan disematkan" active={showPinned} onClick={() => setShowPinned((v) => !v)}>
                      <Pin className="h-4 w-4" />
                    </IconButton>
                    <IconButton
                      label="Digest harian (approval, SLA, kontrak, invoice)"
                      active={showDigest}
                      onClick={() => setShowDigest((v) => !v)}
                    >
                      <ClipboardList className="h-4 w-4" />
                    </IconButton>
                    {activeMeta && (
                      <div className="relative" data-popover>
                        <IconButton
                          label={`Notifikasi: ${notifyCurrent?.label ?? ""}`}
                          active={notifyMenuOpen}
                          onClick={() => setNotifyMenuOpen((v) => !v)}
                        >
                          {activeMeta.notify_level === "none" ? (
                            <BellOff className="h-4 w-4" />
                          ) : activeMeta.notify_level === "mentions" ? (
                            <AtSign className="h-4 w-4" />
                          ) : (
                            <Bell className="h-4 w-4" />
                          )}
                        </IconButton>
                        {notifyMenuOpen && (
                          <div
                            role="menu"
                            className="absolute right-0 top-full z-20 mt-1 w-60 rounded-lg p-1 shadow-lg"
                            style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
                          >
                            {NOTIFY_OPTIONS.map((opt) => {
                              const selected = opt.value === activeMeta.notify_level;
                              return (
                                <button
                                  key={opt.value}
                                  type="button"
                                  role="menuitemradio"
                                  aria-checked={selected}
                                  onClick={() => {
                                    setNotifyLevel.mutate({ channelId: activeMeta.id, level: opt.value });
                                    setNotifyMenuOpen(false);
                                  }}
                                  className="flex w-full flex-col rounded-md px-2.5 py-2 text-left hover:bg-[var(--hover)]"
                                  style={{ backgroundColor: selected ? "var(--accent-tint)" : undefined }}
                                >
                                  <span
                                    className="text-sm font-medium"
                                    style={{ color: selected ? "var(--accent)" : "var(--text)" }}
                                  >
                                    {opt.label}
                                  </span>
                                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                                    {opt.hint}
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </header>

            {searchOpen && !threadParent && (
              <Drawer icon={<Search className="h-3.5 w-3.5" />} title="Cari di channel ini" onClose={() => setSearchOpen(false)}>
                <input
                  autoFocus
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Ketik minimal 2 huruf…"
                  aria-label="Kata kunci pencarian pesan"
                  className="input mb-2 w-full py-1.5 text-sm"
                />
                {searchQuery.trim().length >= 2 && (
                  <>
                    {searching && !searchResults && (
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        Mencari…
                      </p>
                    )}
                    {(searchResults ?? []).map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => openThread(m)}
                        className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-[var(--hover)]"
                        title="Buka di thread"
                      >
                        <Avatar name={m.sender_name ?? "?"} isBot={m.is_bot} size={24} />
                        <span className="min-w-0 flex-1">
                          <span className="flex items-baseline gap-2 text-xs">
                            <span className="font-semibold" style={{ color: "var(--text)" }}>
                              {m.sender_name}
                            </span>
                            <span style={{ color: "var(--text-muted)" }}>
                              {dayLabel(m.created_at)}, {formatTime(m.created_at)}
                            </span>
                          </span>
                          <span className="block truncate text-xs" style={{ color: "var(--text)" }}>
                            {m.content}
                          </span>
                        </span>
                      </button>
                    ))}
                    {searchResults && searchResults.length === 0 && (
                      <p className="py-2 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                        Tidak ada pesan yang cocok.
                      </p>
                    )}
                  </>
                )}
              </Drawer>
            )}

            {showPinned && !threadParent && (
              <Drawer icon={<Pin className="h-3.5 w-3.5" />} title="Pesan disematkan" onClose={() => setShowPinned(false)}>
                {pinnedPosts.isLoading && (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Memuat…
                  </p>
                )}
                {(pinnedPosts.data ?? []).map((m) => (
                  <div key={m.id} className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-[var(--hover)]">
                    <Avatar name={m.sender_name ?? "?"} isBot={m.is_bot} size={24} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-semibold" style={{ color: "var(--text)" }}>
                        {m.sender_name}
                      </span>
                      <span className="block truncate text-xs" style={{ color: "var(--text)" }}>
                        {m.content || m.card_data?.title || "(lampiran tanpa teks)"}
                      </span>
                    </span>
                    <IconButton label="Lepas sematan" onClick={() => togglePin.mutate(m.id)}>
                      <PinOff className="h-3.5 w-3.5" />
                    </IconButton>
                  </div>
                ))}
                {pinnedPosts.data && pinnedPosts.data.length === 0 && (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Belum ada pesan yang disematkan. Arahkan kursor ke pesan lalu klik ikon pin.
                  </p>
                )}
              </Drawer>
            )}

            {showDigest && !threadParent && (
              <Drawer
                icon={<ClipboardList className="h-3.5 w-3.5" />}
                title={`Digest harian${digest.data?.date ? ` · ${digest.data.date}` : ""}`}
                onClose={() => setShowDigest(false)}
              >
                {digest.isLoading && (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Menyusun…
                  </p>
                )}
                <ul className="space-y-1">
                  {(digest.data?.items ?? []).map((it, i) => (
                    <li key={i} className="flex gap-2 text-xs" style={{ color: "var(--text)" }}>
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full" style={{ backgroundColor: "var(--accent)" }} />
                      <span>
                        {it.detail}
                        {it.refs.length > 0 && (
                          <span style={{ color: "var(--text-muted)" }}> — {it.refs.join(", ")}</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
                {digest.data && digest.data.items.length === 0 && (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Tidak ada item penting hari ini.
                  </p>
                )}
              </Drawer>
            )}

            {/* Pesan induk thread, dipasang di atas daftar balasan */}
            {threadParent && threadRoot && (
              <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--bg)" }}>
                <div className="flex gap-3">
                  <Avatar name={threadRoot.sender_name} isBot={threadRoot.is_bot} />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>
                      {threadRoot.sender_name}{" "}
                      <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>
                        {dayLabel(threadRoot.created_at)}, {formatTime(threadRoot.created_at)}
                      </span>
                    </p>
                    <p className="line-clamp-3 whitespace-pre-wrap text-sm" style={{ color: "var(--text)" }}>
                      {renderContent(threadRoot.content || threadRoot.card_data?.title || "")}
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="flex-1" style={{ minHeight: 0 }}>
              {messagesLoading ? (
                <div className="space-y-4 p-4" aria-label="Memuat pesan">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="flex gap-3">
                      <div className="h-9 w-9 animate-pulse rounded-lg" style={{ backgroundColor: "var(--hover)" }} />
                      <div className="flex-1 space-y-2">
                        <div className="h-3 w-32 animate-pulse rounded" style={{ backgroundColor: "var(--hover)" }} />
                        <div className="h-3 w-3/4 animate-pulse rounded" style={{ backgroundColor: "var(--hover)" }} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                  <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
                    {threadParent ? "Belum ada balasan" : `Belum ada pesan di ${activeDisplay}`}
                  </p>
                  <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                    {threadParent
                      ? "Tulis balasan pertama di bawah."
                      : "Mulai dengan menyapa tim, atau ketik / untuk melihat perintah."}
                  </p>
                </div>
              ) : (
                <Virtuoso
                  key={`${activeChannel}:${threadParent ?? "root"}`}
                  ref={virtuosoRef}
                  scrollerRef={(el) => {
                    scrollerElRef.current = el instanceof HTMLElement ? el : null;
                  }}
                  totalListHeightChanged={handleListHeightChanged}
                  style={{ height: "100%" }}
                  data={messages}
                  firstItemIndex={firstItemIndex}
                  // Virtuoso 4.18 di layout ini merender NOL item saat mount
                  // (props data terisi, tapi rentang internal kosong sampai
                  // data berubah ~4 dtk kemudian -- terukur lewat fiber props
                  // di browser; bug lama sejak sebelum redesign). Paksa render
                  // awal; posisi dasar diurus handleListHeightChanged.
                  initialItemCount={Math.min(messages.length, 50)}
                  startReached={handleStartReached}
                  followOutput={(isAtBottom) => (isAtBottom ? "smooth" : false)}
                  alignToBottom
                  computeItemKey={(_index, m) => m.id}
                  components={{
                    Header: () => (
                      <>
                        {isFetchingNextPage && (
                          <p className="py-2 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                            Memuat pesan lebih lama…
                          </p>
                        )}
                        {!isFetchingNextPage && hasNextPage === false && !threadParent && (
                          <div className="px-4 pb-2 pt-6">
                            <p className="text-base font-semibold" style={{ color: "var(--text)" }}>
                              Awal dari {activeMeta?.name}
                            </p>
                            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                              Ini pesan paling awal di channel ini.
                            </p>
                          </div>
                        )}
                      </>
                    ),
                    Footer: () => <div style={{ height: 12 }} />,
                  }}
                  itemContent={(_index, m) => renderMessage(m)}
                />
              )}
            </div>

            {/* Composer */}
            <form
              ref={formRef}
              onSubmit={(e) => {
                handleSend(e);
                setMentionQuery(null);
              }}
              className="shrink-0 px-3 pb-3 pt-1 md:px-4"
            >
              <div
                className="relative rounded-xl transition-shadow focus-within:shadow-[0_0_0_3px_var(--accent-tint)]"
                style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
              >
                {(pendingFiles.length > 0 || uploadingCount > 0) && (
                  <div className="flex flex-wrap gap-1.5 px-3 pt-2.5">
                    {pendingFiles.map((f) => (
                      <span
                        key={f.id}
                        className="flex items-center gap-1.5 rounded-md py-1 pl-2 pr-1 text-xs"
                        style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg)" }}
                      >
                        <FileText className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--accent)" }} />
                        <span className="max-w-[10rem] truncate" style={{ color: "var(--text)" }}>
                          {f.file_name}
                        </span>
                        <button
                          type="button"
                          onClick={() => removePendingFile(f.id)}
                          className="rounded p-0.5 hover:bg-[var(--hover)]"
                          aria-label={`Batalkan lampiran ${f.file_name}`}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                    {uploadingCount > 0 && (
                      <span className="flex items-center px-1 text-xs" style={{ color: "var(--text-muted)" }}>
                        Mengunggah {uploadingCount} file…
                      </span>
                    )}
                    {uploadFile.isError && uploadingCount === 0 && (
                      <span className="flex items-center px-1 text-xs text-red-600 dark:text-red-400">
                        Sebagian file gagal diunggah (maks 10 MB).
                      </span>
                    )}
                  </div>
                )}

                {mentionOpen && (
                  <div
                    className="absolute bottom-full left-0 right-0 mb-2 max-h-48 overflow-y-auto rounded-lg p-1 shadow-lg"
                    style={{ backgroundColor: "var(--bg-elevated)", border: "1px solid var(--border)" }}
                  >
                    {(mentionResults ?? []).map((u) => (
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
                        className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-[var(--hover)]"
                      >
                        <Avatar name={u.full_name} size={24} />
                        <span className="text-sm" style={{ color: "var(--text)" }}>
                          {u.full_name}
                        </span>
                        <span className="ml-auto truncate text-xs" style={{ color: "var(--text-muted)" }}>
                          {u.email}
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex items-end gap-1 p-1.5">
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    onChange={(e) => handleFilesSelected(e.target.files)}
                  />
                  <IconButton label="Lampirkan file" onClick={() => fileInputRef.current?.click()}>
                    <Paperclip className="h-4 w-4" />
                  </IconButton>
                  <textarea
                    ref={inputRef}
                    name="content"
                    rows={1}
                    aria-label={threadParent ? "Tulis balasan" : `Kirim pesan ke ${activeMeta?.name ?? "channel"}`}
                    placeholder={threadParent ? "Balas di thread…" : `Kirim pesan ke ${activeDisplay}`}
                    className="max-h-40 min-h-[32px] flex-1 resize-none bg-transparent px-1.5 py-1.5 text-sm leading-5 outline-none"
                    style={{ color: "var(--text)" }}
                    onKeyDown={handleComposerKey}
                    onChange={(e) => {
                      autoGrow(e.currentTarget);
                      const val = e.target.value;
                      const atIdx = val.lastIndexOf("@");
                      if (atIdx >= 0) {
                        const after = val.slice(atIdx + 1).split(/\s/)[0];
                        if (/^[a-zA-Z0-9._-]*$/.test(after) && !/\s/.test(val.slice(atIdx + 1))) setMentionQuery(after);
                        else setMentionQuery(null);
                      } else setMentionQuery(null);
                    }}
                  />
                  <button
                    type="submit"
                    disabled={sendMessage.isPending || uploadingCount > 0}
                    className="btn flex h-8 w-8 shrink-0 items-center justify-center p-0"
                    aria-label="Kirim pesan"
                    title="Kirim (Enter)"
                  >
                    <SendHorizontal className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <p className="mt-1.5 hidden px-1 text-[11px] md:block" style={{ color: "var(--text-muted)" }}>
                <b>Enter</b> kirim · <b>Shift+Enter</b> baris baru · <b>@</b> mention · <b>@AEOS</b> tanya AI ·{" "}
                <b>/help</b> perintah
              </p>
            </form>
          </>
        )}
      </section>
    </div>
  );
}
