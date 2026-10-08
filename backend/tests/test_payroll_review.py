"""Tinjauan run payroll sebelum finalisasi (audit 2026-10-08 Phase 6)."""

from tests.conftest import _auth_header


def _emp(client, headers, name, salary):
    resp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": name, "base_salary": salary}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _run(client, headers, month):
    run = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": month}
    ).json()
    gen = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    assert gen.status_code == 201, gen.text
    return run


def _setup_two_runs(client, headers):
    emp = _emp(client, headers, "Review Lama", 6_000_000)
    first = _run(client, headers, month=4)
    assert (
        client.post(f"/api/v1/payroll/runs/{first['id']}/finalize", headers=headers).status_code
        == 200
    )

    # Kenaikan gaji 50% + karyawan baru -> dua temuan.
    client.patch(f"/api/v1/employees/{emp['id']}", headers=headers, json={"base_salary": 9_000_000})
    _emp(client, headers, "Review Baru", 5_000_000)
    second = _run(client, headers, month=5)
    return first, second


def test_review_membandingkan_dengan_run_final_sebelumnya(client):
    headers = _auth_header(client)
    first, second = _setup_two_runs(client, headers)

    resp = client.get(f"/api/v1/payroll/runs/{second['id']}/review", headers=headers)
    assert resp.status_code == 200, resp.text
    review = resp.json()

    assert review["compared_to"]["run_id"] == first["id"]
    kinds = {(f["kind"], f["employee_name"]) for f in review["findings"]}
    assert ("net_berubah", "Review Lama") in kinds
    assert ("karyawan_baru", "Review Baru") in kinds
    assert review["totals"]["slips"] == {"current": 2, "previous": 1}
    assert review["totals"]["gross"]["current"] > review["totals"]["gross"]["previous"]
    # AI tidak dikonfigurasi di test -> tanpa ringkasan, temuan tetap ada.
    assert review["summary"] is None
    assert review["summary_source"] == "none"


def test_review_tanpa_run_sebelumnya(client):
    headers = _auth_header(client)
    _emp(client, headers, "Run Pertama", 5_000_000)
    run = _run(client, headers, month=3)
    review = client.get(f"/api/v1/payroll/runs/{run['id']}/review", headers=headers).json()
    assert review["compared_to"] is None
    assert review["totals"]["gross"]["previous"] is None
    # Tanpa pembanding, karyawan tidak ditandai "baru".
    assert not [f for f in review["findings"] if f["kind"] == "karyawan_baru"]


def test_ringkasan_ai_hanya_merangkum_temuan(client, monkeypatch):
    import app.modules.payroll.review as review_module

    captured = {}

    def fake_completion(system, user, **kwargs):
        captured["user"] = user
        captured["feature"] = kwargs.get("feature")
        return "Cek kenaikan net pay Review Lama sebelum finalisasi."

    monkeypatch.setattr(review_module, "ai_configured", lambda: True)
    monkeypatch.setattr(review_module, "chat_completion", fake_completion)

    headers = _auth_header(client)
    _first, second = _setup_two_runs(client, headers)
    review = client.get(f"/api/v1/payroll/runs/{second['id']}/review", headers=headers).json()

    assert review["summary_source"] == "ai"
    assert review["summary"].startswith("Cek kenaikan")
    assert captured["feature"] == "payroll.pre_finalize_review"
    # Konteks ke AI = temuan yang sudah dihitung, bukan data mentah.
    assert "Review Lama" in captured["user"] and "net_berubah" not in captured["user"]
