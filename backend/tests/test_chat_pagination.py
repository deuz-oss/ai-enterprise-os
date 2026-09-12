"""Cursor pagination (before_id + X-Has-More) untuk histori pesan chat.

Sebelumnya `GET /chat/channels/{id}/messages` cuma punya `limit` tanpa cara
apa pun memuat histori yang lebih lama -- channel dengan > `limit` pesan,
sisanya tidak bisa pernah dilihat lagi lewat UI.

Catatan penting soal timestamp di test: SQLite (dev/test) menyimpan
DateTime cuma dengan presisi DETIK (`CURRENT_TIMESTAMP`), jadi beberapa
pesan yang dikirim berurutan lewat test bisa punya `created_at` yang
BENAR-BENAR IDENTIK -- tiebreak-nya jatuh ke `id` (UUID acak), bukan
urutan kirim. Ini bukan bug: kalau dua pesan betul-betul simultan
(tidak bisa dibedakan waktunya), tiebreak yang konsisten (apa pun itu)
tetap sah selama TIDAK ADA gap/duplikat -- itulah yang dites di sini
lewat pendekatan set-based, bukan asumsi urutan insert. Untuk menguji
urutan KRONOLOGIS yang sesungguhnya, timestamp di-set manual jadi
berbeda-beda (mensimulasikan presisi microsecond Postgres asli).
"""

import datetime as dt
from uuid import UUID

from tests.conftest import _auth_header


def _set_created_at(client, message_id: str, when: dt.datetime) -> None:
    from app.core.database import parse_uuid
    from app.modules.chat.models import ChatMessage

    db = client.testing_session()
    try:
        msg = db.get(ChatMessage, parse_uuid(message_id))
        msg.created_at = when
        db.commit()
    finally:
        db.close()


def test_before_id_cursor_covers_all_without_gap_or_duplicate(client):
    """Tanpa asumsi urutan insert (timestamp bisa tie di SQLite) -- yang
    wajib benar: gabungan semua halaman = semua pesan, tepat sekali, dan
    `has_more` jadi false persis saat pesan terakhir sudah termuat."""
    admin = _auth_header(client)
    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={"name": "Pagination Test", "channel_type": "public"},
    ).json()

    sent_ids = set()
    for i in range(7):
        resp = client.post(
            f"/api/v1/chat/channels/{ch['id']}/messages",
            headers=admin,
            json={"content": f"Pesan #{i + 1}"},
        )
        sent_ids.add(resp.json()["id"])

    collected: list[str] = []
    before_id = None
    pages_fetched = 0
    while True:
        pages_fetched += 1
        assert pages_fetched <= 10, "terlalu banyak halaman -- kemungkinan loop tak berhenti"
        qs = "limit=3" + (f"&before_id={before_id}" if before_id else "")
        resp = client.get(f"/api/v1/chat/channels/{ch['id']}/messages?{qs}", headers=admin)
        assert resp.status_code == 200
        page = resp.json()
        assert len(page) > 0, "halaman kosong tapi has_more sebelumnya true -- gap/loop"
        has_more = resp.headers["x-has-more"] == "true"
        page_ids = [m["id"] for m in page]
        assert not (set(page_ids) & set(collected)), f"duplikat lintas halaman: {page_ids}"
        collected = page_ids + collected
        if not has_more:
            break
        before_id = page[0]["id"]

    assert set(collected) == sent_ids
    assert len(collected) == 7
    assert pages_fetched == 3  # 3 + 3 + 1


def test_has_more_false_when_channel_has_fewer_messages_than_limit(client):
    admin = _auth_header(client)
    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={"name": "Pagination Small", "channel_type": "public"},
    ).json()
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin, json={"content": "Satu pesan"}
    )

    resp = client.get(f"/api/v1/chat/channels/{ch['id']}/messages?limit=50", headers=admin)
    assert resp.status_code == 200
    assert resp.headers["x-has-more"] == "false"
    assert len(resp.json()) == 1


def test_before_id_returns_strictly_chronological_order(client):
    """Timestamp dipaksa berbeda-beda (simulasi presisi microsecond Postgres
    asli) -- cursor harus memuat histori persis sesuai urutan waktu kirim,
    tanpa gap/duplikat, halaman demi halaman."""
    admin = _auth_header(client)
    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={"name": "Pagination Chronological", "channel_type": "public"},
    ).json()

    base = dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.UTC)
    sent_ids = []
    for i in range(7):
        resp = client.post(
            f"/api/v1/chat/channels/{ch['id']}/messages",
            headers=admin,
            json={"content": f"Pesan #{i + 1}"},
        )
        mid = resp.json()["id"]
        _set_created_at(client, mid, base + dt.timedelta(seconds=i))
        sent_ids.append(mid)

    collected: list[str] = []
    before_id = None
    while True:
        qs = "limit=3" + (f"&before_id={before_id}" if before_id else "")
        resp = client.get(f"/api/v1/chat/channels/{ch['id']}/messages?{qs}", headers=admin)
        page = resp.json()
        has_more = resp.headers["x-has-more"] == "true"
        collected = [m["id"] for m in page] + collected
        if not has_more:
            break
        before_id = page[0]["id"]

    assert collected == sent_ids


def test_before_id_scoped_correctly_for_thread_replies(client):
    """Cursor `before_id` untuk thread (`parent_id`) tidak boleh bocor ke
    pesan top-level channel yang sama."""
    admin = _auth_header(client)
    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={"name": "Pagination Thread", "channel_type": "public"},
    ).json()
    root = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin, json={"content": "Root"}
    ).json()

    base = dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.UTC)
    reply_ids = []
    for i in range(4):
        r = client.post(
            f"/api/v1/chat/channels/{ch['id']}/messages",
            headers=admin,
            json={"content": f"Reply {i + 1}", "parent_id": root["id"]},
        )
        rid = r.json()["id"]
        _set_created_at(client, rid, base + dt.timedelta(seconds=i + 1))
        reply_ids.append(rid)

    resp = client.get(
        f"/api/v1/chat/channels/{ch['id']}/messages?parent_id={root['id']}&limit=2",
        headers=admin,
    )
    page1 = resp.json()
    assert [m["id"] for m in page1] == reply_ids[2:]
    assert resp.headers["x-has-more"] == "true"
    # Root (top-level, bukan reply) tidak boleh ikut muncul di daftar thread.
    assert root["id"] not in [m["id"] for m in page1]

    resp2 = client.get(
        f"/api/v1/chat/channels/{ch['id']}/messages"
        f"?parent_id={root['id']}&limit=2&before_id={page1[0]['id']}",
        headers=admin,
    )
    page2 = resp2.json()
    assert [m["id"] for m in page2] == reply_ids[:2]
    assert resp2.headers["x-has-more"] == "false"


def test_before_id_with_nonexistent_cursor_returns_empty_not_error(client):
    """`before_id` yang tidak cocok pesan apa pun (mis. sudah dihapus
    permanen/tidak valid) tidak boleh 500 -- subquery anchor kosong
    membuat perbandingan tuple NULL, jadi hasilnya kosong, bukan error."""
    admin = _auth_header(client)
    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={"name": "Pagination Bad Cursor", "channel_type": "public"},
    ).json()
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin, json={"content": "Halo"}
    )

    fake_id = str(UUID(int=0))
    resp = client.get(
        f"/api/v1/chat/channels/{ch['id']}/messages?before_id={fake_id}", headers=admin
    )
    assert resp.status_code == 200
    assert resp.json() == []
