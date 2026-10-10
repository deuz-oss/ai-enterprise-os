"""Baca KTP/NPWP saat unggah di onboarding self-service (hrd/doc_extract.py, AI #9)."""

import io
from datetime import date

import app.core.llm as llm
import pytest
from app.modules.hrd.doc_extract import nik_birth_date_matches

from tests.conftest import _auth_header
from tests.test_hrd_onboarding import _create_invite

PNG = b"\x89PNG\r\n\x1a\n fake ktp photo"


def _upload(client, token, doc_type="ktp", extract=True, name="ktp.png", mime="image/png"):
    data = {"document_type": doc_type}
    if extract is not None:
        data["extract"] = "true" if extract else "false"
    resp = client.post(
        f"/api/v1/onboarding/{token}/documents",
        files={"file": (name, io.BytesIO(PNG), mime)},
        data=data,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def vision(monkeypatch):
    """AI aktif + vision palsu; `calls` mencatat setiap panggilan."""
    state: dict = {"reply": {}, "calls": 0}

    def fake(**kwargs):
        state["calls"] += 1
        return state["reply"]

    monkeypatch.setattr(llm, "ai_configured", lambda: True)
    monkeypatch.setattr(llm, "vision_completion", lambda *a, **k: fake(**k))
    return state


def test_nothing_is_sent_to_ai_without_explicit_permission(client, vision):
    _, token = _create_invite(client, _auth_header(client))
    for extract in (None, False):
        assert _upload(client, token, extract=extract)["extraction"] is None
    assert vision["calls"] == 0


def test_ktp_fields_validated_and_mapped_to_form(client, vision):
    _, token = _create_invite(client, _auth_header(client))  # kandidat "Citra Lestari"
    vision["reply"] = {
        "nik": "3201 0145 0790 0001",  # perempuan: tanggal 05 + 40 = 45
        "nama": "CITRA LESTARI",
        "tanggal_lahir": "1990-07-05",
        "alamat": "JL. MAWAR NO. 5",
        "rt_rw": "003/004",
        "kelurahan": "CIBUBUR",
        "kecamatan": "CIRACAS",
        "kota": "JAKARTA TIMUR",
        "provinsi": "DKI JAKARTA",
    }
    out = _upload(client, token)["extraction"]
    assert out["status"] == "ok"
    assert out["warnings"] == []
    assert out["fields"]["ktp_no"] == "3201014507900001"
    assert out["fields"]["citizen_address"] == {
        "province": "DKI JAKARTA",
        "city": "JAKARTA TIMUR",
        "district": "CIRACAS",
        "detail": "JL. MAWAR NO. 5, RT/RW 003/004, CIBUBUR",
    }
    # Hasil baca TIDAK disimpan: data onboarding tetap kosong sampai kandidat submit.
    assert client.get(f"/api/v1/onboarding/{token}").json()["submitted_data"] == {}


def test_ktp_nik_checks(client, vision):
    _, token = _create_invite(client, _auth_header(client))
    vision["reply"] = {"nik": "3201010507900001", "tanggal_lahir": "1991-07-05"}
    out = _upload(client, token)["extraction"]
    assert out["fields"]["ktp_no"] == "3201010507900001"
    assert any("Tanggal lahir di NIK" in w for w in out["warnings"])

    vision["reply"] = {"nik": "320101050790001"}  # 15 digit
    out = _upload(client, token)["extraction"]
    assert "ktp_no" not in out["fields"] and out["status"] == "failed"
    assert any("15 digit" in w for w in out["warnings"])


def test_npwp_digits_and_name_mismatch(client, vision):
    _, token = _create_invite(client, _auth_header(client))
    vision["reply"] = {"npwp": "09.123.456.7-890.000", "nama": "BUDI SANTOSO"}
    out = _upload(client, token, doc_type="npwp", name="npwp.jpg", mime="image/jpeg")["extraction"]
    assert out["fields"]["npwp_no"] == "091234567890000"
    assert any("berbeda dari nama kandidat" in w for w in out["warnings"])


def test_pdf_and_other_types_are_not_sent_to_ai(client, vision):
    _, token = _create_invite(client, _auth_header(client))
    out = _upload(client, token, name="ktp.pdf", mime="application/pdf")["extraction"]
    assert out["status"] == "unsupported"
    out = _upload(client, token, doc_type="skck")["extraction"]
    assert out["status"] == "unsupported"
    assert vision["calls"] == 0


def test_ai_off_hides_option_and_skips_extraction(client, monkeypatch):
    _, token = _create_invite(client, _auth_header(client))
    assert client.get(f"/api/v1/onboarding/{token}").json()["ai_extraction_available"] is False
    out = _upload(client, token)["extraction"]
    assert out["status"] == "ai_off"


def test_vision_failure_does_not_fail_upload(client, monkeypatch):
    monkeypatch.setattr(llm, "ai_configured", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(llm, "vision_completion", boom)
    _, token = _create_invite(client, _auth_header(client))
    body = _upload(client, token)
    assert body["document_type"] == "ktp"
    assert body["extraction"]["status"] == "failed"


@pytest.mark.parametrize(
    ("nik", "birth", "ok"),
    [
        ("3201010507900001", date(1990, 7, 5), True),
        ("3201014507900001", date(1990, 7, 5), True),  # perempuan
        ("3201010507900001", date(1990, 7, 6), False),
        ("3201010507010001", date(2001, 7, 5), True),
    ],
)
def test_nik_birth_date_matches(nik, birth, ok):
    assert nik_birth_date_matches(nik, birth) is ok
