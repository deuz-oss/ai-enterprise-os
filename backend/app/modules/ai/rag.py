"""RAG Q&A atas dokumen kontrak kerja karyawan.

Alur: teks kontrak diekstrak, dipecah jadi chunk, di-embed lalu disimpan
di tabel ai_document_chunks. Pertanyaan di-embed, dicari top-k chunk
terdekat (cosine similarity, dihitung di Python), lalu LLM menjawab
hanya berdasarkan konteks yang ditemukan.
"""

from __future__ import annotations

import json
import math
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.llm import chat_completion, embed_texts
from app.core.storage import get_object
from app.modules.ai.models import AIDocumentChunk
from app.modules.ai.schemas import (
    AskResultOut,
    AskSourceOut,
    ContractIndexOut,
    IndexedContractOut,
)
from app.modules.ai.textutils import extract_document_text
from app.modules.hrd.models import Employee, EmploymentContract

_CHUNK_SIZE = 1_200
_CHUNK_OVERLAP = 200
_TOP_K = 5

_SYSTEM_PROMPT = (
    "Anda asisten HR yang menjawab pertanyaan berdasarkan potongan dokumen "
    "kontrak kerja yang diberikan. Jawab dalam bahasa Indonesia yang ringkas. "
    "Jika jawaban tidak terdapat pada konteks, katakan dengan jujur bahwa "
    "informasinya tidak ditemukan dalam dokumen — jangan mengarang. "
    'Balas HANYA JSON valid: {"answer": "<jawaban>"}'
)


def _get_contract(db: Session, contract_id: UUID) -> EmploymentContract:
    contract = db.get(EmploymentContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Kontrak tidak ditemukan")
    return contract


def _chunk_text(text: str) -> list[str]:
    """Potong teks menjadi chunk dengan tumpang tindih agar konteks tak terputus."""
    step = _CHUNK_SIZE - _CHUNK_OVERLAP
    chunks = []
    for start in range(0, len(text), step):
        piece = text[start : start + _CHUNK_SIZE].strip()
        if piece:
            chunks.append(piece)
        if start + _CHUNK_SIZE >= len(text):
            break
    return chunks or ([text.strip()] if text.strip() else [])


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def index_contract(db: Session, contract_id: UUID) -> ContractIndexOut:
    """Ekstrak, pecah, embed, dan simpan isi satu kontrak kerja."""
    contract = _get_contract(db, contract_id)
    if not contract.object_key:
        raise HTTPException(
            status_code=422, detail="Kontrak belum memiliki file. Unggah file kontrak dahulu."
        )
    text = extract_document_text(get_object(contract.object_key), contract.file_name or "")
    chunks = _chunk_text(text)
    vectors = embed_texts(chunks)

    db.execute(delete(AIDocumentChunk).where(AIDocumentChunk.source_id == contract.id))
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        db.add(
            AIDocumentChunk(
                source_type="employment_contract",
                source_id=contract.id,
                employee_id=contract.employee_id,
                chunk_index=idx,
                content=chunk,
                embedding_json=json.dumps(vector),
                model=get_settings().ai_embedding_model,
            )
        )
    db.commit()
    return ContractIndexOut(contract_id=contract.id, chunks=len(chunks))


def list_indexed(db: Session) -> list[IndexedContractOut]:
    """Daftar kontrak yang punya indeks RAG beserta jumlah chunk."""
    rows = db.execute(
        select(
            EmploymentContract.id,
            EmploymentContract.file_name,
            Employee.full_name,
            func.count(AIDocumentChunk.id),
        )
        .join(Employee, Employee.id == EmploymentContract.employee_id)
        .join(AIDocumentChunk, AIDocumentChunk.source_id == EmploymentContract.id)
        .group_by(
            EmploymentContract.id, EmploymentContract.file_name, Employee.full_name
        )
        .order_by(Employee.full_name)
    ).all()
    return [
        IndexedContractOut(
            contract_id=row[0], file_name=row[1], employee_name=row[2], chunks=row[3]
        )
        for row in rows
    ]


def ask(db: Session, question: str, employee_id: UUID | None = None) -> AskResultOut:
    """Jawab pertanyaan dari potongan kontrak paling relevan."""
    question = question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Pertanyaan tidak boleh kosong")

    stmt = select(AIDocumentChunk)
    if employee_id:
        stmt = stmt.where(AIDocumentChunk.employee_id == employee_id)
    all_chunks = list(db.scalars(stmt).all())
    if not all_chunks:
        raise HTTPException(
            status_code=422,
            detail="Belum ada kontrak ter-indeks. Indekskan kontrak terlebih dahulu.",
        )

    query_vector = embed_texts([question])[0]
    scored = sorted(
        ((_cosine(query_vector, json.loads(c.embedding_json)), c) for c in all_chunks),
        key=lambda pair: pair[0],
        reverse=True,
    )[:_TOP_K]

    employee_ids = {c.employee_id for _, c in scored if c.employee_id}
    contract_ids = {c.source_id for _, c in scored}
    employees: dict[UUID, Employee] = (
        {
            e.id: e
            for e in db.scalars(select(Employee).where(Employee.id.in_(employee_ids))).all()
        }
        if employee_ids
        else {}
    )
    contracts: dict[UUID, EmploymentContract] = {
        k.id: k
        for k in db.scalars(
            select(EmploymentContract).where(EmploymentContract.id.in_(contract_ids))
        ).all()
    }

    context_parts: list[str] = []
    sources: list[AskSourceOut] = []
    for rank, (score, chunk) in enumerate(scored, start=1):
        emp = employees.get(chunk.employee_id) if chunk.employee_id else None
        contract = contracts.get(chunk.source_id)
        emp_label = emp.full_name if emp else "Karyawan"
        no_label = contract.contract_no if contract else ""
        label = f"[{rank}] {emp_label} — kontrak {no_label}"
        context_parts.append(f"{label}\n{chunk.content}")
        sources.append(
            AskSourceOut(
                contract_id=chunk.source_id,
                employee_name=emp.full_name if emp else None,
                contract_no=contract.contract_no if contract else None,
                score=round(score, 4),
                snippet=chunk.content[:200],
            )
        )

    user_prompt = (
        "KONTEKS DOKUMEN KONTRAK:\n\n" + "\n\n".join(context_parts) +
        f"\n\nPERTANYAAN: {question}"
    )
    result = chat_completion(_SYSTEM_PROMPT, user_prompt, json_mode=True)
    answer = str(result.get("answer") or "").strip() if isinstance(result, dict) else ""
    if not answer:
        answer = "Tidak ada jawaban yang dapat dibuat dari dokumen."

    return AskResultOut(answer=answer, sources=sources)
