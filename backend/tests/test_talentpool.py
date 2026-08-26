"""Fase 13 — Talent Pool & CV Standardization (PRD §10)."""

import io

from tests.conftest import _auth_header


def _minimal_pdf_bytes(text: str = "Budi Santoso CV") -> bytes:
    """PDF ber-text-layer via reportlab (tanpa LLM) untuk uji deteksi & intake."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 780, text)
    c.save()
    return buf.getvalue()


def _fake_profile() -> dict:
    return {
        "full_name": "Budi Santoso",
        "phone": "+628123456789",
        "email": "budi@example.com",
        "domisili": "Jakarta",
        "birth_date": "1995-04-12",
        "summary": "Admin operasional 3 tahun.",
        "education": [
            {
                "jenjang": "S1",
                "institusi": "Universitas Indonesia",
                "jurusan": "Manajemen",
                "tahun_lulus": 2017,
            }
        ],
        "experience": [
            {
                "perusahaan": "PT Maju",
                "posisi": "Admin",
                "periode": "2018-2024",
                "ringkasan": "Operasional harian",
            }
        ],
        "skills": ["Excel", "SAP"],
        "certifications": [{"nama": "AHPP", "penerbit": "LSP", "tahun": 2022}],
        "languages": [{"bahasa": "Inggris", "tingkat": "Lancar"}],
        "readiness": "segera",
        "readiness_weeks": None,
        "willing_locations": ["Jakarta", "Bandung"],
        "expected_salary": 6_500_000,
        "contract_preference": "PKWT",
        "confidence": {
            "identitas": 0.9,
            "pendidikan": 0.95,
            "pengalaman": 0.9,
            "skill": 0.85,
            "penempatan": 0.8,
        },
    }


def test_intake_validasi_consent_dan_format(client):
    headers = _auth_header(client)

    no_consent = client.post(
        "/api/v1/talentpool/intake",
        headers=headers,
        files={"file": ("cv.png", io.BytesIO(b"\x89PNG"), "image/png")},
        data={"consent": "false"},
    )
    assert no_consent.status_code == 422

    bad_format = client.post(
        "/api/v1/talentpool/intake",
        headers=headers,
        files={"file": ("cv.txt", io.BytesIO(b"halo"), "text/plain")},
        data={"consent": "true"},
    )
    assert bad_format.status_code == 422


def test_intake_pdf_tanpa_ai_gagal_dan_bisa_reprocess(client):
    headers = _auth_header(client)
    pdf = _minimal_pdf_bytes()

    created = client.post(
        "/api/v1/talentpool/intake",
        headers=headers,
        files={"file": ("cv-budi.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"consent": "true"},
    )
    assert created.status_code == 201, created.text
    data = created.json()
    # AI tidak dikonfigurasi → intake gagal tercatat + bisa diproses ulang
    assert data["status"] == "gagal"
    assert "AI" in (data["error"] or "")

    reproc = client.post(f"/api/v1/talentpool/intake/{data['id']}/reprocess")
    if reproc.status_code in (401, 403):
        reproc = client.post(f"/api/v1/talentpool/intake/{data['id']}/reprocess", headers=headers)
    assert reproc.status_code == 200, reproc.text
    assert reproc.json()["status"] == "gagal"  # tetap gagal tanpa AI


def test_pipeline_review_finalize_render_pdf(client, monkeypatch):
    from app.modules.talentpool import service

    monkeypatch.setattr(service, "extract_profile", lambda db, data, kind: _fake_profile())
    headers = _auth_header(client)
    pdf = _minimal_pdf_bytes("Budi Santoso")

    created = client.post(
        "/api/v1/talentpool/intake",
        headers=headers,
        files={"file": ("cv-budi.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"consent": "true"},
    )
    assert created.status_code == 201, created.text
    intake = created.json()
    assert intake["status"] == "menunggu_review"
    assert intake["extracted"]["full_name"] == "Budi Santoso"
    assert intake["candidate_name"] == "Budi Santoso"
    assert intake["tp_status"] == "diproses"

    # Semua confidence tinggi → finalize langsung boleh
    fin = client.post(f"/api/v1/talentpool/intake/{intake['id']}/finalize", headers=headers)
    assert fin.status_code == 200, fin.text
    finalized = fin.json()
    assert finalized["status"] == "finalisasi"
    assert len(finalized["versions"]) == 1
    assert finalized["versions"][0]["seq"] == 1

    dl = client.get(
        f"/api/v1/talentpool/cv-versions/{finalized['versions'][0]['id']}/download",
        headers=headers,
    )
    assert dl.status_code == 200
    assert dl.content[:5] == b"%PDF-"

    # Finalize ulang pada intake final ditolak
    again = client.post(f"/api/v1/talentpool/intake/{intake['id']}/finalize", headers=headers)
    assert again.status_code == 409


def test_finalize_diblokir_sebelum_field_review(client, monkeypatch):
    from app.modules.talentpool import service

    raw = _fake_profile()
    # Penempatan kosong → confidence rendah → wajib review
    raw["readiness"] = None
    raw["willing_locations"] = []
    raw["expected_salary"] = None
    monkeypatch.setattr(service, "extract_profile", lambda db, data, kind: raw)

    headers = _auth_header(client)
    pdf = _minimal_pdf_bytes()
    created = client.post(
        "/api/v1/talentpool/intake",
        headers=headers,
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"consent": "true"},
    )
    intake = created.json()
    assert "penempatan" in intake["needs_review"]

    blocked = client.post(f"/api/v1/talentpool/intake/{intake['id']}/finalize", headers=headers)
    assert blocked.status_code == 422
    assert "penempatan" in blocked.json()["detail"]

    # Koreksi recruiter mengisi penempatan → skor naik → finalize lolos
    review = client.post(
        f"/api/v1/talentpool/intake/{intake['id']}/review",
        headers=headers,
        json={
            "corrections": {"readiness": "n_minggu", "readiness_weeks": 2},
            "reviewed": [],
        },
    )
    assert review.status_code == 200, review.text
    assert review.json()["needs_review"] == []

    fin = client.post(f"/api/v1/talentpool/intake/{intake['id']}/finalize", headers=headers)
    assert fin.status_code == 200


def test_facet_list_dan_hak_hapus_uu_pdp(client, monkeypatch):
    from app.modules.talentpool import service

    monkeypatch.setattr(service, "extract_profile", lambda db, data, kind: _fake_profile())
    headers = _auth_header(client)
    pdf = _minimal_pdf_bytes()

    client.post(
        "/api/v1/talentpool/intake",
        headers=headers,
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"consent": "true"},
    )

    by_city = client.get("/api/v1/talentpool?domisili=jakarta", headers=headers).json()
    assert len(by_city) == 1 and by_city[0]["city"] == "Jakarta"
    by_skill = client.get("/api/v1/talentpool?skill=sap", headers=headers).json()
    assert len(by_skill) == 1
    none_city = client.get("/api/v1/talentpool?domisili=surabaya", headers=headers).json()
    assert none_city == []

    candidate_id = by_city[0]["candidate_id"]
    forget = client.post(f"/api/v1/talentpool/candidates/{candidate_id}/forget", headers=headers)
    assert forget.status_code == 200, forget.text
    assert forget.json()["intakes"] >= 1

    after = client.get("/api/v1/talentpool", headers=headers).json()
    row = next(r for r in after if r["candidate_id"] == candidate_id)
    assert row["full_name"].startswith("(dihapus")


def test_placement_mengunci_versi_cv_terbaru(client, monkeypatch):
    from app.modules.talentpool import service

    monkeypatch.setattr(service, "extract_profile", lambda db, data, kind: _fake_profile())
    headers = _auth_header(client)

    # Klien + job order + kandidat CV ter-finalisasi
    cl = client.post("/api/v1/clients", headers=headers, json={"name": "PT Klien A"})
    assert cl.status_code == 201, cl.text
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": cl.json()["id"], "title": "Admin"},
    ).json()

    pdf = _minimal_pdf_bytes()
    intake = client.post(
        "/api/v1/talentpool/intake",
        headers=headers,
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"consent": "true"},
    ).json()
    fin = client.post(f"/api/v1/talentpool/intake/{intake['id']}/finalize", headers=headers).json()
    version_id = fin["versions"][0]["id"]
    candidate_id = fin["candidate_id"]

    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": candidate_id, "job_order_id": jo["id"]},
    )
    assert placement.status_code == 201, placement.text

    from uuid import UUID

    from sqlalchemy import select

    db = client.testing_session()
    try:
        from app.modules.talentpool.models import StandardCvVersion

        row = db.execute(
            select(StandardCvVersion).where(StandardCvVersion.id == UUID(version_id))
        ).scalar_one()
        assert row.is_locked is True
        assert str(row.locked_for_placement_id) == placement.json()["id"]
    finally:
        db.close()


def test_branding_default_dan_update(client):
    headers = _auth_header(client)
    default = client.get("/api/v1/talentpool/branding", headers=headers).json()
    assert default["accent_color"]

    upd = client.put(
        "/api/v1/talentpool/branding",
        headers=headers,
        json={"accent_color": "#0F62FE", "footer_text": "CV resmi PT Contoh"},
    )
    assert upd.status_code == 200
    assert upd.json()["accent_color"] == "#0F62FE"
    assert upd.json()["footer_text"] == "CV resmi PT Contoh"

    bad = client.put(
        "/api/v1/talentpool/branding",
        headers=headers,
        json={"accent_color": "merah"},
    )
    assert bad.status_code == 422


_PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd400000000"
    "49454e44ae426082"
)


def test_logo_upload_render_dan_hapus(client, monkeypatch):
    from app.modules.talentpool import service

    monkeypatch.setattr(service, "extract_profile", lambda db, data, kind: _fake_profile())
    admin = _auth_header(client)

    # Format salah ditolak
    bad = client.post(
        "/api/v1/talentpool/branding/logo",
        headers=admin,
        files={"file": ("logo.gif", b"GIF89a", "image/gif")},
    )
    assert bad.status_code == 422

    up = client.post(
        "/api/v1/talentpool/branding/logo",
        headers=admin,
        files={"file": ("logo.png", _PNG_1PX, "image/png")},
    )
    assert up.status_code == 201, up.text
    assert up.json()["has_logo"] is True
    assert up.json()["logo_url"]

    preview = client.get(up.json()["logo_url"], headers=admin)
    assert preview.status_code == 200
    assert preview.content[:4] == b"\x89PNG"

    # Finalize dengan logo → PDF tetap ter-render (logo di header)
    pdf = _minimal_pdf_bytes()
    intake = client.post(
        "/api/v1/talentpool/intake",
        headers=admin,
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"consent": "true"},
    ).json()
    fin = client.post(f"/api/v1/talentpool/intake/{intake['id']}/finalize", headers=admin)
    assert fin.status_code == 200, fin.text
    dl = client.get(
        f"/api/v1/talentpool/cv-versions/{fin.json()['versions'][0]['id']}/download",
        headers=admin,
    )
    assert dl.status_code == 200
    assert dl.content[:5] == b"%PDF-"

    # Hapus logo → has_logo false
    rm = client.delete("/api/v1/talentpool/branding/logo", headers=admin)
    assert rm.status_code == 204
    after = client.get("/api/v1/talentpool/branding", headers=admin).json()
    assert after["has_logo"] is False


def test_normalize_and_score_unit():
    from app.modules.talentpool.service import normalize_and_score

    raw = {
        "full_name": "",
        "email": "bukan-email",
        "phone": "08x",
        "skills": [],
        "readiness": "salah",
        "confidence": {"identitas": 0.8, "skill": 0.9, "penempatan": 0.9},
    }
    profile, groups, needs = normalize_and_score(raw)
    assert profile["email"] is None  # email invalid dibuang
    assert groups["skill"] < 0.7  # skills kosong → turun
    assert "skill" in needs and "penempatan" in needs


def test_foto_kandidat_toggle_show_photo(client, monkeypatch):
    """Polish §10.3: foto tampil di CV hanya bila branding show_photo aktif."""
    from app.modules.talentpool import service

    monkeypatch.setattr(service, "extract_profile", lambda db, data, kind: _fake_profile())
    admin = _auth_header(client)

    bad = client.post(
        "/api/v1/talentpool/candidates/photo-x/photo",
        headers=admin,
        files={"file": ("p.png", _PNG_1PX, "image/png")},
    )
    assert bad.status_code == 404  # kandidat tidak dikenal dicek sebelum simpan

    pdf = _minimal_pdf_bytes()
    intake = client.post(
        "/api/v1/talentpool/intake",
        headers=admin,
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"consent": "true"},
    ).json()
    candidate_id = intake["candidate_id"]

    up = client.post(
        f"/api/v1/talentpool/candidates/{candidate_id}/photo",
        headers=admin,
        files={"file": ("pas-foto.png", _PNG_1PX, "image/png")},
    )
    assert up.status_code == 201, up.text
    preview = client.get(f"/api/v1/talentpool/candidates/{candidate_id}/photo/download")
    if preview.status_code in (401, 403):
        preview = client.get(
            f"/api/v1/talentpool/candidates/{candidate_id}/photo/download", headers=admin
        )
    assert preview.status_code == 200
    assert preview.content[:4] == b"\x89PNG"

    # Tanpa show_photo → finalize tetap jalan (foto diabaikan)
    fin1 = client.post(f"/api/v1/talentpool/intake/{intake['id']}/finalize", headers=admin)
    assert fin1.status_code == 200

    # Aktifkan toggle lalu finalize CV baru dari intake kedua
    client.put("/api/v1/talentpool/branding", headers=admin, json={"show_photo": True})
    intake2 = client.post(
        "/api/v1/talentpool/intake",
        headers=admin,
        files={"file": ("cv2.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
        data={"consent": "true", "candidate_id": candidate_id},
    ).json()
    fin2 = client.post(f"/api/v1/talentpool/intake/{intake2['id']}/finalize", headers=admin)
    assert fin2.status_code == 200, fin2.text
    dl = client.get(
        f"/api/v1/talentpool/cv-versions/{fin2.json()['versions'][0]['id']}/download",
        headers=admin,
    )
    assert dl.content[:5] == b"%PDF-"

    rm = client.delete(f"/api/v1/talentpool/candidates/{candidate_id}/photo", headers=admin)
    assert rm.status_code == 200
    assert rm.json()["has_photo"] is False
