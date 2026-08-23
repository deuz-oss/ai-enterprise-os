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
