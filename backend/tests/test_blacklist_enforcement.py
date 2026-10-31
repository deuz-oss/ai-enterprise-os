"""Blacklist sebagai blocking check (lanjutan Fase 29, PRD §15 Backlog #4).

Aturan yang diuji:
- hanya entri `approved` yang dihitung; identitas (email/telepon/NIK
  ternormalisasi) ikut dicocokkan, bukan cuma `candidate_id`;
- guest apply di job portal DITANDAI (audit internal), respons publik
  identik dengan lamaran normal -- status blacklist tidak boleh bocor;
- pipeline: tambah/majukan placement -> 422, keluarkan (gagal/batal) -> OK;
- matching & talent pool: default disaring, `include_blacklisted=true`
  memunculkan lagi dengan flag (talent pool: hanya RECRUITMENT_ROLES);
- scoping tenant: entri tenant lain tidak berpengaruh.
"""

import io
import json
from unittest.mock import patch

from app.modules.auth.schemas import UserCreate
from app.modules.blacklist.matching import normalize_email, normalize_nik, normalize_phone
from sqlalchemy import select

from tests.conftest import _auth_header, _login_header, _seed_user_idempotent
from tests.test_ai import _CV_TEXT, _upload_cv
from tests.test_platform import _login, _provision

BLOCK_DETAIL = (
    "Kandidat ini masuk daftar Blacklist (disetujui) dan tidak bisa diusulkan ke job order."
)


# ---------------- helper ----------------


def _create_client(client, headers, name="PT Klien Blacklist") -> str:
    resp = client.post("/api/v1/clients", headers=headers, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_jo(client, headers, client_id, *, is_public=False, title="Operator Gudang") -> str:
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": client_id,
            "title": title,
            "headcount": 1,
            "requirements": "operator gudang forklift",
            "is_public": is_public,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_candidate(client, headers, name, **fields) -> str:
    resp = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": name, "skills": "operator gudang forklift", **fields},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _blacklist(client, headers, candidate_id, decision="disetujui") -> None:
    req = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": candidate_id, "reason": "Kabur saat OJT"},
    )
    assert req.status_code == 200, req.text
    if decision is None:
        return
    rev = client.post(
        f"/api/v1/blacklist/entries/{req.json()['id']}/review",
        headers=headers,
        json={"decision": decision},
    )
    assert rev.status_code == 200, rev.text


def _apply(client, jo_id, *, email, phone=None, name="Pelamar Portal", slug="default"):
    data = {
        "full_name": name,
        "email": email,
        "consent": "true",
        "screening_answers": "{}",
    }
    if phone is not None:
        data["phone"] = phone
    return client.post(
        f"/api/v1/public/{slug}/job-orders/{jo_id}/apply",
        data=data,
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 cv"), "application/pdf")},
    )


def _flag_events(client) -> list:
    from app.modules.audit.models import AuditLog

    db = client.testing_session()
    try:
        return list(
            db.execute(
                select(AuditLog).where(AuditLog.action == "blacklist.portal_apply_flagged")
            ).scalars()
        )
    finally:
        db.close()


def _role_header(client, role: str) -> dict[str, str]:
    from app.core.bootstrap import ensure_default_tenant

    email = f"{role}-bl@example.com"
    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        _seed_user_idempotent(
            db,
            UserCreate(email=email, full_name=role, password="rahasia-123", role=role),
            tenant_id=tenant.id,
        )
    finally:
        db.close()
    return _login_header(client, email, "rahasia-123")


# ---------------- normalisasi ----------------


def test_normalisasi_identitas():
    assert normalize_email("  Budi@Example.COM ") == "budi@example.com"
    assert normalize_email("   ") is None
    expected = "081234567890"
    for raw in ("+62 812-3456-7890", "62812 3456 7890", "0812.3456.7890", "812-3456-7890"):
        assert normalize_phone(raw) == expected, raw
    assert normalize_phone("12345") is None  # terlalu pendek -> diabaikan
    assert normalize_phone(None) is None
    assert normalize_nik("3171-0123-4567-8901") == "3171012345678901"
    assert normalize_nik("317101234567890") is None  # 15 digit -> diabaikan
    assert normalize_nik(None) is None


# ---------------- guest apply (job portal) ----------------


def test_portal_apply_kandidat_blacklist_respons_identik_dan_ditandai(client):
    admin = _auth_header(client)
    jo_id = _create_jo(client, admin, _create_client(client, admin), is_public=True)

    bad = _create_candidate(client, admin, "Pelamar Bermasalah", phone="+62 811-2222-3333")
    _blacklist(client, admin, bad)

    normal = _apply(client, jo_id, email="normal@example.com", name="Pelamar Normal")
    # Email baru (profil Candidate baru), tapi telepon sama dgn kandidat ter-blacklist.
    flagged = _apply(client, jo_id, email="baru@example.com", phone="0811 2222 3333")

    assert normal.status_code == flagged.status_code == 200, flagged.text
    assert normal.json().keys() == flagged.json().keys()
    assert normal.json()["message"] == flagged.json()["message"]

    # Cek status publik juga tidak membedakan.
    s_normal = client.get(f"/api/v1/public/applications/{normal.json()['application_token']}")
    s_flagged = client.get(f"/api/v1/public/applications/{flagged.json()['application_token']}")
    assert s_normal.status_code == s_flagged.status_code == 200
    assert s_normal.json()["status_label"] == s_flagged.json()["status_label"]
    assert "blacklist" not in str(s_flagged.json()).lower()
    assert "blacklist" not in flagged.text.lower()

    events = _flag_events(client)
    assert len(events) == 1
    assert json.loads(events[0].detail_json)["matched_by"] == ["phone"]

    # Recruiter melihat flag di placement hasil portal.
    placements = client.get(
        "/api/v1/recruitment/placements", headers=admin, params={"job_order_id": jo_id}
    ).json()
    flags = {p["candidate_is_blacklisted"] for p in placements}
    assert flags == {True, False}


def test_portal_apply_entri_pending_atau_ditolak_tidak_menandai(client):
    admin = _auth_header(client)
    jo_id = _create_jo(client, admin, _create_client(client, admin), is_public=True)

    pending = _create_candidate(client, admin, "Pending", email="pending@example.com")
    _blacklist(client, admin, pending, decision=None)
    rejected = _create_candidate(client, admin, "Ditolak", email="ditolak@example.com")
    _blacklist(client, admin, rejected, decision="ditolak")

    assert _apply(client, jo_id, email="PENDING@example.com").status_code == 200
    assert _apply(client, jo_id, email="ditolak@example.com").status_code == 200
    assert _flag_events(client) == []


def test_portal_apply_blacklist_tenant_lain_tidak_berpengaruh(client):
    admin_a = _auth_header(client)
    jo_a = _create_jo(client, admin_a, _create_client(client, admin_a), is_public=True)

    _provision(client, "bl-b")
    admin_b = _login(client, "admin-bl-b@example.com")
    cand_b = _create_candidate(client, admin_b, "Hitam di B", email="lintas@example.com")
    _blacklist(client, admin_b, cand_b)

    resp = _apply(client, jo_a, email="lintas@example.com")
    assert resp.status_code == 200, resp.text
    assert _flag_events(client) == []

    placements = client.get(
        "/api/v1/recruitment/placements", headers=admin_a, params={"job_order_id": jo_a}
    ).json()
    assert [p["candidate_is_blacklisted"] for p in placements] == [False]


# ---------------- pipeline / placement ----------------


def test_create_placement_kandidat_blacklist_422(client):
    admin = _auth_header(client)
    jo_id = _create_jo(client, admin, _create_client(client, admin))
    bad = _create_candidate(client, admin, "Bermasalah", ktp_no="3171012345678901")
    _blacklist(client, admin, bad)
    # Profil duplikat: NIK sama (format beda), email/telepon beda.
    twin = _create_candidate(client, admin, "Kembaran", ktp_no="3171 0123 4567 8901")

    for cand in (bad, twin):
        resp = client.post(
            "/api/v1/recruitment/placements",
            headers=admin,
            json={"candidate_id": cand, "job_order_id": jo_id},
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"] == BLOCK_DETAIL

    detail = client.get(f"/api/v1/recruitment/candidates/{twin}", headers=admin).json()
    assert detail["is_blacklisted"] is True


def test_update_placement_status_kandidat_blacklist(client):
    admin = _auth_header(client)
    jo_id = _create_jo(client, admin, _create_client(client, admin))
    cand = _create_candidate(client, admin, "Sudah Jalan", email="jalan@example.com")
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=admin,
        json={"candidate_id": cand, "job_order_id": jo_id},
    ).json()
    assert placement["candidate_is_blacklisted"] is False

    # Blacklist disetujui SETELAH placement berjalan.
    _blacklist(client, admin, cand)
    url = f"/api/v1/recruitment/placements/{placement['id']}"

    for status in ("screening", "interview_rekruter"):
        resp = client.patch(url, headers=admin, json={"status": status})
        assert resp.status_code == 422, (status, resp.text)
        assert resp.json()["detail"] == BLOCK_DETAIL

    gagal = client.patch(url, headers=admin, json={"status": "gagal", "note": "Blacklist"})
    assert gagal.status_code == 200, gagal.text
    assert gagal.json()["candidate_is_blacklisted"] is True

    # Reaktivasi placement lama ke Sourcing (jalur "Usulkan Kandidat" FE) juga diblok.
    reaktivasi = client.patch(url, headers=admin, json={"status": "disourcing"})
    assert reaktivasi.status_code == 422

    batal = client.patch(url, headers=admin, json={"status": "dibatalkan"})
    assert batal.status_code == 200, batal.text


# ---------------- matching ----------------


def test_recruitment_match_menyaring_kandidat_blacklist(client):
    admin = _auth_header(client)
    jo_id = _create_jo(client, admin, _create_client(client, admin))
    good = _create_candidate(client, admin, "Bersih", email="bersih@example.com")
    bad = _create_candidate(client, admin, "Hitam", email="hitam@example.com")
    _blacklist(client, admin, bad)

    base = f"/api/v1/recruitment/job-orders/{jo_id}"
    default = client.get(f"{base}/matches", headers=admin).json()
    assert {r["candidate_id"] for r in default} == {good}
    assert all(r["is_blacklisted"] is False for r in default)

    posted = client.post(f"{base}/match", headers=admin, json={"top_k": 10})
    assert posted.status_code == 200, posted.text
    assert {r["candidate_id"] for r in posted.json()} == {good}

    with_bl = client.get(
        f"{base}/matches", headers=admin, params={"include_blacklisted": "true"}
    ).json()
    by_id = {r["candidate_id"]: r for r in with_bl}
    assert set(by_id) == {good, bad}
    assert by_id[bad]["is_blacklisted"] is True
    assert by_id[good]["is_blacklisted"] is False


def test_ai_match_menyaring_kandidat_blacklist_sebelum_llm(client):
    admin = _auth_header(client)
    jo_id = _create_jo(client, admin, _create_client(client, admin))
    good = _create_candidate(client, admin, "Bersih AI", email="bersih-ai@example.com")
    bad = _create_candidate(client, admin, "Hitam AI", email="hitam-ai@example.com")
    for cand in (good, bad):
        _upload_cv(client, admin, cand)
    _blacklist(client, admin, bad)

    llm_result = {
        "score": 70,
        "verdict": "dipertimbangkan",
        "summary": "Relevan.",
        "strengths": ["a"],
        "risks": ["b"],
    }
    with (
        patch("app.modules.ai.service.chat_completion", return_value=llm_result) as llm,
        patch("app.modules.ai.service.get_object", return_value=_CV_TEXT),
    ):
        default = client.post(f"/api/v1/ai/job-orders/{jo_id}/match", headers=admin)
        assert default.status_code == 200, default.text
        names = [r["candidate"]["full_name"] for r in default.json()["results"]]
        assert names == ["Bersih AI"]
        assert default.json()["results"][0]["candidate"]["is_blacklisted"] is False
        assert llm.call_count == 1  # kandidat ter-blacklist tidak dinilai LLM

        with_bl = client.post(
            f"/api/v1/ai/job-orders/{jo_id}/match",
            headers=admin,
            params={"include_blacklisted": "true"},
        )
        assert with_bl.status_code == 200, with_bl.text
        flags = {
            r["candidate"]["full_name"]: r["candidate"]["is_blacklisted"]
            for r in with_bl.json()["results"]
        }
        assert flags == {"Bersih AI": False, "Hitam AI": True}


# ---------------- talent pool ----------------


def test_talentpool_menyaring_dan_include_blacklisted_per_role(client):
    admin = _auth_header(client)
    good = _create_candidate(client, admin, "TP Bersih", email="tp-bersih@example.com")
    bad = _create_candidate(client, admin, "TP Hitam", email="tp-hitam@example.com")
    _blacklist(client, admin, bad)

    default = client.get("/api/v1/talentpool", headers=admin).json()
    ids = {r["candidate_id"] for r in default}
    assert good in ids and bad not in ids
    assert all(r["is_blacklisted"] is False for r in default)

    recruiter = _role_header(client, "recruiter")
    with_bl = client.get(
        "/api/v1/talentpool", headers=recruiter, params={"include_blacklisted": "true"}
    )
    assert with_bl.status_code == 200, with_bl.text
    by_id = {r["candidate_id"]: r for r in with_bl.json()}
    assert by_id[bad]["is_blacklisted"] is True
    assert by_id[good]["is_blacklisted"] is False

    for role in ("operations", "hr"):
        headers = _role_header(client, role)
        assert client.get("/api/v1/talentpool", headers=headers).status_code == 200
        forbidden = client.get(
            "/api/v1/talentpool", headers=headers, params={"include_blacklisted": "true"}
        )
        assert forbidden.status_code == 403, (role, forbidden.text)

    detail = client.get(f"/api/v1/talentpool/{bad}", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["is_blacklisted"] is True


def test_candidate_list_menandai_kandidat_blacklist(client):
    admin = _auth_header(client)
    good = _create_candidate(client, admin, "List Bersih", email="list-bersih@example.com")
    bad = _create_candidate(client, admin, "List Hitam", email="list-hitam@example.com")
    _blacklist(client, admin, bad)

    rows = client.get("/api/v1/recruitment/candidates", headers=admin).json()
    flags = {r["id"]: r["is_blacklisted"] for r in rows}
    assert flags[bad] is True
    assert flags[good] is False
