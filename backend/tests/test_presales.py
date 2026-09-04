from unittest.mock import patch

from app.core.config import get_settings
from app.modules.presales.rendering import render_document_docx, render_document_pdf

from tests.conftest import _auth_header


def _create_lead(client, headers, name="PT Maju Jaya"):
    resp = client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "company_name": name,
            "industry": "manufaktur",
            "contact_name": "Budi",
            "estimated_headcount": 50,
            "estimated_value": 250_000_000,
        },
    )
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
