"""Black Lists (riset arsitektur MyOHRIS) — request->approve gate untuk
menandai kandidat, tanpa role approver terpisah (siapa pun recruiter/
management boleh mengajukan ATAU review)."""

from tests.conftest import _auth_header


def _create_candidate(client, headers, name="Budi", email="budi@example.com") -> str:
    resp = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": name, "email": email, "city": "Jakarta"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_request_blacklist_creates_pending_entry(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)

    resp = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_id, "reason": "Tidak hadir onboarding 3x tanpa kabar"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "menunggu_review"
    assert body["candidate_id"] == cand_id
    assert body["candidate_name"] == "Budi"
    assert body["reviewed_by"] is None


def test_request_blacklist_unknown_candidate_404(client):
    headers = _auth_header(client)
    resp = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": "00000000-0000-0000-0000-000000000000", "reason": "x"},
    )
    assert resp.status_code == 404


def test_duplicate_active_request_conflicts(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)

    first = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_id, "reason": "Alasan pertama"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_id, "reason": "Alasan kedua"},
    )
    assert second.status_code == 409


def test_review_approve_updates_status_and_reviewer(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)
    entry = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_id, "reason": "Pemalsuan ijazah"},
    ).json()

    resp = client.post(
        f"/api/v1/blacklist/entries/{entry['id']}/review",
        headers=headers,
        json={"decision": "disetujui", "notes": "Sudah dikonfirmasi ke kampus"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "disetujui"
    assert body["reviewed_by"] is not None
    assert body["review_notes"] == "Sudah dikonfirmasi ke kampus"


def test_review_reject_then_allows_new_request(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)
    entry = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_id, "reason": "Laporan belum jelas"},
    ).json()

    rejected = client.post(
        f"/api/v1/blacklist/entries/{entry['id']}/review",
        headers=headers,
        json={"decision": "ditolak"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "ditolak"

    # Rejected bukan status aktif -- kandidat yang sama boleh diajukan ulang.
    again = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_id, "reason": "Laporan baru dengan bukti"},
    )
    assert again.status_code == 200


def test_review_twice_rejected_422(client):
    headers = _auth_header(client)
    cand_id = _create_candidate(client, headers)
    entry = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_id, "reason": "x"},
    ).json()

    client.post(
        f"/api/v1/blacklist/entries/{entry['id']}/review",
        headers=headers,
        json={"decision": "disetujui"},
    )
    second = client.post(
        f"/api/v1/blacklist/entries/{entry['id']}/review",
        headers=headers,
        json={"decision": "ditolak"},
    )
    assert second.status_code == 422


def test_list_entries_filters_by_status(client):
    headers = _auth_header(client)
    cand_a = _create_candidate(client, headers, name="Andi", email="andi@example.com")
    cand_b = _create_candidate(client, headers, name="Cici", email="cici@example.com")

    entry_a = client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_a, "reason": "x"},
    ).json()
    client.post(
        "/api/v1/blacklist/entries",
        headers=headers,
        json={"candidate_id": cand_b, "reason": "y"},
    )
    client.post(
        f"/api/v1/blacklist/entries/{entry_a['id']}/review",
        headers=headers,
        json={"decision": "disetujui"},
    )

    pending = client.get("/api/v1/blacklist/entries?status=menunggu_review", headers=headers)
    assert pending.status_code == 200
    assert len(pending.json()) == 1
    assert pending.json()[0]["candidate_id"] == cand_b

    approved = client.get("/api/v1/blacklist/entries?status=disetujui", headers=headers)
    assert len(approved.json()) == 1
    assert approved.json()[0]["candidate_id"] == cand_a

    all_entries = client.get("/api/v1/blacklist/entries", headers=headers)
    assert len(all_entries.json()) == 2
