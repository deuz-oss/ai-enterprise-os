"""Router AI Interview (PRD v3.1 Patch 4). Dua router terpisah:
`router` (staf, authenticated + RBAC, di-mount dengan guard lisensi
`recruitment` di `main.py`) dan `public_router` (kandidat via `invite_token`,
tanpa autentikasi sama sekali — mirror `payroll/router.py::public_router`)."""

from app.core.database import get_db
from app.core.permissions import AI_INTERVIEW_SETTINGS_ROLES, RECRUITMENT_ROLES
from app.core.ratelimit import get_limiter
from app.core.security import get_current_user, require_roles
from app.core.tenancy import get_request_meta
from app.modules.ai_interview import service
from app.modules.ai_interview.models import (
    AIInterviewResponseStatus,
    AIInterviewReviewStatus,
    AIInterviewTemplateStatus,
)
from app.modules.ai_interview.schemas import (
    AIInterviewInviteIn,
    AIInterviewInviteOut,
    AIInterviewResponseOut,
    AIInterviewReviewIn,
    AIInterviewSettingsOut,
    AIInterviewSettingsUpdate,
    AIInterviewTemplateCreate,
    AIInterviewTemplateOut,
    AIInterviewTemplateUpdate,
    AnswerIn,
    CalibrationOut,
    InterviewGuidelineOut,
    PublicInterviewSessionOut,
    RecordingUrlOut,
    RetentionRunOut,
    VoiceCompleteIn,
    VoiceContextOut,
    VoiceSessionOut,
)
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/ai-interview",
    tags=["ai-interview"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*RECRUITMENT_ROLES))],
)


@router.post(
    "/templates", response_model=AIInterviewTemplateOut, status_code=status.HTTP_201_CREATED
)
def create_template(
    payload: AIInterviewTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.create_template(db, payload, user)


@router.get("/templates", response_model=list[AIInterviewTemplateOut])
def list_templates(
    job_order_id: str | None = Query(None),
    status_filter: AIInterviewTemplateStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    return service.list_templates(db, job_order_id=job_order_id, status=status_filter)


@router.get("/guidelines/builtin", response_model=list[InterviewGuidelineOut])
def builtin_guidelines():
    """Aturan percakapan bawaan agen suara (Fase 4) -- ditampilkan di editor
    template supaya staf tahu apa yang sudah dijaga sistem."""
    return service.builtin_guidelines()


@router.get("/templates/{template_id}/calibration", response_model=CalibrationOut)
def template_calibration(template_id: str, db: Session = Depends(get_db)):
    """Fase 5: kesesuaian skor AI dengan keputusan reviewer per template."""
    return service.template_calibration(db, template_id)


@router.get("/templates/{template_id}", response_model=AIInterviewTemplateOut)
def get_template(template_id: str, db: Session = Depends(get_db)):
    return service.get_template(db, template_id)


@router.patch("/templates/{template_id}", response_model=AIInterviewTemplateOut)
def update_template(
    template_id: str, payload: AIInterviewTemplateUpdate, db: Session = Depends(get_db)
):
    return service.update_template(db, template_id, payload)


@router.post("/templates/{template_id}/invite", response_model=AIInterviewInviteOut)
def invite_candidates(
    template_id: str,
    payload: AIInterviewInviteIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.invite_candidates(db, template_id, payload, user)


@router.get("/responses", response_model=list[AIInterviewResponseOut])
def list_responses(
    template_id: str | None = Query(None),
    candidate_id: str | None = Query(None),
    job_order_id: str | None = Query(None),
    status_filter: AIInterviewResponseStatus | None = Query(None, alias="status"),
    review_status: AIInterviewReviewStatus | None = Query(None),
    db: Session = Depends(get_db),
):
    responses = service.list_responses(
        db,
        template_id=template_id,
        candidate_id=candidate_id,
        job_order_id=job_order_id,
        status=status_filter,
        review_status=review_status,
    )
    return service.responses_out(db, responses)


@router.get("/responses/{response_id}", response_model=AIInterviewResponseOut)
def get_response(response_id: str, db: Session = Depends(get_db)):
    return service.responses_out(db, [service.get_response(db, response_id)])[0]


@router.post("/responses/{response_id}/score", response_model=AIInterviewResponseOut)
def score_response(response_id: str, db: Session = Depends(get_db)):
    """Trigger ulang scoring manual (auto-scoring saat submit gagal, atau mau dinilai ulang)."""
    return service.score_response(db, response_id)


@router.post("/responses/{response_id}/review", response_model=AIInterviewResponseOut)
def review_response(
    response_id: str,
    payload: AIInterviewReviewIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Gate wajib — skor AI tidak dianggap final di UI manapun sebelum endpoint ini dipanggil.
    Fase 5: boleh sekaligus memindahkan kandidat di pipeline (`placement_status`)."""
    response = service.review_response(db, user, response_id, payload)
    return service.responses_out(db, [response])[0]


@router.get("/responses/{response_id}/recording-url", response_model=RecordingUrlOut)
def get_recording_url(
    response_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Link putar rekaman sesi suara (kedaluwarsa 15 menit, akses diaudit)."""
    return RecordingUrlOut(
        url=service.recording_url(db, user, response_id),
        expires_in_seconds=service.RECORDING_URL_TTL_SECONDS,
    )


@router.get(
    "/responses/{response_id}/answers/{question_id}/audio-url", response_model=RecordingUrlOut
)
def get_answer_audio_url(
    response_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Link putar rekaman satu jawaban (mode rekaman). Akses diaudit."""
    return RecordingUrlOut(
        url=service.answer_audio_url(db, user, response_id, question_id),
        expires_in_seconds=service.RECORDING_URL_TTL_SECONDS,
        channels=["Kandidat"],
    )


@router.post("/responses/{response_id}/resend-invite", response_model=AIInterviewResponseOut)
def resend_invite(response_id: str, db: Session = Depends(get_db)):
    return service.resend_invite(db, response_id)


# ---------- Fase 0: retensi data (UU PDP) ----------


@router.get("/settings", response_model=AIInterviewSettingsOut)
def get_settings_view(db: Session = Depends(get_db)):
    return service.get_interview_settings(db)


@router.put(
    "/settings",
    response_model=AIInterviewSettingsOut,
    dependencies=[Depends(require_roles(*AI_INTERVIEW_SETTINGS_ROLES))],
)
def update_settings(
    payload: AIInterviewSettingsUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Masa retensi = keputusan kepatuhan, bukan operasional rekrutmen harian."""
    return service.update_interview_settings(db, user, payload)


@router.post(
    "/retention/run",
    response_model=RetentionRunOut,
    dependencies=[Depends(require_roles(*AI_INTERVIEW_SETTINGS_ROLES))],
)
def run_retention(db: Session = Depends(get_db)):
    """Jalankan pembersihan retensi sekarang (juga otomatis tiap daftar respons dibuka)."""
    return RetentionRunOut(purged=service.purge_expired_responses(db))


# ---------- Sisi kandidat — publik, tanpa autentikasi ----------

public_router = APIRouter(prefix="/ai-interview/session", tags=["ai-interview-public"])

# Dua kelas batas (dulu satu bucket 30/jam per IP untuk semuanya):
# - "read" (GET sesi): halaman mode rekaman mem-polling status transkripsi
#   tiap ±2,5 dtk -> 30/jam habis dalam ~1 menit dan kandidat terkena 429
#   di tengah interview (ditemukan saat uji Fase 3 dgn faster-whisper asli).
# - "write" (persetujuan, unggah jawaban, mulai sesi suara): tetap ketat.
# Kunci = token + IP, bukan IP saja: beberapa kandidat dari satu jaringan
# kantor (IP publik sama) dulu saling menghabiskan jatah. Token 256-bit tidak
# bisa ditebak, jadi batas ini soal kewajaran beban, bukan anti-brute-force.
_RATE_LIMITS = {"read": 1200, "write": 60}
_SESSION_RATE_WINDOW_SEC = 3600


def _check_rate_limit(db: Session, token: str, kind: str = "write") -> None:
    ip, _ = get_request_meta()
    limiter = get_limiter(f"ai_interview_session_{kind}")
    key = f"{ip or 'unknown'}|{token[:16]}"
    allowed, retry_after = limiter.check(
        db, key, max_attempts=_RATE_LIMITS[kind], window_seconds=_SESSION_RATE_WINDOW_SEC
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan dari lokasi ini. Coba lagi nanti.",
            headers={"Retry-After": str(retry_after)},
        )
    limiter.hit(db, key, window_seconds=_SESSION_RATE_WINDOW_SEC)


@public_router.get("/{token}", response_model=PublicInterviewSessionOut)
def get_session(token: str, db: Session = Depends(get_db)):
    _check_rate_limit(db, token, "read")
    return service.get_session(db, token)


@public_router.post("/{token}/consent", status_code=status.HTTP_204_NO_CONTENT)
def give_consent(token: str, db: Session = Depends(get_db)):
    """Kandidat menyetujui ketentuan pemrosesan data (wajib sebelum mulai)."""
    _check_rate_limit(db, token)
    service.give_consent(db, token)


@public_router.post("/{token}/withdraw-consent", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_consent(token: str, db: Session = Depends(get_db)):
    """Kandidat menarik persetujuan -- jawaban, transkrip & hasil AI dihapus."""
    _check_rate_limit(db, token)
    service.withdraw_consent(db, token)


@public_router.post("/{token}/start", status_code=status.HTTP_204_NO_CONTENT)
def start_session(token: str, db: Session = Depends(get_db)):
    service.start_session(db, token)


@public_router.post("/{token}/answer", status_code=status.HTTP_204_NO_CONTENT)
def submit_answer(token: str, payload: AnswerIn, db: Session = Depends(get_db)):
    service.submit_answer(db, token, payload)


@public_router.post("/{token}/submit", response_model=PublicInterviewSessionOut)
def submit_session(token: str, db: Session = Depends(get_db)):
    service.submit_session(db, token)
    return service.get_session(db, token)


# ---------- AI Interview Fase 2: percakapan suara real-time ----------


@public_router.post("/{token}/voice/start", response_model=VoiceSessionOut)
async def start_voice_session(token: str, db: Session = Depends(get_db)):
    _check_rate_limit(db, token)
    return await service.start_voice_session(db, token)


@public_router.get("/{token}/voice/context", response_model=VoiceContextOut)
def get_voice_context(
    token: str,
    db: Session = Depends(get_db),
    x_agent_signature: str | None = Header(default=None),
):
    """Khusus agent worker (bukan browser kandidat): memuat kriteria &
    bobot penilaian, jadi wajib tanda tangan agent -- dulu cukup token
    yang juga dipegang kandidat."""
    service.verify_agent_signature(token, x_agent_signature)
    return service.get_voice_context(db, token)


@public_router.post("/{token}/voice/complete", response_model=PublicInterviewSessionOut)
def complete_voice_session(
    token: str,
    payload: VoiceCompleteIn,
    db: Session = Depends(get_db),
    x_agent_signature: str | None = Header(default=None),
):
    """Khusus agent: dulu kandidat bisa mengirim transkrip karangan sendiri
    lewat endpoint ini lalu dinilai."""
    service.verify_agent_signature(token, x_agent_signature)
    service.complete_voice_session(db, token, payload.transcript)
    return service.get_session(db, token)


@public_router.post("/{token}/voice/recording", status_code=status.HTTP_204_NO_CONTENT)
async def upload_voice_recording(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    x_agent_signature: str | None = Header(default=None),
):
    """Khusus agent: unggah rekaman sesi (body = bytes audio mentah)."""
    service.verify_agent_signature(token, x_agent_signature)
    data = await request.body()
    service.upload_voice_recording(
        db, token, data=data, content_type=request.headers.get("content-type", "")
    )


@public_router.post("/{token}/answers/{question_id}/audio", status_code=status.HTTP_202_ACCEPTED)
async def upload_answer_audio(
    token: str,
    question_id: str,
    request: Request,
    background: BackgroundTasks,
    duration_sec: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    """Mode rekaman: unggah jawaban suara satu pertanyaan (body = bytes
    audio). Transkripsi berjalan di latar belakang; kandidat memantau
    statusnya lewat GET sesi (`recorded_answers`)."""
    _check_rate_limit(db, token)
    data = await request.body()
    response, key = service.upload_answer_audio(
        db,
        token,
        question_id,
        data=data,
        content_type=request.headers.get("content-type", ""),
        duration_sec=duration_sec,
    )
    # Sesi DB task dibuat dari dependency get_db yang AKTIF (termasuk
    # override di test), bukan SessionLocal langsung -- sesi request sudah
    # ditutup saat background task berjalan.
    db_dep = request.app.dependency_overrides.get(get_db, get_db)
    background.add_task(_run_transcription, db_dep, str(response.id), question_id, key)
    return {"status": "processing"}


def _run_transcription(db_dep, response_id: str, question_id: str, key: str) -> None:
    gen = db_dep()
    db = next(gen)
    try:
        service.transcribe_answer_audio(db, response_id, question_id, key)
    finally:
        gen.close()
