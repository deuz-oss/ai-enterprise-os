import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader } from "../components/notion";

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

export default function Pages() {
  const params = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pageId = params.id ?? null;

  const [title, setTitle] = useState<string | null>(null);
  const [icon, setIcon] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);

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
      setContent(detail.data.content);
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
        content: content ?? undefined,
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
        style={{ borderRight: "1px solid var(--n-border)" }}
      >
        <div className="flex items-center justify-between px-2 pb-2">
          <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--n-text-muted)" }}>
            📄 Halaman
          </span>
          <button
            onClick={() => createPage.mutate({ title: "Tanpa judul" })}
            disabled={createPage.isPending}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
          >
            + Baru
          </button>
        </div>
        <div className="space-y-0.5">
          {roots.map((p) => (
            <div key={p.id}>
              <NavLink to={`/pages/${p.id}`} active={pageId === p.id} label={`${p.icon} ${p.title}`} />
              {childrenOf(p.id).map((c) => (
                <NavLink
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
            <p className="px-2 text-xs" style={{ color: "var(--n-text-muted)" }}>
              Belum ada halaman.
            </p>
          )}
        </div>
      </aside>

      {/* Editor */}
      <div className="min-w-0 flex-1 space-y-4">
        {!pageId && (
          <>
            <PageHeader
              emoji="📄"
              title="Halaman"
              subtitle="Catatan & dokumen workspace dengan struktur sub-halaman ala Notion"
            />
            <button
              onClick={() => createPage.mutate({ title: "Tanpa judul" })}
              disabled={createPage.isPending}
              className="btn-secondary"
            >
              + Buat halaman pertama
            </button>
          </>
        )}

        {pageId && detail.data && (
          <form onSubmit={handleSave} className="space-y-3">
            <div className="flex items-center gap-2">
              <input
                value={icon ?? ""}
                onChange={(e) => setIcon(e.target.value)}
                className="input w-14 text-center text-xl"
                aria-label="Ikon"
              />
              <input
                value={title ?? ""}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Judul halaman"
                className="input flex-1 text-lg font-semibold"
              />
            </div>
            <textarea
              value={content ?? ""}
              onChange={(e) => setContent(e.target.value)}
              rows={18}
              placeholder="Tulis konten halaman..."
              className="input w-full"
            />
            <div className="flex items-center gap-3 text-xs">
              <button type="submit" disabled={updatePage.isPending} className="btn-secondary">
                Simpan
              </button>
              {updatePage.isSuccess && !updatePage.isPending && (
                <span className="text-emerald-600">Tersimpan ✓</span>
              )}
              <button
                type="button"
                onClick={() => {
                  if (window.confirm("Hapus halaman ini beserta sub-halamannya?"))
                    deletePage.mutate(pageId);
                }}
                disabled={deletePage.isPending}
                className="ml-auto text-rose-600 hover:text-rose-800"
              >
                Hapus halaman
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function NavLink({
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
      className={`block truncate rounded px-2 py-1 text-sm transition-colors hover:bg-[var(--n-hover)] ${
        indent ? "pl-6" : ""
      }`}
      style={{
        color: active ? "var(--n-text)" : "var(--n-text-muted)",
        backgroundColor: active ? "var(--n-hover)" : undefined,
        fontWeight: active ? 500 : 400,
      }}
    >
      {label}
    </a>
  );
}
