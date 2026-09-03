import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { api } from "../api/client";
import TiptapEditor from "../components/editor/TiptapEditor";

interface PageRow {
  id: string;
  parent_id: string | null;
  title: string;
  icon: string;
  updated_at: string | null;
}

interface PageDetail extends PageRow {
  content: string;
}

// D3: emoji picker sederhana — daftar statis cukup (plan Fase D).
const EMOJIS = [
  "📄", "📘", "📗", "📒", "💡", "🚀", "🎯", "🧲",
  "💼", "📊", "🗓️", "✅", "🔥", "⭐", "🧠", "🏗️",
  "🧾", "💬", "🔔", "🎨", "🧪", "📌", "⚙️", "🤝",
  "🏢", "🧑‍💻", "💰", "🔒", "📈", "🗂️",
];

/** D1: konten legacy teks pola → HTML paragraf; HTML dibiarkan apa adanya. */
function toEditorHtml(raw: string | undefined): string {
  const text = raw ?? "";
  if (/^\s*</.test(text)) return text;
  if (!text.trim()) return "<p></p>";
  return text
    .split(/\r?\n/)
    .map((line) =>
      line.trim()
        ? `<p>${line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p>`
        : ""
    )
    .join("");
}

export default function Pages() {
  const params = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pageId = params.id ?? null;

  const [title, setTitle] = useState<string | null>(null);
  const [icon, setIcon] = useState<string | null>(null);
  const [contentHtml, setContentHtml] = useState("");
  const [preview, setPreview] = useState(false);
  const [iconPickerOpen, setIconPickerOpen] = useState(false);

  const pages = useQuery({
    queryKey: ["pages"],
    queryFn: () => api.get<PageRow[]>("/pages"),
  });

  const detail = useQuery({
    queryKey: ["pages", pageId],
    queryFn: () => api.get<PageDetail>(`/pages/${pageId}`),
    enabled: Boolean(pageId),
  });

  useEffect(() => {
    if (detail.data) {
      setTitle(detail.data.title);
      setIcon(detail.data.icon);
      setContentHtml(toEditorHtml(detail.data.content));
      setPreview(false);
    }
  }, [detail.data]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["pages"] });
  };

  const createPage = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<PageDetail>("/pages", body),
    onSuccess: (created) => {
      invalidate();
      navigate(`/pages/${created.id}`);
    },
  });

  const updatePage = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/pages/${id}`, body),
    onSuccess: invalidate,
  });

  const deletePage = useMutation({
    mutationFn: (id: string) => api.delete(`/pages/${id}`),
    onSuccess: () => {
      invalidate();
      navigate("/pages");
    },
  });

  function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!pageId) return;
    updatePage.mutate({
      id: pageId,
      body: {
        title: title ?? undefined,
        icon: icon ?? undefined,
        content: preview ? undefined : contentHtml || "<p></p>",
      },
    });
  }

  const roots = (pages.data ?? []).filter((p) => !p.parent_id);
  const childrenOf = (pid: string) => (pages.data ?? []).filter((p) => p.parent_id === pid);

  return (
    <div className="flex gap-4">
      {/* Page tree */}
      <aside
        className="hidden w-56 shrink-0 md:block"
        style={{ borderRight: "1px solid var(--border)" }}
      >
        <div className="flex items-center justify-between px-2 pb-2">
          <span
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: "var(--text-muted)" }}
          >
            📄 Workspace
          </span>
          <button
            onClick={() => createPage.mutate({ title: "Tanpa judul" })}
            disabled={createPage.isPending}
            className="text-xs font-medium text-[var(--accent)] hover:opacity-80"
            style={{ color: "var(--accent)" }}
          >
            + Baru
          </button>
        </div>
        <div className="space-y-0.5">
          {roots.map((p) => (
            <div key={p.id}>
              <TreeLink to={`/pages/${p.id}`} active={pageId === p.id} label={`${p.icon} ${p.title}`} />
              {childrenOf(p.id).map((c) => (
                <TreeLink
                  key={c.id}
                  to={`/pages/${c.id}`}
                  active={pageId === c.id}
                  label={`${c.icon} ${c.title}`}
                  indent
                />
              ))}
            </div>
          ))}
          {pages.data?.length === 0 && (
            <p className="px-2 text-xs" style={{ color: "var(--text-muted)" }}>
              Belum ada halaman.
            </p>
          )}
        </div>
      </aside>

      {/* Editor */}
      <div className="min-w-0 flex-1 space-y-4">
        {!pageId && (
          <>
            <div className="mb-4 text-[56px] leading-none">📄</div>
            <h1 className="text-[38px] font-bold leading-[1.15] tracking-[-0.02em]" style={{ color: "var(--text)" }}>
              Workspace
            </h1>
            <p className="mb-6 mt-1 text-[15px]" style={{ color: "var(--text-muted)" }}>
              Catatan & dokumen workspace dengan block editor rich-text.
            </p>
            <button
              onClick={() => createPage.mutate({ title: "Tanpa judul" })}
              disabled={createPage.isPending}
              className="btn-secondary"
            >
              + Buat halaman pertama
            </button>
          </>
        )}

        {pageId && (
          <>
            {/* Header dokumen halaman */}
            <div className="flex items-start justify-between gap-3">
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setIconPickerOpen((v) => !v)}
                  className="block rounded-md px-1 transition-colors hover:bg-[var(--hover)]"
                  title="Ganti ikon"
                >
                  <span className="text-[56px] leading-none">{icon ?? "📄"}</span>
                </button>
                {iconPickerOpen && (
                  <div
                    className="absolute left-0 top-16 z-20 grid w-64 grid-cols-6 gap-1 rounded-lg p-2 shadow-lg"
                    style={{
                      backgroundColor: "var(--bg-elevated)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    {EMOJIS.map((em) => (
                      <button
                        key={em}
                        onClick={() => {
                          setIcon(em);
                          setIconPickerOpen(false);
                        }}
                        className="rounded p-1 text-xl transition-colors hover:bg-[var(--hover)]"
                      >
                        {em}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm("Hapus halaman ini beserta sub-halamannya?"))
                    deletePage.mutate(pageId);
                }}
                disabled={deletePage.isPending}
                title="Hapus halaman"
                className="mt-2 flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-rose-600 transition-colors hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" /> Hapus halaman
              </button>
            </div>

            <input
              value={title ?? ""}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Judul halaman"
              className="w-full border-none bg-transparent text-[38px] font-bold leading-[1.15] tracking-[-0.02em] focus:outline-none"
              style={{ color: "var(--text)" }}
            />

            <form onSubmit={handleSave} className="space-y-3">
              <TiptapEditor
                html={contentHtml}
                pageKey={pageId}
                editable={!preview}
                onChange={(html) => setContentHtml(html)}
              />

              <div className="flex items-center gap-3 text-xs">
                {!preview ? (
                  <>
                    <button type="submit" disabled={updatePage.isPending} className="btn">
                      Simpan
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreview(true)}
                      className="btn-secondary"
                    >
                      👁 Pratinjau
                    </button>
                  </>
                ) : (
                  <button type="button" onClick={() => setPreview(false)} className="btn-secondary">
                    ✏️ Ubah
                  </button>
                )}
                {updatePage.isSuccess && !updatePage.isPending && (
                  <span style={{ color: "#0f7b6d" }}>Tersimpan ✓</span>
                )}
              </div>
              {updatePage.error && (
                <p className="text-xs text-red-600">{(updatePage.error as Error).message}</p>
              )}
            </form>

            {/* Sub-halaman */}
            {(childrenOf(pageId).length > 0 || true) && (
              <div className="pt-2 text-xs">
                <b style={{ color: "var(--text-muted)" }}>Sub-halaman</b>
                <div className="mt-1 space-y-0.5">
                  {childrenOf(pageId).map((c) => (
                    <TreeLink
                      key={`inline-${c.id}`}
                      to={`/pages/${c.id}`}
                      active={false}
                      label={`${c.icon} ${c.title}`}
                    />
                  ))}
                  <button
                    onClick={() => createPage.mutate({ title: "Sub-halaman", parent_id: pageId })}
                    disabled={createPage.isPending}
                    className="font-medium hover:underline"
                    style={{ color: "var(--accent)" }}
                  >
                    + Tambah sub-halaman
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function TreeLink({
  to,
  active,
  label,
  indent,
}: {
  to: string;
  active: boolean;
  label: string;
  indent?: boolean;
}) {
  return (
    <a
      href={to}
      className={`block truncate rounded px-2 py-1 text-sm transition-colors hover:bg-[var(--hover)] ${
        indent ? "pl-6" : ""
      }`}
      style={{
        color: active ? "var(--text)" : "var(--text-muted)",
        backgroundColor: active ? "var(--hover)" : undefined,
        fontWeight: active ? 500 : 400,
      }}
    >
      {label}
    </a>
  );
}
