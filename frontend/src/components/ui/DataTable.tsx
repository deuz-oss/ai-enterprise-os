import { Fragment, useEffect, useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { Pagination } from "../Pagination";
import { EmptyState, QueryState, TableStateRow, type QueryLike } from "./states";

/**
 * Tabel data standar (audit 2026-10-08 §8, Phase 3). Sebelumnya 57 `<table>`
 * di 26 file ditulis manual: tanpa sort, header tidak sticky, angka rata kiri,
 * tanpa total, dan state loading/error berbeda-beda.
 *
 * - Sort di klien atas `rows` yang diberikan. Untuk daftar yang dipaginasi
 *   SERVER, jangan beri `sortValue` (sort satu halaman saja menyesatkan).
 *   Daftar yang dimuat penuh: beri `pageSize` supaya DataTable sort DULU baru
 *   memotong halaman.
 * - Kolom `numeric`: rata kanan + digit tabular (`.num`).
 * - `footer` per kolom -> baris total di bawah (mis. jumlah rupiah).
 * - `onRowClick`: baris bisa diklik & dijangkau keyboard (Enter/Spasi). Sengaja
 *   tanpa role="button" -- baris sering berisi tombol/select (nested-interactive).
 * - `renderExpanded`: baris tambahan di bawah baris (mis. form inline).
 */

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  numeric?: boolean;
  /** Aktifkan sort kolom ini. Kembalikan null untuk nilai kosong (selalu di akhir). */
  sortValue?: (row: T) => string | number | null | undefined;
  footer?: ReactNode;
  /** Kelas untuk sel isi (<td>) & footer -- tidak diterapkan ke header. */
  className?: string;
  headerClassName?: string;
}

type SortState = { key: string; dir: "asc" | "desc" } | null;

/**
 * Sort stabil (salinan baru). Nilai kosong (null/undefined/"") SELALU di akhir,
 * apa pun arahnya; angka dibandingkan numerik; teks pakai collation "id" dengan
 * `numeric: true` (EMP-2 sebelum EMP-10). Diekspor untuk unit test.
 */
export function sortRows<T>(
  rows: readonly T[],
  get: (row: T) => string | number | null | undefined,
  dir: "asc" | "desc"
): T[] {
  const factor = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = get(a);
    const vb = get(b);
    const aEmpty = va === null || va === undefined || va === "";
    const bEmpty = vb === null || vb === undefined || vb === "";
    if (aEmpty || bEmpty) return aEmpty === bEmpty ? 0 : aEmpty ? 1 : -1;
    if (typeof va === "number" && typeof vb === "number") return (va - vb) * factor;
    return String(va).localeCompare(String(vb), "id", { numeric: true, sensitivity: "base" }) * factor;
  });
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  query,
  emptyTitle,
  emptyDescription,
  emptyAction,
  onRowClick,
  isRowSelected,
  renderExpanded,
  defaultSort = null,
  pageSize,
  maxHeight = "70vh",
  label,
  mobileCards = true,
  plain = false,
}: {
  rows: T[] | undefined;
  columns: Column<T>[];
  rowKey: (row: T) => string;
  query?: QueryLike;
  emptyTitle: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  onRowClick?: (row: T) => void;
  isRowSelected?: (row: T) => boolean;
  renderExpanded?: (row: T) => ReactNode | null;
  defaultSort?: SortState;
  pageSize?: number;
  /** Tinggi maksimum area gulir -- diperlukan supaya header bisa sticky. */
  maxHeight?: string;
  /** Nama tabel untuk screen reader. */
  label: string;
  /** Di bawah breakpoint `sm`, tampilkan tiap baris sebagai kartu label: nilai
   * (bukan tabel yang digeser horizontal). Default aktif. */
  mobileCards?: boolean;
  /** Tanpa bingkai kartu -- untuk tabel yang sudah berada di dalam kartu lain. */
  plain?: boolean;
}) {
  const [sort, setSort] = useState<SortState>(defaultSort);
  const [offset, setOffset] = useState(0);

  const sorted = useMemo(() => {
    const list = rows ?? [];
    const col = sort && columns.find((c) => c.key === sort.key);
    if (!sort || !col?.sortValue) return list;
    return sortRows(list, col.sortValue, sort.dir);
  }, [rows, columns, sort]);

  // Kembali ke halaman pertama kalau jumlah baris berubah (filter/tab/pencarian).
  const total = sorted.length;
  useEffect(() => {
    setOffset(0);
  }, [total]);
  const safeOffset = pageSize && offset >= total ? 0 : offset;
  const visible = pageSize ? sorted.slice(safeOffset, safeOffset + pageSize) : sorted;
  const hasFooter = columns.some((c) => c.footer !== undefined);

  function toggleSort(key: string) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: "asc" };
      if (prev.dir === "asc") return { key, dir: "desc" };
      return null;
    });
    setOffset(0);
  }

  function rowKeyDown(e: KeyboardEvent<HTMLTableRowElement>, row: T) {
    if (e.target !== e.currentTarget) return; // jangan bajak Enter di input/tombol di dalam baris
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onRowClick?.(row);
    }
  }

  const emptyState = query ? (
    <TableStateRow
      query={query}
      colSpan={columns.length}
      isEmpty={total === 0}
      emptyTitle={emptyTitle}
      emptyDescription={emptyDescription}
      emptyAction={emptyAction}
    />
  ) : (
    total === 0 && (
      <tr>
        <td colSpan={columns.length} className="td py-8 text-center" style={{ color: "var(--th-color)" }}>
          {emptyTitle}
        </td>
      </tr>
    )
  );

  const ready = !query || (!query.isPending && !query.isError);
  const cards = mobileCards && (
    <div
      className="space-y-2 sm:hidden"
      // role list hanya bila ada item (axe aria-required-children).
      role={ready && total > 0 ? "list" : undefined}
      aria-label={ready && total > 0 ? label : undefined}
    >
      {!ready || total === 0 ? (
        <div className={plain ? "" : "card"}>
          {query && !ready ? (
            <QueryState query={query} compact>
              {null}
            </QueryState>
          ) : (
            <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} compact />
          )}
        </div>
      ) : (
        visible.map((row) => {
          const [first, ...rest] = columns;
          const expanded = renderExpanded?.(row);
          const selected = isRowSelected?.(row) ?? false;
          return (
            <div
              key={rowKey(row)}
              role="listitem"
              className={plain ? "space-y-2 border-t py-3" : "card space-y-2"}
              style={selected ? { backgroundColor: "var(--accent-tint)" } : undefined}
            >
              <div
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
                aria-current={selected ? "true" : undefined}
                className={onRowClick ? "cursor-pointer" : undefined}
              >
                <div className={`text-sm font-medium ${first.className ?? ""}`} style={{ color: "var(--text)" }}>
                  {first.cell(row)}
                </div>
                <dl className="mt-1.5 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-sm">
                  {rest.map((c) => (
                    <Fragment key={c.key}>
                      <dt style={{ color: "var(--th-color)" }}>{c.header}</dt>
                      {/* Tanpa inline color: kelas kolom (mis. merah potongan) harus menang. */}
                      <dd className={`min-w-0 ${c.numeric ? "tabular-nums" : ""} ${c.className ?? ""}`}>
                        {c.cell(row)}
                      </dd>
                    </Fragment>
                  ))}
                </dl>
              </div>
              {expanded}
            </div>
          );
        })
      )}
      {ready && hasFooter && total > 0 && (
        <dl className="card grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-sm font-semibold">
          {columns
            .filter((c) => c.footer !== undefined && c.numeric)
            .map((c) => (
              <Fragment key={c.key}>
                <dt style={{ color: "var(--th-color)" }}>Total {c.header}</dt>
                <dd className="tabular-nums" style={{ color: "var(--text)" }}>
                  {c.footer}
                </dd>
              </Fragment>
            ))}
        </dl>
      )}
    </div>
  );

  return (
    <>
      {cards}
      <div
        className={`${plain ? "" : "card p-0"} overflow-auto ${mobileCards ? "hidden sm:block" : ""}`}
        // container-type: baris ekspansi memakai lebar area gulir (cqw), bukan lebar
        // tabel. Hanya bila ada renderExpanded -- containment membuat lebar intrinsik
        // area ini 0, berisiko di induk shrink-to-fit.
        style={{ maxHeight, containerType: renderExpanded ? "inline-size" : undefined }}
        // Area gulir (header sticky + tabel lebar) harus bisa difokus agar bisa
        // digulir dengan keyboard (axe scrollable-region-focusable).
        tabIndex={0}
        role="region"
        aria-label={label}
      >
        <table className="w-full">
          {/* Dasar solid: --hover di dark mode transparan, header sticky tanpa
              dasar akan tembus memperlihatkan baris yang lewat di bawahnya. */}
          <thead className="sticky top-0 z-[1]" style={{ backgroundColor: "var(--bg-elevated)" }}>
            <tr style={{ boxShadow: "inset 0 -1px 0 var(--border)" }}>
              {columns.map((c) => {
                const active = sort?.key === c.key ? sort.dir : null;
                return (
                  <th
                    key={c.key}
                    scope="col"
                    className={`th ${c.numeric ? "num" : ""} ${c.headerClassName ?? ""}`}
                    aria-sort={active ? (active === "asc" ? "ascending" : "descending") : undefined}
                  >
                    {c.sortValue ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(c.key)}
                        className={`inline-flex items-center gap-1 hover:opacity-80 ${c.numeric ? "flex-row-reverse" : ""}`}
                      >
                        {c.header}
                        {active === "asc" ? (
                          <ArrowUp className="h-3 w-3" aria-hidden="true" />
                        ) : active === "desc" ? (
                          <ArrowDown className="h-3 w-3" aria-hidden="true" />
                        ) : (
                          <ChevronsUpDown className="h-3 w-3 opacity-50" aria-hidden="true" />
                        )}
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {(!query || (!query.isPending && !query.isError)) &&
              visible.map((row) => {
                const key = rowKey(row);
                const selected = isRowSelected?.(row) ?? false;
                const expanded = renderExpanded?.(row);
                return (
                  <Fragment key={key}>
                    <tr
                      onClick={onRowClick ? () => onRowClick(row) : undefined}
                      onKeyDown={onRowClick ? (e) => rowKeyDown(e, row) : undefined}
                      tabIndex={onRowClick ? 0 : undefined}
                      aria-current={selected ? "true" : undefined}
                      className={onRowClick ? "cursor-pointer transition-colors hover:bg-[var(--hover)]" : undefined}
                      style={selected ? { backgroundColor: "var(--accent-tint)" } : undefined}
                    >
                      {columns.map((c) => (
                        <td key={c.key} className={`td ${c.numeric ? "num" : ""} ${c.className ?? ""}`}>
                          {c.cell(row)}
                        </td>
                      ))}
                    </tr>
                    {expanded && (
                      <tr>
                        <td colSpan={columns.length} className="td" style={{ backgroundColor: "var(--hover)" }}>
                          {/* Sticky selebar area yang terlihat: saat tabel lebar digulir ke
                              kanan, form/panel ekspansi tidak ikut terpotong di kiri. */}
                          <div className="sticky left-4" style={{ width: "calc(100cqw - 2rem)" }}>
                            {expanded}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            {emptyState}
          </tbody>
          {hasFooter && total > 0 && (
            <tfoot className="sticky bottom-0" style={{ backgroundColor: "var(--bg-elevated)" }}>
              <tr style={{ boxShadow: "inset 0 1px 0 var(--border)" }}>
                {columns.map((c) => (
                  <td key={c.key} className={`td font-semibold ${c.numeric ? "num" : ""} ${c.className ?? ""}`}>
                    {c.footer}
                  </td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {pageSize && <Pagination offset={safeOffset} limit={pageSize} total={total} onOffsetChange={setOffset} />}
    </>
  );
}
