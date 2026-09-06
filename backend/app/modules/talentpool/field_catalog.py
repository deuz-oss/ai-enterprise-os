"""Katalog field Candidate yang bisa ditampilkan/disembunyikan admin di tabel Talent Pool.

`full_name` sengaja tidak masuk katalog -- selalu kolom pertama, bukan opsional.
"""

CANDIDATE_FIELD_CATALOG: list[dict[str, str]] = [
    {"key": "phone", "label": "Telepon", "group": "Kontak"},
    {"key": "email", "label": "Email", "group": "Kontak"},
    {"key": "city", "label": "Domisili", "group": "Kontak"},
    {"key": "address", "label": "Alamat", "group": "Kontak"},
    {"key": "gender", "label": "Jenis Kelamin", "group": "Identitas"},
    {"key": "birthdate", "label": "Tanggal Lahir", "group": "Identitas"},
    {"key": "birthplace", "label": "Tempat Lahir", "group": "Identitas"},
    {"key": "ktp_no", "label": "No. KTP", "group": "Identitas"},
    {"key": "marital_status", "label": "Status Pernikahan", "group": "Identitas"},
    {"key": "blood_type", "label": "Golongan Darah", "group": "Identitas"},
    {"key": "religion", "label": "Agama", "group": "Identitas"},
    {"key": "education", "label": "Pendidikan", "group": "Profesional"},
    {"key": "education_level", "label": "Jenjang Pendidikan", "group": "Profesional"},
    {"key": "school", "label": "Sekolah/Kampus", "group": "Profesional"},
    {"key": "experience_years", "label": "Lama Pengalaman (tahun)", "group": "Profesional"},
    {"key": "current_company", "label": "Perusahaan Saat Ini", "group": "Profesional"},
    {"key": "current_position", "label": "Posisi Saat Ini", "group": "Profesional"},
    {"key": "position_pool", "label": "Kategori Posisi", "group": "Profesional"},
    {"key": "job_level", "label": "Level Posisi", "group": "Profesional"},
    {"key": "skills", "label": "Skill", "group": "Profesional"},
    {"key": "languages", "label": "Bahasa", "group": "Profesional"},
    {"key": "reference", "label": "Kode Referensi", "group": "Lainnya"},
    {"key": "expected_salary", "label": "Ekspektasi Gaji", "group": "Lainnya"},
    {"key": "source", "label": "Sumber", "group": "Lainnya"},
    {"key": "description", "label": "Bio Singkat", "group": "Lainnya"},
]

CANDIDATE_FIELD_KEYS: frozenset[str] = frozenset(f["key"] for f in CANDIDATE_FIELD_CATALOG)

DEFAULT_VISIBLE_FIELDS: list[str] = ["city", "skills", "expected_salary"]
