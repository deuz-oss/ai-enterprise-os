"""Test modul AI: screening kandidat, matching, RAG kontrak, forecast arus kas.

LLM dan storage di-mock agar test tidak butuh provider AI sungguhan.
"""

import json
from datetime import date
from unittest.mock import patch

from app.core.config import get_settings

from tests.conftest import _auth_header

_CV_TEXT = (
    b"BUDI SANTOSO\n"
    b"Pengalaman 5 tahun sebagai Operator Produksi di PT Maju Jaya.\n"
    b"Keahlian: forklift, QC, K3. Pendidikan SMA Negeri 1 Surabaya.\n"
)

_CONTRACT_TEXT = (
    b"PERJANJIAN KERJA POKOK\n"
    b"Pasal 1: Gaji pokok karyawan adalah Rp5.000.000 per bulan.\n"
    b"Pasal 2: Masa kontrak berlaku 12 bulan sejak tanggal mulai.\n"
    b"Pasal 3: Tunjangan transportasi Rp500.000 per bulan.\n"
)


def _client_id(client, headers) -> str:
    resp = client.post("/api/v1/clients", headers=headers, json={"name": "PT Pemberi Kerja"})
    return resp.json()["id"]


def _create_jo(client, headers, client_id, title="Operator Produksi") -> str:
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": client_id,
            "title": title,
            "headcount": 2,
            "requirements": "Pengalaman operator pabrik minimal 2 tahun",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_candidate(client, headers, name="Budi") -> str:
    resp = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": name, "skills": "forklift, QC"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _upload_cv(client, headers, cand_id) -> None:
    with patch("app.modules.recruitment.service.storage.put_object") as put:
        put.return_value = f"candidates/{cand_id}/cv.txt"
        resp = client.post(
            f"/api/v1/recruitment/candidates/{cand_id}/cv",
            headers=headers,
            files={"file": ("cv-budi.txt", _CV_TEXT, "text/plain")},
        )
    assert resp.status_code == 200, resp.text


def _llm_result(score: int, verdict: str) -> dict:
    return {
        "score": score,
        "verdict": verdict,
        "summary": "Kandidat relevan dengan kebutuhan.",
        "strengths": ["Pengalaman sesuai"],
        "risks": ["Ekspektasi gaji di batas atas"],
    }


def test_screen_tanpa_konfigurasi_ai_mengembalikan_503(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)
    _upload_cv(client, headers, cand_id)

    settings = get_settings()
    with (
        patch.object(settings, "ai_base_url", None),
        patch("app.modules.ai.service.get_object") as get_obj,
    ):
        get_obj.return_value = _CV_TEXT
        resp = client.post(
            f"/api/v1/ai/candidates/{cand_id}/screen", headers=headers, json={}
        )
    assert resp.status_code == 503


def test_screen_butuh_cv(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)

    resp = client.post(f"/api/v1/ai/candidates/{cand_id}/screen", headers=headers, json={})
    assert resp.status_code == 422
    assert "CV" in resp.json()["detail"]


def test_screen_sukses_tersimpan_dan_update_status(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)
    _upload_cv(client, headers, cand_id)

    with (
        patch("app.modules.ai.service.chat_completion") as llm,
        patch("app.modules.ai.service.get_object") as get_obj,
    ):
        llm.return_value = _llm_result(82, "direkomendasikan")
        get_obj.return_value = _CV_TEXT
        resp = client.post(f"/api/v1/ai/candidates/{cand_id}/screen", headers=headers, json={})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["score"] == 82
    assert body["verdict"] == "direkomendasikan"
    assert body["strengths"] == ["Pengalaman sesuai"]
    assert body["risks"] == ["Ekspektasi gaji di batas atas"]
    assert body["model"] == "gpt-4o-mini"

    # Kandidat baru otomatis masuk tahap screening
    cand = client.get(f"/api/v1/recruitment/candidates/{cand_id}", headers=headers).json()
    assert cand["status"] == "screening"

    # Riwayat screening tercatat
    history = client.get(f"/api/v1/ai/candidates/{cand_id}/screenings", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_screen_pdf_rusak_mengembalikan_422(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)
    _upload_cv(client, headers, cand_id)

    with patch("app.modules.ai.service.get_object") as get_obj:
        get_obj.return_value = b"%PDF-1.4 konten rusak"
        resp = client.post(f"/api/v1/ai/candidates/{cand_id}/screen", headers=headers, json={})
    assert resp.status_code == 422


def test_verdict_tidak_valid_fallback_berdasar_skor(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)
    _upload_cv(client, headers, cand_id)

    with (
        patch("app.modules.ai.service.chat_completion") as llm,
        patch("app.modules.ai.service.get_object") as get_obj,
    ):
        llm.return_value = {"score": 30, "verdict": "hmm", "summary": "-"}
        get_obj.return_value = _CV_TEXT
        resp = client.post(f"/api/v1/ai/candidates/{cand_id}/screen", headers=headers, json={})

    assert resp.status_code == 200
    assert resp.json()["verdict"] == "tidak_direkomendasikan"


def test_match_job_order_ranking_dan_reuse(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)

    c1 = _create_candidate(client, headers, "Andi")
    _upload_cv(client, headers, c1)
    c2 = _create_candidate(client, headers, "Citra")
    _upload_cv(client, headers, c2)

    with (
        patch("app.modules.ai.service.chat_completion") as llm,
        patch("app.modules.ai.service.get_object") as get_obj,
    ):
        # Panggilan pertama untuk Andi (skor rendah), kedua untuk Citra (tinggi).
        llm.side_effect = [_llm_result(55, "dipertimbangkan"), _llm_result(91, "direkomendasikan")]
        get_obj.return_value = _CV_TEXT
        first = client.post(f"/api/v1/ai/job-orders/{jo_id}/match", headers=headers)
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["evaluated"] == 2
        assert body["reused"] == 0
        # Terurut menurun berdasarkan skor
        assert body["results"][0]["candidate"]["full_name"] == "Citra"
        assert body["results"][0]["screening"]["score"] == 91
        assert llm.call_count == 2

        # Menjalankan ulang memakai hasil lama → tidak ada panggilan LLM baru
        second = client.post(f"/api/v1/ai/job-orders/{jo_id}/match", headers=headers)
        assert second.status_code == 200
        body2 = second.json()
        assert body2["reused"] == 2
        assert body2["results"][0]["candidate"]["full_name"] == "Citra"
        assert llm.call_count == 2  # tetap 2


def test_match_mengabaikan_kandidat_nonaktif(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)

    aktif = _create_candidate(client, headers, "Aktif")
    _upload_cv(client, headers, aktif)
    gagal = _create_candidate(client, headers, "Gagal")
    client.patch(
        f"/api/v1/recruitment/candidates/{gagal}", headers=headers, json={"status": "gagal"}
    )

    with (
        patch("app.modules.ai.service.chat_completion") as llm,
        patch("app.modules.ai.service.get_object") as get_obj,
    ):
        llm.return_value = _llm_result(70, "dipertimbangkan")
        get_obj.return_value = _CV_TEXT
        resp = client.post(f"/api/v1/ai/job-orders/{jo_id}/match", headers=headers)

    assert resp.status_code == 200
    names = [item["candidate"]["full_name"] for item in resp.json()["results"]]
    assert names == ["Aktif"]


def test_match_tanpa_kandidat_aktif_mengembalikan_422(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)

    resp = client.post(f"/api/v1/ai/job-orders/{jo_id}/match", headers=headers)
    assert resp.status_code == 422


def test_endpoint_ai_butuh_role_recruiter(client):
    """Role hr tidak boleh menjalankan screening (khusus recruiter/management)."""
    admin = _auth_header(client)
    cand_id = _create_candidate(client, admin)

    reg = client.post(
        "/api/v1/auth/register",
        headers=admin,
        json={
            "email": "hr@example.com",
            "full_name": "HR Staff",
            "password": "password123",
            "role": "hr",
        },
    )
    assert reg.status_code == 201, reg.text
    login = client.post(
        "/api/v1/auth/login", json={"email": "hr@example.com", "password": "password123"}
    )
    hr_token = login.json()["access_token"]
    resp = client.post(
        f"/api/v1/ai/candidates/{cand_id}/screen",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={},
    )
    assert resp.status_code == 403


# ---- RAG Q&A kontrak ----


def _employee_with_contract(client, headers, name="Budi Karyawan") -> str:
    """Buat karyawan + kontrak + unggah file kontrak; kembalikan contract_id."""
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": name}
    ).json()
    contract = client.post(
        f"/api/v1/employees/{emp['id']}/contracts", headers=headers, json={}
    ).json()
    with patch("app.modules.hrd.service.storage.put_object") as put:
        put.return_value = f"contracts/{emp['id']}/kontrak.txt"
        resp = client.post(
            f"/api/v1/employees/contracts/{contract['id']}/file",
            headers=headers,
            files={"file": ("kontrak.txt", _CONTRACT_TEXT, "text/plain")},
        )
    assert resp.status_code == 200, resp.text
    return contract["id"]


def test_index_contract_butuh_file(client):
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Tanpa File"}
    ).json()
    contract = client.post(
        f"/api/v1/employees/{emp['id']}/contracts", headers=headers, json={}
    ).json()

    resp = client.post(f"/api/v1/ai/contracts/{contract['id']}/index", headers=headers)
    assert resp.status_code == 422
    assert "file" in resp.json()["detail"].lower()


def test_index_dan_ask_contract(client):
    headers = _auth_header(client)
    contract_id = _employee_with_contract(client, headers)

    vector = [0.0, 1.0]
    with (
        patch("app.modules.ai.rag.get_object") as get_obj,
        patch("app.modules.ai.rag.embed_texts") as embed,
        patch("app.modules.ai.rag.chat_completion") as llm,
    ):
        get_obj.return_value = _CONTRACT_TEXT
        embed.return_value = [vector]
        idx = client.post(f"/api/v1/ai/contracts/{contract_id}/index", headers=headers)
        assert idx.status_code == 200, idx.text
        assert idx.json()["chunks"] == 1

        # Daftar kontrak terindeks
        listed = client.get("/api/v1/ai/contracts/indexed", headers=headers).json()
        assert len(listed) == 1
        assert listed[0]["contract_id"] == contract_id
        assert listed[0]["employee_name"] == "Budi Karyawan"
        assert listed[0]["chunks"] == 1

        # Pertanyaan dijawab dari konteks kontrak
        embed.return_value = [vector]
        llm.return_value = {"answer": "Gaji pokoknya Rp5.000.000 per bulan."}
        ask = client.post(
            "/api/v1/ai/contracts/ask",
            headers=headers,
            json={"question": "Berapa gaji pokok Budi?"},
        )
        assert ask.status_code == 200, ask.text
        body = ask.json()
        assert body["answer"] == "Gaji pokoknya Rp5.000.000 per bulan."
        assert len(body["sources"]) == 1
        assert body["sources"][0]["contract_id"] == contract_id
        assert body["sources"][0]["employee_name"] == "Budi Karyawan"
        assert "Gaji pokok" in body["sources"][0]["snippet"]

        # Re-index mengganti chunk lama (tidak menduplikasi); teks > 1 chunk
        get_obj.return_value = _CONTRACT_TEXT + b"Pasal 5: " + b"klausul tambahan. " * 80
        embed.return_value = [vector, vector]
        reidx = client.post(f"/api/v1/ai/contracts/{contract_id}/index", headers=headers)
        assert reidx.json()["chunks"] == 2
        listed2 = client.get("/api/v1/ai/contracts/indexed", headers=headers).json()
        assert listed2[0]["chunks"] == 2

    # Chunk tersimpan dengan embedding JSON valid (via session test, bukan DB dev)
    from app.modules.ai.models import AIDocumentChunk  # noqa: PLC0415

    with client.testing_session() as db:  # type: ignore[attr-defined]
        rows = db.query(AIDocumentChunk).all()
        assert len(rows) == 2
        for row in rows:
            assert isinstance(json.loads(row.embedding_json), list)


def test_ask_tanpa_indeks_mengembalikan_422(client):
    headers = _auth_header(client)
    resp = client.post(
        "/api/v1/ai/contracts/ask", headers=headers, json={"question": "Gaji siapa?"}
    )
    assert resp.status_code == 422


# ---- Forecast arus kas ----


def _seed_cashflow(client, headers) -> None:
    def shift(y: int, m: int, delta: int) -> tuple[int, int]:
        idx = y * 12 + (m - 1) + delta
        return idx // 12, idx % 12 + 1

    today = date.today()
    pola = [(5_000_000, 3_500_000), (6_000_000, 4_000_000), (7_000_000, 4_500_000)]
    for delta in (-3, -2, -1):
        y, m = shift(today.year, today.month, delta)
        inflow, outflow = pola.pop(0)
        resp_in = client.post(
            "/api/v1/finance/cashflow",
            headers=headers,
            json={
                "direction": "masuk",
                "category": "pembayaran klien",
                "amount": inflow,
                "entry_date": f"{y}-{m:02d}-10",
            },
        )
        assert resp_in.status_code == 201, resp_in.text
        resp_out = client.post(
            "/api/v1/finance/cashflow",
            headers=headers,
            json={
                "direction": "keluar",
                "category": "payrol",
                "amount": outflow,
                "entry_date": f"{y}-{m:02d}-25",
            },
        )
        assert resp_out.status_code == 201, resp_out.text


def test_forecast_arus_kas(client):
    headers = _auth_header(client)
    _seed_cashflow(client, headers)

    with patch("app.modules.ai.forecast.chat_completion") as llm:
        llm.return_value = {
            "outlook": "positif",
            "summary": "Arus kas cenderung membaik.",
            "risks": ["Ketergantungan satu klien"],
            "recommendations": ["Percepat penagihan invoice jatuh tempo"],
        }
        resp = client.post(
            "/api/v1/ai/finance/forecast", headers=headers, json={"months_ahead": 2}
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outlook"] == "positif"
    assert len(body["history"]) == 6
    assert len(body["projection"]) == 2
    total_net_history = sum(h["net"] for h in body["history"])
    assert total_net_history == 6_000_000  # (15jt masuk − 12jt keluar)
    # Proyeksi net positif mengikuti tren naik
    assert all(p["net"] > 0 for p in body["projection"])
    assert body["model"] == "gpt-4o-mini"

    # Role finance diperlukan: hr tidak boleh akses forecast
    reg = client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={
            "email": "hr2@example.com",
            "full_name": "HR Dua",
            "password": "password123",
            "role": "hr",
        },
    )
    assert reg.status_code == 201
    token = client.post(
        "/api/v1/auth/login", json={"email": "hr2@example.com", "password": "password123"}
    ).json()["access_token"]
    denied = client.post(
        "/api/v1/ai/finance/forecast",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert denied.status_code == 403
