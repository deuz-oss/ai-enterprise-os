"""Polish Fase 7 — Halaman workspace (page tree ala Notion)."""

from tests.conftest import _auth_header


def _create_karyawan(client):
    from app.core.bootstrap import ensure_default_tenant
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user

    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        try:
            create_user(
                db,
                UserCreate(
                    email="worker-pages@t.co",
                    full_name="Worker Pages",
                    password="rahasia-123",
                    role="karyawan",
                ),
                tenant_id=tenant.id,
            )
        except Exception:
            pass
    finally:
        db.close()
    resp = client.post(
        "/api/v1/auth/login", json={"email": "worker-pages@t.co", "password": "rahasia-123"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_page_crud_dan_tree(client):
    admin = _auth_header(client)

    root = client.post(
        "/api/v1/pages",
        headers=admin,
        json={"title": "SOP Onboarding", "icon": "📘", "content": "Langkah onboarding..."},
    )
    assert root.status_code == 201, root.text
    root_id = root.json()["id"]

    child = client.post(
        "/api/v1/pages",
        headers=admin,
        json={"title": "Checklist Hari 1", "parent_id": root_id, "content": "1. Akun email"},
    )
    assert child.status_code == 201
    assert child.json()["parent_id"] == root_id

    listed = client.get("/api/v1/pages", headers=admin).json()
    titles = {p["title"] for p in listed}
    assert {"SOP Onboarding", "Checklist Hari 1"} <= titles

    got = client.get(f"/api/v1/pages/{child.json()['id']}", headers=admin).json()
    assert got["content"].startswith("1.")

    upd = client.patch(
        f"/api/v1/pages/{root_id}", headers=admin, json={"content": "Revisi langkah"}
    )
    assert upd.status_code == 200
    assert upd.json()["content"] == "Revisi langkah"

    # Hapus induk → sub-halaman ikut terhapus
    deleted = client.delete(f"/api/v1/pages/{root_id}", headers=admin)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 2
    gone = client.get(f"/api/v1/pages/{child.json()['id']}", headers=admin)
    assert gone.status_code == 404


def test_page_cyle_ditolak_dan_karyawan_dilarang(client):
    admin = _auth_header(client)
    a = client.post("/api/v1/pages", headers=admin, json={"title": "A"}).json()
    b = client.post(
        "/api/v1/pages", headers=admin, json={"title": "B", "parent_id": a["id"]}
    ).json()

    # Jadikan A anak dari B-nya sendiri → siklus ditolak
    cycle = client.patch(f"/api/v1/pages/{a['id']}", headers=admin, json={"parent_id": b["id"]})
    assert cycle.status_code == 422

    self_parent = client.patch(
        f"/api/v1/pages/{a['id']}", headers=admin, json={"parent_id": a["id"]}
    )
    assert self_parent.status_code == 422

    worker = _create_karyawan(client)
    forbidden_create = client.post("/api/v1/pages", headers=worker, json={"title": "X"})
    assert forbidden_create.status_code == 403
    forbidden_delete = client.delete(f"/api/v1/pages/{a['id']}", headers=worker)
    assert forbidden_delete.status_code == 403
