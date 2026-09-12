/**
 * Tahap PlacementStatus (label + warna dot) -- dulu diduplikasi persis di
 * JobOrderDetail.tsx, TalentPool.tsx, dan TalentPoolDetail.tsx (masing-masing
 * sudah menandai sendiri sebagai "duplikat kecil" lewat komentar). Disatukan
 * di sini (audit UI/UX 2026-09-12, prinsip design.md §6.2: "satu keputusan
 * warna, satu tempat") supaya urutan/label/warna tahap konsisten di Kanban
 * Job Order, pill status Talent Pool, dan detail kandidat sekaligus.
 *
 * Riwayat tahap (dari JobOrderDetail.tsx, disederhanakan 2026-09-07 lewat
 * umpan balik domain owner): "Kirim Klien"/"Screening Klien" dibuang (lebur
 * ke "Disubmit" -- checkpoint klien yang genuinely penting tetap terekam
 * lewat "Interview Klien" + status Gagal/rejection_note, bukan lewat tahap
 * antara yang jarang dibedakan penindaklanjutannya), "Diusulkan"+"Disetujui"
 * lebur jadi satu "Offering" (surat penawaran + status esign sudah cukup
 * merepresentasikan menunggu-TTD vs sudah-TTD).
 */

export interface PipelineStageMeta {
  key: string;
  label: string;
  dot: string;
}

export const PIPELINE_STAGES: PipelineStageMeta[] = [
  { key: "disourcing", label: "Sourcing", dot: "#9f9f9f" },
  { key: "screening", label: "Screening", dot: "#2383e2" },
  { key: "interview_rekruter", label: "Interview Internal", dot: "#5b5bd6" },
  { key: "disubmit", label: "Disubmit", dot: "#8b5cf6" },
  { key: "interview_klien", label: "Interview Klien", dot: "#cb912f" },
  { key: "ojt", label: "OJT", dot: "#d97706" },
  { key: "offering", label: "Offering", dot: "#059669" },
  { key: "hired", label: "Hired", dot: "#0f7b6c" },
  { key: "onboarded", label: "Onboarded", dot: "#0f172a" },
];

export const TERMINAL_STAGE_DOT = "#e03e3e";
export const TERMINAL_STAGE_LABEL: Record<string, string> = { gagal: "Gagal", dibatalkan: "Dibatalkan" };

/** Lookup gabungan (tahap aktif + terminal) untuk pill/badge status kandidat. */
export const PLACEMENT_STAGE_META: Record<string, { label: string; dot: string }> = {
  ...Object.fromEntries(PIPELINE_STAGES.map((s) => [s.key, { label: s.label, dot: s.dot }])),
  ...Object.fromEntries(Object.entries(TERMINAL_STAGE_LABEL).map(([key, label]) => [key, { label, dot: TERMINAL_STAGE_DOT }])),
};
