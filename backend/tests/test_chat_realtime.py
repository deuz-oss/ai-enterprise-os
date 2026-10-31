"""Presence & typing WS chat (PRD §9.2 + §9.4): fokus KEBOCORAN SCOPE.

Pola "barrier": klien mengirim ping lalu membaca sampai pong. Karena tiap
koneksi memproses frame berurutan dan fan-out di-await sebelum frame
berikutnya diproses, semua event yang SEHARUSNYA sampai pasti sudah antre
sebelum pong -> bisa membuktikan "TIDAK menerima" tanpa sleep.
"""

from contextlib import ExitStack
from uuid import UUID, uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import _auth_header, _login_header, _platform_admin_header

PW = "rahasia-123"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture()
def rt(client, monkeypatch):
    """Hub baru per test: clock palsu, tanpa sweeper (tick dipanggil manual)."""
    import app.core.database as database
    import app.modules.chat.ws_manager as wsm
    from app.modules.chat.realtime.hub import RealtimeHub

    # WS & cache realtime membuka SessionLocal() sendiri -> arahkan ke DB test.
    monkeypatch.setattr(database, "SessionLocal", client.testing_session)
    clock = FakeClock()
    hub = RealtimeHub(clock=clock, sweeper=False)
    monkeypatch.setattr(wsm, "manager", hub)

    class _RT:
        pass

    ctx = _RT()
    ctx.hub = hub  # type: ignore[attr-defined]
    ctx.clock = clock  # type: ignore[attr-defined]
    ctx.tick = lambda: client.portal.call(hub.tick)  # type: ignore[attr-defined]
    return ctx


def _token(client, email: str) -> str:
    return _login_header(client, email, PW)["Authorization"].split()[1]


def _world(client) -> dict:
    """Tenant default: admin, hr, ops, fin, karyawan a1+a2 (Klien A), b1 (Klien B),
    lone (karyawan tanpa placement)."""
    from app.core.bootstrap import ensure_default_tenant
    from app.core.tenancy import tenant_context
    from app.modules.auth.models import User
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user
    from app.modules.clients.models import Client
    from app.modules.hrd.models import Employee
    from app.modules.recruitment.models import JobOrder, Placement
    from sqlalchemy import select

    admin_header = _auth_header(client)
    db = client.testing_session()
    ids: dict[str, str] = {}
    try:
        tenant = ensure_default_tenant(db)
        tid = tenant.id
        for key, role in [
            ("hr", "hr"),
            ("ops", "operations"),
            ("fin", "finance"),
            ("a1", "karyawan"),
            ("a2", "karyawan"),
            ("b1", "karyawan"),
            ("lone", "karyawan"),
        ]:
            user = create_user(
                db,
                UserCreate(
                    email=f"rt-{key}@t.co", full_name=f"RT {key.upper()}", password=PW, role=role
                ),
                tenant_id=tid,
            )
            ids[key] = str(user.id)
        with tenant_context(tid):
            for client_name, members in [("Klien A", ["a1", "a2"]), ("Klien B", ["b1"])]:
                klien = Client(name=client_name, tenant_id=tid)
                db.add(klien)
                db.flush()
                jo = JobOrder(client_id=klien.id, title="Operator", tenant_id=tid)
                db.add(jo)
                db.flush()
                for key in members:
                    placement = Placement(candidate_id=uuid4(), job_order_id=jo.id, tenant_id=tid)
                    db.add(placement)
                    db.flush()
                    db.add(
                        Employee(
                            employee_no=f"E-{key}",
                            full_name=f"RT {key.upper()}",
                            user_id=UUID(ids[key]),
                            placement_id=placement.id,
                            tenant_id=tid,
                        )
                    )
            db.commit()
        admin = db.execute(select(User).where(User.email == "brian@outsourcing.co.id")).scalar_one()
        ids["admin"] = str(admin.id)
        ids["tenant"] = str(tid)
    finally:
        db.close()
    tokens = {k: _token(client, f"rt-{k}@t.co") for k in ids if k not in ("admin", "tenant")}
    tokens["admin"] = admin_header["Authorization"].split()[1]
    return {"ids": ids, "tokens": tokens}


def _tenant2_admin_token(client) -> str:
    plat = _platform_admin_header(client)
    resp = client.post(
        "/api/v1/platform/tenants",
        headers=plat,
        json={
            "name": "Tenant Dua",
            "slug": "tenant-dua",
            "admin_email": "admin-dua@example.com",
            "admin_full_name": "Admin Dua",
            "admin_password": PW,
        },
    )
    assert resp.status_code == 201, resp.text
    return _token(client, "admin-dua@example.com")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _open(stack: ExitStack, client, token: str, *, hello: bool = True):
    ws = stack.enter_context(client.websocket_connect(f"/api/v1/chat/ws?token={token}"))
    if hello:
        ws.send_json({"type": "hello", "features": ["presence", "typing"]})
        snapshot = ws.receive_json()
        assert snapshot["event"] == "presence.snapshot", snapshot
        ws.snapshot = snapshot
    return ws


def _drain(ws) -> list[dict]:
    """Semua event yang sudah antre sebelum pong."""
    ws.send_json({"type": "ping"})
    out = []
    while True:
        msg = ws.receive_json()
        if msg.get("event") == "pong":
            return out
        out.append(msg)


def _presence_about(events: list[dict], user_id: str) -> list[dict]:
    return [e for e in events if e.get("event") == "presence.updated" and e["user_id"] == user_id]


def _typing(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("event") == "typing"]


def _channel(client, token: str, name: str, member_ids: list[str], ch_type="private") -> str:
    resp = client.post(
        "/api/v1/chat/channels",
        headers=_bearer(token),
        json={"name": name, "channel_type": ch_type, "member_ids": member_ids},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _type(ws, channel_id: str, *, start: bool = True, parent_id=None) -> None:
    ws.send_json(
        {
            "type": "typing.start" if start else "typing.stop",
            "channel_id": channel_id,
            "parent_id": parent_id,
        }
    )


# ---------- presence ----------


def test_snapshot_karyawan_hanya_cohort_dan_ops(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    with ExitStack() as stack:
        for key in ("hr", "fin", "ops", "a2", "b1"):
            _open(stack, client, tok[key])
        a1 = _open(stack, client, tok["a1"])
        seen = {u["user_id"] for u in a1.snapshot["users"]}
        assert seen == {ids["a2"], ids["ops"]}, "karyawan hanya melihat se-proyek + Ops"
        lone = _open(stack, client, tok["lone"])
        assert {u["user_id"] for u in lone.snapshot["users"]} == {ids["ops"]}
        hr = _open(stack, client, tok["hr"])
        assert {ids["a1"], ids["b1"], ids["fin"]} <= {u["user_id"] for u in hr.snapshot["users"]}


def test_presence_update_tidak_bocor_ke_luar_proyek(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        lone = _open(stack, client, tok["lone"])
        hr = _open(stack, client, tok["hr"])
        b1_stack = ExitStack()
        b1 = _open(b1_stack, client, tok["b1"])
        _drain(b1)
        assert not _presence_about(_drain(a1), ids["b1"]), "a1 (Klien A) tidak boleh lihat b1"
        assert not _presence_about(_drain(lone), ids["b1"])
        assert _presence_about(_drain(hr), ids["b1"]) == [
            {"event": "presence.updated", "user_id": ids["b1"], "status": "online"}
        ]
        b1_stack.close()
        rt.clock.advance(11)
        rt.tick()
        assert not _presence_about(_drain(a1), ids["b1"])
        assert _presence_about(_drain(hr), ids["b1"])[0]["status"] == "offline"


def test_presence_tidak_bocor_antar_tenant(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    t2 = _tenant2_admin_token(client)
    with ExitStack() as stack:
        admin1 = _open(stack, client, tok["admin"])
        hr1 = _open(stack, client, tok["hr"])
        admin2 = _open(stack, client, t2)
        assert admin2.snapshot["users"] == [], "tenant lain tidak boleh terlihat"
        events = _drain(admin1) + _drain(hr1)
        assert all(e["user_id"] in ids.values() for e in events if "user_id" in e)
        assert _presence_about(_drain(admin2), ids["hr"]) == []


def test_multi_tab_presence_dan_grace_period(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    with ExitStack() as stack:
        hr = _open(stack, client, tok["hr"])
        tab1_stack, tab2_stack = ExitStack(), ExitStack()
        _open(tab1_stack, client, tok["a1"], hello=False)
        _open(tab2_stack, client, tok["a1"], hello=False)
        assert [e["status"] for e in _presence_about(_drain(hr), ids["a1"])] == ["online"]
        tab1_stack.close()
        assert _presence_about(_drain(hr), ids["a1"]) == [], "tab lain masih terbuka"
        tab2_stack.close()
        rt.clock.advance(5)
        rt.tick()
        assert _presence_about(_drain(hr), ids["a1"]) == [], "masih dalam grace 10 dtk"
        # Reconnect dalam grace (mis. reload) -> tidak ada event sama sekali.
        again = ExitStack()
        _open(again, client, tok["a1"], hello=False)
        rt.clock.advance(20)
        rt.tick()
        assert _presence_about(_drain(hr), ids["a1"]) == []
        again.close()
        rt.clock.advance(11)
        rt.tick()
        assert [e["status"] for e in _presence_about(_drain(hr), ids["a1"])] == ["offline"]


def test_away_agregat_semua_koneksi(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    with ExitStack() as stack:
        hr = _open(stack, client, tok["hr"])
        tab1 = _open(stack, client, tok["a1"])
        tab2 = _open(stack, client, tok["a1"])
        _drain(hr)
        tab1.send_json({"type": "presence.set", "status": "away"})
        _drain(tab1)
        assert _presence_about(_drain(hr), ids["a1"]) == []
        tab2.send_json({"type": "presence.set", "status": "away"})
        _drain(tab2)
        assert [e["status"] for e in _presence_about(_drain(hr), ids["a1"])] == ["away"]
        tab1.send_json({"type": "presence.set", "status": "online"})
        _drain(tab1)
        assert [e["status"] for e in _presence_about(_drain(hr), ids["a1"])] == ["online"]


# ---------- typing ----------


def test_typing_hanya_ke_audience_channel(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Proyek A", [ids["a1"], ids["a2"]])
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        a2 = _open(stack, client, tok["a2"])
        lone = _open(stack, client, tok["lone"])
        b1 = _open(stack, client, tok["b1"])
        hr = _open(stack, client, tok["hr"])
        _type(a1, ch)
        assert _typing(_drain(a1)) == [], "pengirim tidak menerima typing-nya sendiri"
        expected = {
            "event": "typing",
            "channel_id": ch,
            "parent_id": None,
            "user_id": ids["a1"],
            "user_name": "RT A1",
            "state": "start",
        }
        assert _typing(_drain(a2)) == [expected]
        assert _typing(_drain(hr)) == [expected], "staff = audience semua channel tenant"
        assert _typing(_drain(lone)) == [], "karyawan non-member tidak boleh menerima"
        assert _typing(_drain(b1)) == []


def test_typing_strict_penerima_karyawan_di_luar_scope(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    # Staff boleh menggabungkan karyawan beda klien dalam satu channel, tapi
    # mode STRICT: karyawan hanya melihat typing dari user dalam scope-nya.
    ch = _channel(client, tok["admin"], "Campuran", [ids["a1"], ids["b1"]])
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        b1 = _open(stack, client, tok["b1"])
        ops = _open(stack, client, tok["ops"])
        _type(a1, ch)
        _drain(a1)
        assert _typing(_drain(b1)) == []
        assert len(_typing(_drain(ops))) == 1
        _type(b1, ch)
        _drain(b1)
        assert _typing(_drain(a1)) == []


def test_typing_ditolak_non_member_dan_channel_tak_dikenal(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Hanya A1", [ids["a1"]])
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        hr = _open(stack, client, tok["hr"])
        a2 = _open(stack, client, tok["a2"])
        _type(a2, ch)
        rejected = _drain(a2)
        _type(a2, str(uuid4()))
        unknown = _drain(a2)
        assert rejected == unknown == [{"event": "error", "code": "typing_rejected"}]
        assert _typing(_drain(a1)) == [] and _typing(_drain(hr)) == []


def test_typing_ditolak_karyawan_di_channel_broadcast(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["ops"], "Pengumuman", [ids["a1"]], ch_type="broadcast")
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        _type(a1, ch)
        assert _drain(a1) == [{"event": "error", "code": "typing_rejected"}]


def test_typing_channel_tenant_lain_ditolak(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Rahasia", [ids["a1"]])
    t2 = _tenant2_admin_token(client)
    with ExitStack() as stack:
        hr = _open(stack, client, tok["hr"])
        admin2 = _open(stack, client, t2)
        _type(admin2, ch)
        assert _drain(admin2) == [{"event": "error", "code": "typing_rejected"}]
        assert _typing(_drain(hr)) == []


def test_typing_throttle_dan_ttl(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Throttle", [ids["a1"]])
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        hr = _open(stack, client, tok["hr"])
        for _ in range(3):
            _type(a1, ch)
        _drain(a1)
        assert [e["state"] for e in _typing(_drain(hr))] == ["start"], "throttle 3 dtk"
        rt.clock.advance(3.1)
        _type(a1, ch)
        _drain(a1)
        assert [e["state"] for e in _typing(_drain(hr))] == ["start"]
        rt.clock.advance(5)
        rt.tick()
        assert _typing(_drain(hr)) == [], "TTL 6 dtk belum habis sejak refresh terakhir"
        rt.clock.advance(1.5)
        rt.tick()
        assert [e["state"] for e in _typing(_drain(hr))] == ["stop"]


def test_typing_stop_saat_disconnect_dan_stop_eksplisit(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Stop", [ids["a1"], ids["a2"]])
    with ExitStack() as stack:
        hr = _open(stack, client, tok["hr"])
        a2 = _open(stack, client, tok["a2"])
        _type(a2, ch)
        _drain(a2)
        _type(a2, ch, start=False)
        _drain(a2)
        assert [e["state"] for e in _typing(_drain(hr))] == ["start", "stop"]
        a1_stack = ExitStack()
        a1 = _open(a1_stack, client, tok["a1"])
        _type(a1, ch)
        _drain(a1)
        _drain(hr)
        a1_stack.close()
        assert [e["state"] for e in _typing(_drain(hr))] == ["stop"]


def test_kirim_pesan_menghentikan_typing_dan_event_message_terkirim(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Pesan", [ids["a1"]])
    with ExitStack() as stack:
        hr = _open(stack, client, tok["hr"])
        a1 = _open(stack, client, tok["a1"])
        _type(a1, ch)
        _drain(a1)
        _drain(hr)
        resp = client.post(
            f"/api/v1/chat/channels/{ch}/messages",
            headers=_bearer(tok["a1"]),
            json={"content": "halo"},
        )
        assert resp.status_code == 201, resp.text
        events = _drain(hr)
        if not any(e.get("event") == "message.created" for e in events):
            events += _drain(hr)  # jadwal lintas-thread: beri satu putaran lagi
        assert {"event": "message.created", "channel_id": ch} in events
        assert [e["state"] for e in _typing(events)] == ["stop"]


def test_add_member_menginvalidasi_cache_audience(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Bertambah", [ids["a1"]])
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        a2 = _open(stack, client, tok["a2"])
        _type(a1, ch)
        _drain(a1)
        assert _typing(_drain(a2)) == []
        resp = client.post(
            f"/api/v1/chat/channels/{ch}/members",
            headers=_bearer(tok["admin"]),
            json={"user_id": ids["a2"]},
        )
        assert resp.status_code == 200, resp.text
        _type(a1, ch, start=False)
        _type(a1, ch)
        _drain(a1)
        assert [e["state"] for e in _typing(_drain(a2))] == ["stop", "start"]


# ---------- kompatibilitas & keamanan koneksi ----------


def test_klien_tanpa_hello_tetap_dapat_message_tanpa_presence_typing(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Legacy", [ids["a1"]])
    with ExitStack() as stack:
        legacy = _open(stack, client, tok["hr"], hello=False)
        a1 = _open(stack, client, tok["a1"])
        _type(a1, ch)
        _drain(a1)
        resp = client.post(
            f"/api/v1/chat/channels/{ch}/messages",
            headers=_bearer(tok["admin"]),
            json={"content": "pengumuman"},
        )
        assert resp.status_code == 201
        events = _drain(legacy)
        if not events:
            events = _drain(legacy)
        assert events == [{"event": "message.created", "channel_id": ch}]


def test_ws_menolak_platform_admin(client, rt):
    plat = _platform_admin_header(client)["Authorization"].split()[1]
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/api/v1/chat/ws?token={plat}"):
            pass
    assert exc.value.code == 1008


def test_revalidasi_menutup_koneksi_user_nonaktif(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        db = client.testing_session()
        try:
            from app.modules.auth.models import User

            user = db.get(User, UUID(ids["a1"]))
            user.is_active = False
            db.commit()
        finally:
            db.close()
        rt.clock.advance(61)
        rt.tick()
        with pytest.raises(WebSocketDisconnect) as exc:
            a1.receive_json()
        assert exc.value.code == 1008


def test_rate_limit_menutup_1008(client, rt):
    w = _world(client)
    with ExitStack() as stack:
        ws = _open(stack, client, w["tokens"]["a1"])
        for _ in range(21):
            ws.send_json({"type": "ping"})
        received = []
        with pytest.raises(WebSocketDisconnect) as exc:
            while True:
                received.append(ws.receive_json())
        assert exc.value.code == 1008
        assert {"event": "error", "code": "rate_limited"} in received


def test_koneksi_idle_ditutup_setelah_70_detik(client, rt):
    w = _world(client)
    with ExitStack() as stack:
        ws = _open(stack, client, w["tokens"]["a1"])
        rt.clock.advance(71)
        rt.tick()
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 1001


def test_ws_tidak_menahan_sesi_db(client, rt, monkeypatch):
    import app.core.database as database

    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Pool", [ids["a1"]])
    counter = {"open": 0, "close": 0}
    factory = client.testing_session

    def counting_session():
        session = factory()
        counter["open"] += 1
        original_close = session.close

        def close():
            counter["close"] += 1
            original_close()

        session.close = close  # type: ignore[method-assign]
        return session

    monkeypatch.setattr(database, "SessionLocal", counting_session)
    with ExitStack() as stack:
        a1 = _open(stack, client, tok["a1"])
        hr = _open(stack, client, tok["hr"])
        _type(a1, ch)
        _drain(a1)
        _drain(hr)
        assert counter["open"] > 0
        assert counter["open"] == counter["close"], "sesi DB harus ditutup per event"


# ---------- REST yang ikut diperbaiki ----------


def test_create_channel_karyawan_tidak_bisa_ajak_user_di_luar_scope(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    a1 = _bearer(tok["a1"])
    body = {"name": "DM", "channel_type": "dm"}
    resp = client.post(
        "/api/v1/chat/channels", headers=a1, json={**body, "member_ids": [ids["fin"]]}
    )
    assert resp.status_code == 403
    resp = client.post(
        "/api/v1/chat/channels", headers=a1, json={**body, "member_ids": [ids["b1"]]}
    )
    assert resp.status_code == 403
    resp = client.post(
        "/api/v1/chat/channels", headers=a1, json={**body, "member_ids": [ids["a2"]]}
    )
    assert resp.status_code == 201, resp.text


def test_create_channel_menolak_user_tenant_lain(client, rt):
    w = _world(client)
    _tenant2_admin_token(client)
    db = client.testing_session()
    try:
        from app.modules.auth.models import User
        from sqlalchemy import select

        other = db.execute(select(User).where(User.email == "admin-dua@example.com")).scalar_one()
        other_id = str(other.id)
    finally:
        db.close()
    resp = client.post(
        "/api/v1/chat/channels",
        headers=_bearer(w["tokens"]["admin"]),
        json={"name": "Lintas", "channel_type": "private", "member_ids": [other_id]},
    )
    assert resp.status_code == 404


def test_mention_karyawan_dalam_scope_diterima_luar_scope_ditolak(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    ch = _channel(client, tok["admin"], "Mention", [ids["a1"], ids["a2"]])
    a1 = _bearer(tok["a1"])
    url = f"/api/v1/chat/channels/{ch}/messages"
    ok = client.post(url, headers=a1, json={"content": "@RT A2 tolong cek shift"})
    assert ok.status_code == 201, ok.text
    blocked = client.post(url, headers=a1, json={"content": "@RT FIN gaji saya?"})
    assert blocked.status_code == 403


def test_list_channels_menyertakan_dm_user_id(client, rt):
    w = _world(client)
    ids, tok = w["ids"], w["tokens"]
    dm = _channel(client, tok["a1"], "DM A", [ids["a2"]], ch_type="dm")
    group = _channel(client, tok["admin"], "Grup", [ids["a1"]])
    rows = {
        c["id"]: c for c in client.get("/api/v1/chat/channels", headers=_bearer(tok["a1"])).json()
    }
    assert rows[dm]["dm_user_id"] == ids["a2"]
    assert rows[group]["dm_user_id"] is None
    staff_rows = client.get("/api/v1/chat/channels", headers=_bearer(tok["hr"])).json()
    assert next(c for c in staff_rows if c["id"] == dm)["dm_user_id"] is None
