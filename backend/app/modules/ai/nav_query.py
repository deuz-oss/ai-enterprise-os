"""Kalimat bebas di ⌘K -> daftar yang sudah terfilter (peluang AI #5 audit 2026-10-08).

Contoh: "karyawan PT Maju kontrak habis bulan depan" ->
`/employees?client=<id>&contract_days=52`.

Pembagian kerja:
- LLM HANYA memetakan kalimat ke skema tetap (halaman + filter dari daftar
  putih). Ia tidak melihat data dan tidak memilih ID.
- Backend memvalidasi semuanya: nilai di luar daftar putih dibuang, nama
  klien dicocokkan ke ID secara deterministik (bukan oleh LLM), tanggal
  dikonversi ke jumlah hari dari hari ini.
- Halaman tujuan menerapkan filter dari URL dan menegakkan RBAC-nya sendiri.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

PAGES: dict[str, dict[str, Any]] = {
    "employees": {
        "path": "/employees",
        "label": "Karyawan",
        "statuses": {"aktif": "aktif", "resign": "resign"},
    },
    "invoices": {
        "path": "/finance",
        "label": "Invoice",
        "statuses": {
            "draft": "draft",
            "terkirim": "terkirim",
            "dibayar": "dibayar",
            "dibatalkan": "dibatalkan",
        },
    },
    "job_orders": {
        "path": "/job-orders",
        "label": "Job Order",
        "statuses": {
            "dibuka": "dibuka",
            "ditahan": "ditahan",
            "dibatalkan": "dibatalkan",
            "terisi": "terisi",
        },
    },
}

_SYSTEM = (
    "Anda menerjemahkan permintaan user aplikasi HR/outsourcing Indonesia menjadi filter "
    "daftar. Balas HANYA JSON dengan skema: "
    '{"page": "employees"|"invoices"|"job_orders"|null, '
    '"status": string|null, "client": string|null, '
    '"contract_ends_by": "YYYY-MM-DD"|null, "overdue": boolean|null, "q": string|null}. '
    "Status yang sah: employees = aktif|resign; invoices = draft|terkirim|dibayar|dibatalkan; "
    "job_orders = dibuka|ditahan|dibatalkan|terisi. "
    "`client` = nama perusahaan klien persis seperti ditulis user (jangan mengarang). "
    "`contract_ends_by` hanya untuk employees (kontrak berakhir paling lambat tanggal itu). "
    "`overdue` hanya untuk invoices (lewat jatuh tempo). `q` = kata kunci nama/nomor "
    "karyawan, hanya untuk employees. Isi null untuk yang tidak disebut. "
    "Bila permintaan bukan tentang daftar karyawan, invoice, atau job order, page = null."
)

_CLIENT_STOPWORDS = {"pt", "cv", "tbk", "persero", "the"}


def _tokens(name: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", name.lower()) if t not in _CLIENT_STOPWORDS}


def resolve_client(db: Session, name: str) -> tuple[str, str] | None:
    """Nama klien dari kalimat user -> (id, nama resmi), deterministik.

    Cocok persis (tanpa PT/CV) dulu, lalu klien yang memuat semua token yang
    ditulis user. Lebih dari satu kandidat = ambigu -> tidak dipilih.
    """
    from app.modules.clients.models import Client

    wanted = _tokens(name)
    if not wanted:
        return None
    clients = db.execute(select(Client.id, Client.name)).all()
    exact = [(cid, n) for cid, n in clients if _tokens(n) == wanted]
    partial = [(cid, n) for cid, n in clients if wanted <= _tokens(n)]
    pick = exact if len(exact) == 1 else partial if len(partial) == 1 else []
    return (str(pick[0][0]), pick[0][1]) if pick else None


def build_navigation(db: Session, parsed: dict, today: date | None = None) -> dict:
    """Validasi keluaran LLM -> path + ringkasan filter yang diterapkan."""
    today = today or date.today()
    page_key = parsed.get("page")
    if page_key not in PAGES:
        return {"page": None, "path": None, "applied": [], "ignored": []}
    page = PAGES[page_key]
    params: dict[str, str] = {}
    applied: list[str] = []
    ignored: list[str] = []

    status = str(parsed.get("status") or "").strip().lower()
    if status:
        if status in page["statuses"]:
            params["status"] = page["statuses"][status]
            applied.append(f"Status: {status}")
        else:
            ignored.append(f'status "{status}" tidak dikenal')

    client = str(parsed.get("client") or "").strip()
    if client:
        resolved = resolve_client(db, client)
        if resolved:
            params["client"] = resolved[0]
            applied.append(f"Klien: {resolved[1]}")
        else:
            ignored.append(f'klien "{client}" tidak ditemukan atau ambigu')

    if page_key == "employees":
        ends_by = parsed.get("contract_ends_by")
        if ends_by:
            try:
                days = (date.fromisoformat(str(ends_by)[:10]) - today).days
            except ValueError:
                days = -1
            if 1 <= days <= 365:
                params["contract_days"] = str(days)
                applied.append(f"Kontrak berakhir ≤ {str(ends_by)[:10]} ({days} hari)")
            else:
                ignored.append("tanggal akhir kontrak di luar 1-365 hari ke depan")
        q = str(parsed.get("q") or "").strip()[:60]
        if q:
            params["q"] = q
            applied.append(f'Cari: "{q}"')

    if page_key == "invoices" and parsed.get("overdue") is True:
        params["overdue"] = "1"
        applied.append("Lewat jatuh tempo")

    path = page["path"] + (f"?{urlencode(params)}" if params else "")
    return {"page": page["label"], "path": path, "applied": applied, "ignored": ignored}


def nav_query(db: Session, text: str) -> dict:
    from app.core.llm import ai_configured, chat_completion

    text = text.strip()[:200]
    if not text or not ai_configured():
        return {"page": None, "path": None, "applied": [], "ignored": [], "source": "none"}
    try:
        parsed = chat_completion(
            _SYSTEM + f" Hari ini {date.today().isoformat()}.",
            text,
            json_mode=True,
            feature="palette.nav_query",
        )
    except Exception:  # noqa: BLE001 - palet tetap jalan tanpa terjemahan
        return {"page": None, "path": None, "applied": [], "ignored": [], "source": "none"}
    result = build_navigation(db, parsed if isinstance(parsed, dict) else {})
    return {**result, "source": "ai" if result["path"] else "none"}
