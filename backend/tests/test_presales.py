from unittest.mock import patch

from app.core.config import get_settings
from app.modules.presales.rendering import render_document_docx, render_document_pdf

from tests.conftest import _auth_header


def _create_lead(client, headers, name="PT Maju Jaya", contact_email=None):
    payload = {
        "company_name": name,
        "industry": "manufaktur",
        "contact_name": "Budi",
        "estimated_headcount": 50,
        "estimated_value": 250_000_000,
    }
    if contact_email is not None:
        payload["contact_email"] = contact_email
    resp = client.post("/api/v1/leads", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_and_list_leads(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers)
    assert lead["stage"] == "lead"

    listed = client.get("/api/v1/leads", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["company_name"] == "PT Maju Jaya"


def test_update_lead_stage(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers)
    updated = client.patch(
        f"/api/v1/leads/{lead['id']}", headers=headers, json={"stage": "negosiasi"}
    )
    assert updated.status_code == 200
    assert updated.json()["stage"] == "negosiasi"


def test_lead_stage_changed_at_set_on_create_and_stage_change(client):
    """Fase 42: `stage_changed_at` terisi otomatis saat lead dibuat, dan
    ter-update lagi setiap kali `stage` benar-benar berubah -- tidak
    berubah kalau field lain yang diupdate."""
    headers = _auth_header(client)
    lead = _create_lead(client, headers)
    assert lead["stage_changed_at"] is not None
    first_stage_changed_at = lead["stage_changed_at"]

    same_stage = client.patch(
        f"/api/v1/leads/{lead['id']}", headers=headers, json={"notes": "update tanpa ganti tahap"}
    ).json()
    assert same_stage["stage_changed_at"] == first_stage_changed_at

    changed = client.patch(
        f"/api/v1/leads/{lead['id']}", headers=headers, json={"stage": "negosiasi"}
    ).json()
    assert changed["stage_changed_at"] != first_stage_changed_at


def test_lead_last_activity_at_updates_on_activity_and_stage_change(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers)
    assert lead["last_activity_at"] is not None
    baseline = lead["last_activity_at"]

    client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={"activity_type": "telepon", "content": "Follow up telepon"},
    )
    after_activity = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()
    assert after_activity["last_activity_at"] != baseline


def test_lead_expected_close_date_and_closed_reason_settable(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers)

    updated = client.patch(
        f"/api/v1/leads/{lead['id']}",
        headers=headers,
        json={"expected_close_date": "2026-12-01", "stage": "deal", "closed_reason": "Harga cocok"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["expected_close_date"] == "2026-12-01"
    assert body["closed_reason"] == "Harga cocok"


def test_lead_stage_changed_at_not_spoofable_via_update(client):
    """`stage_changed_at` bukan bagian `LeadUpdate` -- klien yang kirim
    field ini di body PATCH harus diabaikan, dihitung ulang server."""
    headers = _auth_header(client)
    lead = _create_lead(client, headers)
    resp = client.patch(
        f"/api/v1/leads/{lead['id']}",
        headers=headers,
        json={"stage_changed_at": "2020-01-01T00:00:00Z", "notes": "x"},
    )
    assert resp.status_code == 200
    assert resp.json()["stage_changed_at"] != "2020-01-01T00:00:00Z"


def test_activity_and_funnel(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers)
    act = client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={"activity_type": "meeting", "content": "Presentasi ke HRD klien"},
    )
    assert act.status_code == 201

    activities = client.get(f"/api/v1/leads/{lead['id']}/activities", headers=headers).json()
    assert len(activities) == 1

    funnel = client.get("/api/v1/leads/funnel", headers=headers).json()
    assert funnel["total_leads"] == 1
    stage_counts = {s["stage"]: s["count"] for s in funnel["stages"]}
    assert stage_counts["lead"] == 1


def test_activity_with_due_date_appears_in_due_tasks(client):
    """Fase 43: aktivitas dengan `due_at` muncul di daftar tugas jatuh
    tempo lintas lead, aktivitas biasa (tanpa due_at) tidak."""
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Follow Up")
    client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={"activity_type": "catatan", "content": "Catatan biasa tanpa due date"},
    )
    task = client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={
            "activity_type": "tugas",
            "content": "Telepon follow up harga",
            "due_at": "2026-12-25T09:00:00Z",
        },
    )
    assert task.status_code == 201, task.text
    assert task.json()["due_at"] is not None
    assert task.json()["completed_at"] is None

    due_tasks = client.get("/api/v1/leads/activities/due", headers=headers).json()
    assert len(due_tasks) == 1
    assert due_tasks[0]["content"] == "Telepon follow up harga"
    assert due_tasks[0]["company_name"] == "PT Follow Up"


def test_complete_activity_removes_it_from_due_tasks(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Tugas Selesai")
    task = client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={
            "activity_type": "tugas",
            "content": "Kirim ulang quotation",
            "due_at": "2026-11-01T00:00:00Z",
        },
    ).json()

    assert len(client.get("/api/v1/leads/activities/due", headers=headers).json()) == 1

    completed = client.patch(
        f"/api/v1/leads/activities/{task['id']}", headers=headers, json={"completed": True}
    )
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None

    assert client.get("/api/v1/leads/activities/due", headers=headers).json() == []
    with_completed = client.get(
        "/api/v1/leads/activities/due", headers=headers, params={"include_completed": True}
    ).json()
    assert len(with_completed) == 1

    reopened = client.patch(
        f"/api/v1/leads/activities/{task['id']}", headers=headers, json={"completed": False}
    )
    assert reopened.json()["completed_at"] is None
    assert len(client.get("/api/v1/leads/activities/due", headers=headers).json()) == 1


def test_due_tasks_overdue_only_filter(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Overdue")
    client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={"activity_type": "tugas", "content": "Sudah lewat", "due_at": "2020-01-01T00:00:00Z"},
    )
    client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        headers=headers,
        json={"activity_type": "tugas", "content": "Masih jauh", "due_at": "2099-01-01T00:00:00Z"},
    )
    overdue = client.get(
        "/api/v1/leads/activities/due", headers=headers, params={"overdue_only": True}
    ).json()
    assert len(overdue) == 1
    assert overdue[0]["content"] == "Sudah lewat"


def test_search_leads(client):
    headers = _auth_header(client)
    _create_lead(client, headers, "PT ABC")
    _create_lead(client, headers, "CV XYZ")
    result = client.get("/api/v1/leads", headers=headers, params={"q": "abc"}).json()
    assert len(result) == 1
    assert result[0]["company_name"] == "PT ABC"


def test_create_lead_inline_creates_company_and_primary_contact(client):
    """Fase 20 item 1: lead dibuat tanpa company_id -> company+contact baru
    otomatis dibuat, lead.company_id nunjuk ke company itu."""
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Maju Jaya")

    company = client.get(f"/api/v1/companies/{lead['company_id']}", headers=headers).json()
    assert company["name"] == "PT Maju Jaya"
    assert len(company["contacts"]) == 1
    assert company["contacts"][0]["is_primary"] is True
    assert company["contacts"][0]["name"] == "Budi"


def test_create_lead_with_existing_company_id(client):
    """Dua lead bisa menunjuk company yang sama (mis. dua kesempatan
    presales berbeda dari klien yang sama)."""
    headers = _auth_header(client)
    company = client.post(
        "/api/v1/companies", headers=headers, json={"name": "PT Sinergi", "industry": "jasa"}
    ).json()
    lead1 = client.post("/api/v1/leads", headers=headers, json={"company_id": company["id"]}).json()
    lead2 = client.post("/api/v1/leads", headers=headers, json={"company_id": company["id"]}).json()
    assert lead1["company_id"] == company["id"]
    assert lead2["company_id"] == company["id"]
    assert lead1["company_name"] == "PT Sinergi"


def test_create_lead_without_company_id_or_name_rejected(client):
    headers = _auth_header(client)
    resp = client.post("/api/v1/leads", headers=headers, json={})
    assert resp.status_code == 422


def test_lead_source_default_manual(client):
    """Fase 20 item 5 (revisi) -- `company_source` di `LeadOut` default
    "manual" untuk lead yang dibuat lewat form biasa (bukan impor CSV)."""
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Manual Saja")
    assert lead["company_source"] == "manual"


def test_leads_import_template_csv(client):
    headers = _auth_header(client)
    resp = client.get("/api/v1/companies/import/template", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "company_name" in resp.text
    assert "PT Contoh Sejahtera" in resp.text


def test_import_leads_csv_creates_companies_and_leads(client):
    """Alternatif aman dari scraping LinkedIn (PRD Fase 20 butir 5) -- impor
    CSV massal. Baris kedua sengaja pakai casing beda ("pt impor jaya" vs
    "PT Impor Jaya") untuk pastikan dedup company case-insensitive."""
    headers = _auth_header(client)
    csv_text = (
        "company_name;industry;size;contact_name;department;email;phone;"
        "estimated_headcount;estimated_value;notes\n"
        "PT Impor Jaya;Manufaktur;50-100;Sinta;HR;sinta@imporjaya.co.id;"
        "081200000001;60;100000000;Prospek pameran dagang\n"
        "pt impor jaya;Manufaktur;50-100;Dedi;Procurement;dedi@imporjaya.co.id;"
        "081200000002;;;Kontak kedua perusahaan yang sama\n"
    )
    resp = client.post(
        "/api/v1/companies/import",
        headers=headers,
        files={"file": ("leads.csv", csv_text.encode(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["companies_created"] == 1
    assert body["leads_created"] == 2
    assert body["failed"] == []

    leads = client.get("/api/v1/leads", headers=headers).json()
    imported = [lead for lead in leads if lead["company_name"].lower() == "pt impor jaya"]
    assert len(imported) == 2
    assert all(lead["company_source"] == "csv_import" for lead in imported)
    assert imported[0]["company_id"] == imported[1]["company_id"]

    company = client.get(f"/api/v1/companies/{imported[0]['company_id']}", headers=headers).json()
    assert company["source"] == "csv_import"
    assert len(company["contacts"]) == 2
    primary = [c for c in company["contacts"] if c["is_primary"]]
    assert len(primary) == 1
    assert primary[0]["name"] == "Sinta"


def test_import_leads_csv_reports_row_failures(client):
    headers = _auth_header(client)
    csv_text = "company_name;industry\n" "PT Baris Sukses;Jasa\n" ";Tanpa Nama Perusahaan\n"
    resp = client.post(
        "/api/v1/companies/import",
        headers=headers,
        files={"file": ("leads.csv", csv_text.encode(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["companies_created"] == 1
    assert body["leads_created"] == 1
    assert len(body["failed"]) == 1
    assert body["failed"][0]["row"] == 3
    assert "kosong" in body["failed"][0]["error"]


def test_contact_crud(client):
    headers = _auth_header(client)
    company = client.post("/api/v1/companies", headers=headers, json={"name": "PT Kontak"}).json()

    contact = client.post(
        f"/api/v1/companies/{company['id']}/contacts",
        headers=headers,
        json={"name": "Sari", "department": "procurement", "email": "sari@kontak.co.id"},
    ).json()
    assert contact["company_id"] == company["id"]

    listed = client.get(f"/api/v1/companies/{company['id']}/contacts", headers=headers).json()
    assert len(listed) == 1

    updated = client.patch(
        f"/api/v1/companies/contacts/{contact['id']}",
        headers=headers,
        json={"is_primary": True},
    )
    assert updated.status_code == 200
    assert updated.json()["is_primary"] is True

    deleted = client.delete(f"/api/v1/companies/contacts/{contact['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/companies/{company['id']}/contacts", headers=headers).json() == []


def test_lead_contact_add_list_update_remove(client):
    """Fase 40: satu lead bisa punya beberapa PIC dengan peran berbeda,
    dipilih dari daftar kontak company yang sama."""
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Multi Kontak")
    company_id = lead["company_id"]
    contact_a = client.post(
        f"/api/v1/companies/{company_id}/contacts", headers=headers, json={"name": "Ani"}
    ).json()
    contact_b = client.post(
        f"/api/v1/companies/{company_id}/contacts", headers=headers, json={"name": "Bram"}
    ).json()

    lc_a = client.post(
        f"/api/v1/leads/{lead['id']}/contacts",
        headers=headers,
        json={"contact_id": contact_a["id"], "role": "Decision Maker"},
    )
    assert lc_a.status_code == 201, lc_a.text
    lc_a_body = lc_a.json()
    assert lc_a_body["role"] == "Decision Maker"
    assert lc_a_body["contact"]["name"] == "Ani"

    lc_b = client.post(
        f"/api/v1/leads/{lead['id']}/contacts",
        headers=headers,
        json={"contact_id": contact_b["id"], "role": "Champion"},
    )
    assert lc_b.status_code == 201, lc_b.text

    listed = client.get(f"/api/v1/leads/{lead['id']}/contacts", headers=headers).json()
    assert len(listed) == 2
    assert {lc["role"] for lc in listed} == {"Decision Maker", "Champion"}

    updated = client.patch(
        f"/api/v1/leads/contacts/{lc_a_body['id']}", headers=headers, json={"role": "Champion Baru"}
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "Champion Baru"

    deleted = client.delete(f"/api/v1/leads/contacts/{lc_a_body['id']}", headers=headers)
    assert deleted.status_code == 204
    remaining = client.get(f"/api/v1/leads/{lead['id']}/contacts", headers=headers).json()
    assert len(remaining) == 1
    assert remaining[0]["contact"]["name"] == "Bram"


def test_lead_contact_rejects_contact_from_other_company(client):
    headers = _auth_header(client)
    lead1 = _create_lead(client, headers, "PT Satu")
    lead2 = _create_lead(client, headers, "PT Dua")
    contact_lead2 = client.get(
        f"/api/v1/companies/{lead2['company_id']}/contacts", headers=headers
    ).json()[0]

    resp = client.post(
        f"/api/v1/leads/{lead1['id']}/contacts",
        headers=headers,
        json={"contact_id": contact_lead2["id"], "role": "Champion"},
    )
    assert resp.status_code == 422


def test_lead_contact_duplicate_rejected(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Duplikat")
    contact = client.get(
        f"/api/v1/companies/{lead['company_id']}/contacts", headers=headers
    ).json()[0]

    first = client.post(
        f"/api/v1/leads/{lead['id']}/contacts",
        headers=headers,
        json={"contact_id": contact["id"], "role": "Champion"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/leads/{lead['id']}/contacts",
        headers=headers,
        json={"contact_id": contact["id"], "role": "Decision Maker"},
    )
    assert second.status_code == 409


def test_custom_field_text_definition_and_value_lifecycle(client):
    """Fase 41: field kustom teks -- definisi dibuat sekali, nilainya
    per-lead. Lead lain (belum punya value) tetap dapat field-nya dengan
    value=None supaya frontend bisa render form lengkap."""
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Field Kustom")

    fd = client.post(
        "/api/v1/custom-fields/definitions",
        headers=headers,
        json={
            "entity": "lead",
            "key": "sumber_referral",
            "label": "Sumber Referral",
            "field_type": "text",
        },
    )
    assert fd.status_code == 201, fd.text
    fd_body = fd.json()

    values = client.get(
        "/api/v1/custom-fields/values",
        headers=headers,
        params={"entity": "lead", "entity_id": lead["id"]},
    ).json()
    assert len(values) == 1
    assert values[0]["value"] is None
    assert values[0]["label"] == "Sumber Referral"

    set_resp = client.put(
        "/api/v1/custom-fields/values",
        headers=headers,
        json={
            "entity": "lead",
            "entity_id": lead["id"],
            "field_definition_id": fd_body["id"],
            "value": "Pameran Dagang",
        },
    )
    assert set_resp.status_code == 200, set_resp.text
    assert set_resp.json()["value"] == "Pameran Dagang"

    values2 = client.get(
        "/api/v1/custom-fields/values",
        headers=headers,
        params={"entity": "lead", "entity_id": lead["id"]},
    ).json()
    assert values2[0]["value"] == "Pameran Dagang"

    # Update ulang value yang sama (bukan bikin row baru)
    set_resp2 = client.put(
        "/api/v1/custom-fields/values",
        headers=headers,
        json={
            "entity": "lead",
            "entity_id": lead["id"],
            "field_definition_id": fd_body["id"],
            "value": "Referral Klien",
        },
    )
    assert set_resp2.status_code == 200
    values3 = client.get(
        "/api/v1/custom-fields/values",
        headers=headers,
        params={"entity": "lead", "entity_id": lead["id"]},
    ).json()
    assert len(values3) == 1
    assert values3[0]["value"] == "Referral Klien"


def test_custom_field_select_validates_option(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Field Select")
    fd = client.post(
        "/api/v1/custom-fields/definitions",
        headers=headers,
        json={
            "entity": "lead",
            "key": "tipe_layanan",
            "label": "Tipe Layanan",
            "field_type": "select",
            "options": [{"label": "Payroll Only"}, {"label": "Full Outsourcing"}],
        },
    ).json()
    option_id = fd["options"][0]["id"]

    invalid = client.put(
        "/api/v1/custom-fields/values",
        headers=headers,
        json={
            "entity": "lead",
            "entity_id": lead["id"],
            "field_definition_id": fd["id"],
            "value": "bukan-opsi",
        },
    )
    assert invalid.status_code == 422

    valid = client.put(
        "/api/v1/custom-fields/values",
        headers=headers,
        json={
            "entity": "lead",
            "entity_id": lead["id"],
            "field_definition_id": fd["id"],
            "value": option_id,
        },
    )
    assert valid.status_code == 200


def test_custom_field_select_requires_options(client):
    headers = _auth_header(client)
    resp = client.post(
        "/api/v1/custom-fields/definitions",
        headers=headers,
        json={"entity": "lead", "key": "tanpa_opsi", "label": "Tanpa Opsi", "field_type": "select"},
    )
    assert resp.status_code == 422


def test_custom_field_duplicate_key_per_entity_rejected(client):
    headers = _auth_header(client)
    client.post(
        "/api/v1/custom-fields/definitions",
        headers=headers,
        json={
            "entity": "lead",
            "key": "catatan_khusus",
            "label": "Catatan Khusus",
            "field_type": "text",
        },
    )
    dup = client.post(
        "/api/v1/custom-fields/definitions",
        headers=headers,
        json={
            "entity": "lead",
            "key": "catatan_khusus",
            "label": "Catatan Khusus Lain",
            "field_type": "text",
        },
    )
    assert dup.status_code == 409


def test_custom_field_required_rejects_empty_value(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Field Wajib")
    fd = client.post(
        "/api/v1/custom-fields/definitions",
        headers=headers,
        json={
            "entity": "lead",
            "key": "npwp",
            "label": "NPWP",
            "field_type": "text",
            "is_required": True,
        },
    ).json()

    resp = client.put(
        "/api/v1/custom-fields/values",
        headers=headers,
        json={
            "entity": "lead",
            "entity_id": lead["id"],
            "field_definition_id": fd["id"],
            "value": "",
        },
    )
    assert resp.status_code == 422


def test_custom_field_scoped_to_own_entity(client):
    """Field yang didefinisikan untuk entity=company tidak boleh dipasang
    nilai lewat entity=lead, walau entity_id kebetulan valid."""
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Field Scope")
    company_fd = client.post(
        "/api/v1/custom-fields/definitions",
        headers=headers,
        json={
            "entity": "company",
            "key": "npwp_company",
            "label": "NPWP Company",
            "field_type": "text",
        },
    ).json()

    resp = client.put(
        "/api/v1/custom-fields/values",
        headers=headers,
        json={
            "entity": "lead",
            "entity_id": lead["id"],
            "field_definition_id": company_fd["id"],
            "value": "123",
        },
    )
    assert resp.status_code == 422


def test_custom_field_definition_update_and_delete(client):
    headers = _auth_header(client)
    fd = client.post(
        "/api/v1/custom-fields/definitions",
        headers=headers,
        json={"entity": "lead", "key": "prioritas", "label": "Prioritas", "field_type": "text"},
    ).json()

    updated = client.patch(
        f"/api/v1/custom-fields/definitions/{fd['id']}",
        headers=headers,
        json={"label": "Prioritas Deal"},
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Prioritas Deal"

    listed = client.get(
        "/api/v1/custom-fields/definitions", headers=headers, params={"entity": "lead"}
    ).json()
    assert any(f["id"] == fd["id"] for f in listed)

    deleted = client.delete(f"/api/v1/custom-fields/definitions/{fd['id']}", headers=headers)
    assert deleted.status_code == 204
    listed2 = client.get(
        "/api/v1/custom-fields/definitions", headers=headers, params={"entity": "lead"}
    ).json()
    assert not any(f["id"] == fd["id"] for f in listed2)


def test_render_document_pdf_returns_valid_pdf_bytes():
    """Unit test infrastruktur rendering (Fase 20 item 2) -- tanpa DB,
    langsung panggil fungsinya. Dipakai ulang oleh Quotation/Agreement/
    dokumen JO lewat parameter, bukan tiap jenis dokumen renderer sendiri."""
    pdf_bytes = render_document_pdf(
        title="Penawaran Harga",
        subtitle="PT Maju Jaya",
        sections=[("Nilai Penawaran", "Rp 50.000.000"), ("Berlaku Hingga", "30 hari")],
        footer_text="Dokumen ini digenerate otomatis oleh AI Enterprise OS.",
        accent_color="#0f172a",
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def _quotation_template_payload(name="Template Standar"):
    return {
        "name": name,
        "field_schema": [
            {"key": "nilai", "label": "Nilai Penawaran", "type": "number"},
            {"key": "berlaku", "label": "Berlaku Hingga", "type": "text"},
        ],
        "footer_text": "Hormat kami,",
        "accent_color": "#0f172a",
    }


def test_quotation_template_crud(client):
    headers = _auth_header(client)
    created = client.post(
        "/api/v1/quotation-templates", headers=headers, json=_quotation_template_payload()
    )
    assert created.status_code == 201, created.text
    tmpl = created.json()
    assert tmpl["field_schema"][0]["key"] == "nilai"
    assert tmpl["is_active"] is True

    fetched = client.get(f"/api/v1/quotation-templates/{tmpl['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Template Standar"

    listed = client.get("/api/v1/quotation-templates", headers=headers).json()
    assert len(listed) == 1

    updated = client.patch(
        f"/api/v1/quotation-templates/{tmpl['id']}",
        headers=headers,
        json={"is_active": False, "name": "Template Lama"},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert updated.json()["name"] == "Template Lama"
    # field_schema tidak ikut disentuh oleh update parsial -- tetap 2 field.
    assert len(updated.json()["field_schema"]) == 2

    active_only = client.get(
        "/api/v1/quotation-templates", headers=headers, params={"active_only": True}
    ).json()
    assert active_only == []


def _create_quotation(client, headers, lead_id=None):
    if lead_id is None:
        lead_id = _create_lead(client, headers, "PT Quotation")["id"]
    tmpl = client.post(
        "/api/v1/quotation-templates", headers=headers, json=_quotation_template_payload()
    ).json()
    resp = client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "lead_id": lead_id,
            "template_id": tmpl["id"],
            "field_values": {"nilai": "Rp 50.000.000", "berlaku": "30 hari"},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_quotation_full_lifecycle_draft_to_sent(client):
    headers = _auth_header(client)
    lead_id = _create_lead(client, headers, "PT Lifecycle")["id"]
    quotation = _create_quotation(client, headers, lead_id)
    assert quotation["status"] == "draft"

    # Lead otomatis maju ke tahap "penawaran" begitu quotation dibuat.
    lead = client.get(f"/api/v1/leads/{lead_id}", headers=headers).json()
    assert lead["stage"] == "penawaran"

    submitted = client.post(
        f"/api/v1/quotations/{quotation['id']}/submit-approval", headers=headers
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_approval"

    approved = client.post(f"/api/v1/quotations/{quotation['id']}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_at"] is not None

    sent = client.post(f"/api/v1/quotations/{quotation['id']}/send", headers=headers)
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent.json()["sent_at"] is not None

    dl = client.get(f"/api/v1/quotations/{quotation['id']}/download-url", headers=headers)
    assert dl.status_code == 200
    assert dl.json()["url"]


def _drive_quotation_to_sent(client, headers, lead_id=None):
    quotation = _create_quotation(client, headers, lead_id)
    client.post(f"/api/v1/quotations/{quotation['id']}/submit-approval", headers=headers)
    client.post(f"/api/v1/quotations/{quotation['id']}/approve", headers=headers)
    sent = client.post(f"/api/v1/quotations/{quotation['id']}/send", headers=headers)
    assert sent.status_code == 200, sent.text
    return sent.json()


def test_quotation_send_email_gagal_tanpa_smtp(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Email", contact_email="pic@emailklien.co.id")
    quotation = _drive_quotation_to_sent(client, headers, lead["id"])

    resp = client.post(f"/api/v1/quotations/{quotation['id']}/send-email", headers=headers, json={})
    assert resp.status_code == 422
    assert "SMTP belum dikonfigurasi" in resp.json()["detail"]


def test_quotation_send_email_sukses_pakai_default_recipient(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Email Sukses", contact_email="pic@emailklien.co.id")
    quotation = _drive_quotation_to_sent(client, headers, lead["id"])

    calls = []

    def _fake_send(to, subject, body, **kwargs):
        calls.append({"to": to, "subject": subject, **kwargs})

    settings = get_settings()
    with patch.object(settings, "smtp_host", "smtp.test.local"):
        with patch(
            "app.modules.notifications.service.send_raw_email_with_attachment",
            side_effect=_fake_send,
        ):
            resp = client.post(
                f"/api/v1/quotations/{quotation['id']}/send-email", headers=headers, json={}
            )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sent_to"] == "pic@emailklien.co.id"
    assert len(calls) == 1
    assert calls[0]["to"] == "pic@emailklien.co.id"
    assert calls[0]["attachment_subtype"] == "pdf"


def test_quotation_send_email_override_recipient(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Email Override", contact_email="pic@emailklien.co.id")
    quotation = _drive_quotation_to_sent(client, headers, lead["id"])

    settings = get_settings()
    with patch.object(settings, "smtp_host", "smtp.test.local"):
        with patch("app.modules.notifications.service.send_raw_email_with_attachment") as mocked:
            resp = client.post(
                f"/api/v1/quotations/{quotation['id']}/send-email",
                headers=headers,
                json={"to_email": "lain@klien.co.id"},
            )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sent_to"] == "lain@klien.co.id"
    assert mocked.call_args[0][0] == "lain@klien.co.id"


def test_quotation_send_email_tanpa_recipient_manapun_ditolak(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Tanpa Email")
    quotation = _drive_quotation_to_sent(client, headers, lead["id"])

    settings = get_settings()
    with patch.object(settings, "smtp_host", "smtp.test.local"):
        resp = client.post(
            f"/api/v1/quotations/{quotation['id']}/send-email", headers=headers, json={}
        )
    assert resp.status_code == 422
    assert "Email penerima tidak diketahui" in resp.json()["detail"]


def test_quotation_send_email_sebelum_dikirim_ditolak(client):
    headers = _auth_header(client)
    quotation = _create_quotation(client, headers)
    resp = client.post(f"/api/v1/quotations/{quotation['id']}/send-email", headers=headers, json={})
    assert resp.status_code == 404


def test_quotation_reject_requires_note(client):
    headers = _auth_header(client)
    quotation = _create_quotation(client, headers)
    client.post(f"/api/v1/quotations/{quotation['id']}/submit-approval", headers=headers)

    no_note = client.post(f"/api/v1/quotations/{quotation['id']}/reject", headers=headers, json={})
    assert no_note.status_code == 422

    rejected = client.post(
        f"/api/v1/quotations/{quotation['id']}/reject",
        headers=headers,
        json={"note": "Harga belum sesuai budget klien"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_note"] == "Harga belum sesuai budget klien"


def test_quotation_cannot_send_before_approved(client):
    headers = _auth_header(client)
    quotation = _create_quotation(client, headers)
    resp = client.post(f"/api/v1/quotations/{quotation['id']}/send", headers=headers)
    assert resp.status_code == 409


def test_quotation_cannot_approve_before_submitted(client):
    headers = _auth_header(client)
    quotation = _create_quotation(client, headers)
    resp = client.post(f"/api/v1/quotations/{quotation['id']}/approve", headers=headers)
    assert resp.status_code == 409


def test_quotation_list_filter_by_lead_and_status(client):
    headers = _auth_header(client)
    lead_a = _create_lead(client, headers, "PT A")["id"]
    lead_b = _create_lead(client, headers, "PT B")["id"]
    _create_quotation(client, headers, lead_a)
    _create_quotation(client, headers, lead_b)

    by_lead = client.get("/api/v1/quotations", headers=headers, params={"lead_id": lead_a}).json()
    assert len(by_lead) == 1
    assert by_lead[0]["lead_id"] == lead_a

    by_status = client.get("/api/v1/quotations", headers=headers, params={"status": "draft"}).json()
    assert len(by_status) == 2


def test_render_document_docx_returns_valid_docx_bytes():
    """Unit test infrastruktur rendering .docx (Fase 20 item 3) -- docx
    valid ditandai signature ZIP (PK\\x03\\x04), python-docx menyimpan
    sebagai OOXML/ZIP container."""
    docx_bytes = render_document_docx(
        title="Perjanjian Kerja Sama",
        subtitle="PT Maju Jaya",
        sections=[("Ruang Lingkup", "Jasa outsourcing 50 TKI"), ("Durasi", "12 bulan")],
        footer_text="Disetujui bersama,",
    )
    assert docx_bytes.startswith(b"PK\x03\x04")
    assert len(docx_bytes) > 500


def _agreement_template_payload(name="Template Agreement Standar"):
    return {
        "name": name,
        "field_schema": [
            {"key": "ruang_lingkup", "label": "Ruang Lingkup", "type": "textarea"},
            {"key": "durasi", "label": "Durasi Kontrak", "type": "text"},
        ],
        "footer_text": "Disetujui bersama,",
    }


def test_agreement_template_crud(client):
    headers = _auth_header(client)
    created = client.post(
        "/api/v1/agreement-templates", headers=headers, json=_agreement_template_payload()
    )
    assert created.status_code == 201, created.text
    tmpl = created.json()
    assert tmpl["field_schema"][0]["key"] == "ruang_lingkup"
    assert tmpl["is_active"] is True

    listed = client.get("/api/v1/agreement-templates", headers=headers).json()
    assert len(listed) == 1

    updated = client.patch(
        f"/api/v1/agreement-templates/{tmpl['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False


def _create_agreement(client, headers, lead_id=None):
    if lead_id is None:
        lead_id = _create_lead(client, headers, "PT Agreement")["id"]
    tmpl = client.post(
        "/api/v1/agreement-templates", headers=headers, json=_agreement_template_payload()
    ).json()
    resp = client.post(
        "/api/v1/agreements",
        headers=headers,
        json={
            "lead_id": lead_id,
            "template_id": tmpl["id"],
            "field_values": {"ruang_lingkup": "Jasa outsourcing 50 TKI", "durasi": "12 bulan"},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_agreement_cannot_send_before_approved(client):
    headers = _auth_header(client)
    agreement = _create_agreement(client, headers)
    resp = client.post(
        f"/api/v1/agreements/{agreement['id']}/send-esign",
        headers=headers,
        json={"signer_name": "Budi", "signer_email": "budi@klien.co.id"},
    )
    assert resp.status_code == 409


def test_agreement_decline_requires_note(client):
    headers = _auth_header(client)
    agreement = _create_agreement(client, headers)
    client.post(f"/api/v1/agreements/{agreement['id']}/submit-review", headers=headers)

    no_note = client.post(f"/api/v1/agreements/{agreement['id']}/decline", headers=headers, json={})
    assert no_note.status_code == 422

    declined = client.post(
        f"/api/v1/agreements/{agreement['id']}/decline",
        headers=headers,
        json={"note": "Klausul pasal 4 perlu direvisi legal"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"
    assert declined.json()["review_note"] == "Klausul pasal 4 perlu direvisi legal"


def test_agreement_full_lifecycle_draft_to_signed_via_esign(client):
    """End-to-end: draft -> internal_review -> approved -> sent (esign
    dikirim, mode sandbox) -> signed (simulate-complete di modul esign
    memicu efek samping balik ke Agreement lewat `_apply_status`)."""
    headers = _auth_header(client)
    agreement = _create_agreement(client, headers)
    assert agreement["status"] == "draft"

    submitted = client.post(f"/api/v1/agreements/{agreement['id']}/submit-review", headers=headers)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "internal_review"

    approved = client.post(f"/api/v1/agreements/{agreement['id']}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    settings = get_settings()
    with patch.object(settings, "esign_provider", "sandbox"):
        sent = client.post(
            f"/api/v1/agreements/{agreement['id']}/send-esign",
            headers=headers,
            json={"signer_name": "Budi", "signer_email": "budi@klien.co.id"},
        )
        assert sent.status_code == 200, sent.text
        assert sent.json()["status"] == "sent"
        assert sent.json()["sent_at"] is not None

        dl = client.get(f"/api/v1/agreements/{agreement['id']}/download-url", headers=headers)
        assert dl.status_code == 200
        assert dl.json()["url"]

        esign_requests = client.get(
            "/api/v1/esign/requests",
            headers=headers,
            params={"agreement_id": agreement["id"]},
        ).json()
        assert len(esign_requests) == 1
        esign_id = esign_requests[0]["id"]
        assert esign_requests[0]["agreement_id"] == agreement["id"]

        completed = client.post(
            f"/api/v1/esign/requests/{esign_id}/simulate-complete", headers=headers
        )
        assert completed.status_code == 200, completed.text

    final = client.get(f"/api/v1/agreements/{agreement['id']}", headers=headers).json()
    assert final["status"] == "signed"
    assert final["signed_at"] is not None


def _drive_agreement_to_sent(client, headers, lead_id=None):
    agreement = _create_agreement(client, headers, lead_id)
    client.post(f"/api/v1/agreements/{agreement['id']}/submit-review", headers=headers)
    client.post(f"/api/v1/agreements/{agreement['id']}/approve", headers=headers)
    settings = get_settings()
    with patch.object(settings, "esign_provider", "sandbox"):
        sent = client.post(
            f"/api/v1/agreements/{agreement['id']}/send-esign",
            headers=headers,
            json={"signer_name": "Budi", "signer_email": "budi@klien.co.id"},
        )
    assert sent.status_code == 200, sent.text
    return sent.json()


def test_agreement_send_email_gagal_tanpa_smtp(client):
    headers = _auth_header(client)
    lead = _create_lead(client, headers, "PT Agreement Email", contact_email="pic@emailklien.co.id")
    agreement = _drive_agreement_to_sent(client, headers, lead["id"])

    resp = client.post(f"/api/v1/agreements/{agreement['id']}/send-email", headers=headers, json={})
    assert resp.status_code == 422
    assert "SMTP belum dikonfigurasi" in resp.json()["detail"]


def test_agreement_send_email_sukses(client):
    headers = _auth_header(client)
    lead = _create_lead(
        client, headers, "PT Agreement Email Sukses", contact_email="pic@emailklien.co.id"
    )
    agreement = _drive_agreement_to_sent(client, headers, lead["id"])

    calls = []

    def _fake_send(to, subject, body, **kwargs):
        calls.append({"to": to, "subject": subject, **kwargs})

    settings = get_settings()
    with patch.object(settings, "smtp_host", "smtp.test.local"):
        with patch(
            "app.modules.notifications.service.send_raw_email_with_attachment",
            side_effect=_fake_send,
        ):
            resp = client.post(
                f"/api/v1/agreements/{agreement['id']}/send-email", headers=headers, json={}
            )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sent_to"] == "pic@emailklien.co.id"
    assert len(calls) == 1
    assert calls[0]["attachment_subtype"] == (
        "vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_agreement_send_email_sebelum_dikirim_ditolak(client):
    headers = _auth_header(client)
    agreement = _create_agreement(client, headers)
    resp = client.post(f"/api/v1/agreements/{agreement['id']}/send-email", headers=headers, json={})
    assert resp.status_code == 404
