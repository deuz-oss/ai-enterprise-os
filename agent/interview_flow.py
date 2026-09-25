"""AI Interview Fase 4 roadmap — alur interview terstruktur + pedoman percakapan.

Modul murni (tanpa import LiveKit) supaya bisa dites tanpa infra suara.

Kenapa alur dijaga KODE, bukan cuma prompt: dulu agent diberi semua topik
sekaligus dan dibiarkan "ngobrol natural". Akibatnya LLM bebas melompati
pertanyaan, bertanya susulan tanpa batas, atau menutup interview sebelum
semua pertanyaan diajukan -- kandidat berbeda mendapat interview berbeda,
padahal penilaian yang adil butuh pertanyaan yang sama (structured interview).
Sekarang LLM hanya melihat SATU pertanyaan aktif, diberikan lewat tool
`next_question`, dan kuota pertanyaan susulan dihitung di sini.

Pedoman percakapan meniru pola Parlant (guideline = kondisi -> tindakan,
jawaban baku yang disetujui): aturan terkunci dari sistem, lalu pedoman
template, lalu jawaban baku default. Sumber teksnya backend
(`ai_interview/service.py::BUILTIN_GUIDELINES`), dikirim lewat voice/context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Penanda pertanyaan di transkrip. Backend mengabaikan baris ini saat
# mencari kutipan bukti (hanya baris "Kandidat:" yang dihitung) dan UI
# review menampilkannya sebagai judul bagian.
MARKER_PREFIX = "## "

# Penutup baku, diucapkan SETELAH tool end_interview (pola EndCallTool
# LiveKit: balasan tool diputar dulu, baru sesi dimatikan). Uji dengan model
# sungguhan (2026-09-25): kalau penutup diserahkan ke LLM sebelum tool, LLM
# kadang langsung memanggil end_interview tanpa pamit -- kandidat diputus diam.
CLOSING_LINE = (
    "Terima kasih atas waktu dan jawaban Anda. Interview sudah selesai. Hasilnya akan "
    "ditinjau oleh tim rekrutmen, dan Anda akan dihubungi untuk informasi tahap berikutnya."
)


@dataclass
class InterviewFlow:
    """State alur interview. `user_turns` = jumlah giliran bicara kandidat
    sejauh ini (dihitung pemanggil dari riwayat sesi). Dipakai untuk
    penjagaan "sudah dijawab": uji model sungguhan (2026-09-25) menunjukkan
    LLM bisa memanggil next_question beruntun lalu end_interview dalam SATU
    respons -- seluruh interview terlewati tanpa satu pun jawaban kandidat."""

    questions: list[dict]
    index: int = -1
    follow_ups_used: dict[str, int] = field(default_factory=dict)
    # posisi item riwayat percakapan -> teks penanda pertanyaan
    markers: dict[int, str] = field(default_factory=dict)
    # giliran kandidat saat pertanyaan/susulan terakhir diajukan
    _asked_at_turn: int = -1

    def __post_init__(self) -> None:
        self.questions = sorted(self.questions, key=lambda q: q.get("order", 1))

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def current(self) -> dict | None:
        if 0 <= self.index < self.total:
            return self.questions[self.index]
        return None

    @property
    def remaining(self) -> int:
        """Pertanyaan yang belum pernah diajukan."""
        return max(0, self.total - (self.index + 1))

    def _unanswered(self, user_turns: int) -> str | None:
        """Penolakan bila kandidat belum bicara sejak pertanyaan aktif diajukan."""
        q = self.current
        if q is None or user_turns > self._asked_at_turn:
            return None
        return (
            f"Kandidat belum menjawab pertanyaan {self.index + 1}. Ajukan pertanyaan itu "
            f'(kalau belum) lalu TUNGGU jawabannya: "{q.get("prompt", "")}"'
        )

    def next_question(self, history_len: int, user_turns: int) -> str:
        refusal = self._unanswered(user_turns)
        if refusal:
            return refusal
        if self.remaining <= 0:
            self.index = self.total  # tidak ada pertanyaan aktif lagi
            return (
                "Semua pertanyaan sudah diajukan. Langsung panggil end_interview -- JANGAN "
                "mengucapkan penutup sendiri, penutup diberikan oleh tool itu."
            )
        self.index += 1
        self._asked_at_turn = user_turns
        q = self.questions[self.index]
        number = self.index + 1
        self.markers[history_len] = f"{MARKER_PREFIX}Pertanyaan {number}: {q.get('prompt', '')}"
        return (
            f"Ajukan pertanyaan {number} dari {self.total}. Boleh dengan transisi singkat, "
            f'tapi jangan ubah maksudnya dan jangan beri petunjuk jawaban: "{q.get("prompt", "")}"'
        )

    def opening_instruction(self, history_len: int) -> str:
        """Instruksi pembuka dengan pertanyaan pertama SUDAH disisipkan kode.
        Uji model sungguhan (2026-09-25): bila pembukaan diserahkan ke LLM
        ("sapa, lalu panggil next_question"), LLM sering langsung mengarang
        pertanyaan sendiri dan tidak pernah memanggil tool."""
        greeting = (
            "Sapa kandidat dan perkenalkan diri singkat sebagai pewawancara AI, "
            f"sampaikan bahwa ada {self.total} pertanyaan"
        )
        if self.total == 0:
            return f"{greeting}, lalu panggil end_interview."
        step = self.next_question(history_len, user_turns=0)
        return (
            f"{greeting}. Lalu: {step} JANGAN memanggil tool apa pun sekarang; tunggu "
            "jawaban kandidat."
        )

    def request_follow_up(self, user_turns: int) -> str:
        q = self.current
        if q is None:
            return "Tidak ada pertanyaan aktif. Panggil next_question."
        refusal = self._unanswered(user_turns)
        if refusal:
            return refusal
        qid = q.get("id", str(self.index))
        used = self.follow_ups_used.get(qid, 0)
        limit = int(q.get("follow_up_max", 1) or 0)
        if used >= limit:
            return (
                "Batas pertanyaan susulan untuk pertanyaan ini sudah habis. Jangan bertanya "
                "susulan lagi; panggil next_question."
            )
        self.follow_ups_used[qid] = used + 1
        self._asked_at_turn = user_turns  # susulan juga harus dijawab dulu
        focus = (q.get("follow_up_focus") or "").strip()
        target = f" yang menggali: {focus}" if focus else " untuk meminta contoh konkret"
        return (
            f"Boleh. Ajukan SATU pertanyaan susulan singkat{target}. Jangan menggiring "
            "jawaban. Setelah kandidat menjawab, lanjut dengan next_question."
        )

    def closing_instruction(self, candidate_requested_stop: bool) -> str:
        """Balasan tool end_interview: yang harus diucapkan sebelum sesi mati."""
        if candidate_requested_stop:
            return (
                "Ucapkan jawaban baku pedoman untuk kandidat yang ingin berhenti, dalam satu "
                "atau dua kalimat, lalu jangan bicara lagi."
            )
        return f'Ucapkan kalimat penutup ini persis, tanpa tambahan apa pun: "{CLOSING_LINE}"'

    def end_refusal(self, candidate_requested_stop: bool, user_turns: int) -> str | None:
        """Alasan menolak end_interview, atau None bila boleh ditutup."""
        if candidate_requested_stop:
            return None
        refusal = self._unanswered(user_turns)
        if refusal:
            return refusal
        if self.remaining <= 0:
            return None
        return (
            f"Belum bisa ditutup: masih ada {self.remaining} pertanyaan yang belum diajukan. "
            "Panggil next_question. (Hanya bila kandidat sendiri minta berhenti, panggil "
            "end_interview dengan candidate_requested_stop=true.)"
        )


def _guideline_lines(items: list[dict]) -> str:
    return "\n".join(f"- JIKA {g['condition']}: {g['response']}" for g in items)


def build_instructions(context: dict) -> str:
    title = context.get("title", "")
    objective = context.get("objective") or ""
    total = len(context.get("questions") or [])
    guidelines = context.get("guidelines") or []
    locked = [g for g in guidelines if g.get("locked")]
    custom = [g for g in guidelines if g.get("source") == "template"]
    defaults = [g for g in guidelines if not g.get("locked") and g.get("source") != "template"]

    parts = [
        f'Anda pewawancara AI untuk posisi terkait "{title}". {objective}'.strip(),
        "",
        f"Interview ini TERSTRUKTUR: ada {total} pertanyaan wajib yang sama untuk semua "
        "kandidat. Bahasa Indonesia, nada profesional tapi hangat. ALUR:",
        "1. Pertanyaan pertama diberikan saat pembukaan. Anda TIDAK tahu pertanyaan "
        "berikutnya: SATU-SATUNYA cara mendapatkannya adalah memanggil tool "
        "`next_question`. DILARANG mengarang pertanyaan sendiri. Satu pertanyaan per "
        "giliran bicara.",
        "2. Setelah kandidat menjawab: kalau jawabannya kabur atau kurang contoh konkret, "
        "panggil `request_follow_up` dan ikuti balasannya. Kalau sudah cukup, panggil "
        "`next_question`.",
        "3. Pertanyaan susulan HANYA boleh setelah `request_follow_up` mengizinkan.",
        "4. Kalau `next_question` menyatakan semua pertanyaan selesai, langsung panggil "
        "`end_interview` lalu ucapkan penutup yang diberikan tool itu.",
        "Jangan menilai jawaban secara lisan (jangan memuji berlebihan, jangan memberi "
        "skor); tanggapan netral singkat seperti 'baik, terima kasih' boleh. Jangan "
        "mengarang informasi tentang posisi/perusahaan di luar yang diberikan.",
        "",
        "PEDOMAN PERCAKAPAN. Kalimat jawaban di pedoman diucapkan hampir persis -- jangan "
        "menambah janji atau informasi lain -- lalu kembali ke interview.",
    ]
    if locked:
        parts += [
            "ATURAN TERKUNCI (wajib, mengalahkan semua pedoman lain):",
            _guideline_lines(locked),
        ]
    if custom:
        parts += [
            "PEDOMAN DARI TIM REKRUTMEN (diutamakan atas jawaban baku default untuk topik "
            "yang sama, tapi TIDAK boleh melanggar aturan terkunci):",
            _guideline_lines(custom),
        ]
    if defaults:
        parts += ["JAWABAN BAKU DEFAULT:", _guideline_lines(defaults)]
    parts += [
        "Kalau kandidat ingin berhenti: panggil `end_interview` dengan "
        "candidate_requested_stop=true, lalu ikuti balasan tool itu.",
    ]
    return "\n".join(parts)


def format_transcript(items: list[tuple[str, str]], markers: dict[int, str]) -> str:
    """`items` = (role, text) per item riwayat, SEJAJAR indeksnya dengan
    riwayat sesi (item tanpa teks, mis. pemanggilan tool, tetap dihitung
    sebagai posisi supaya penanda jatuh di tempat yang benar)."""
    lines: list[str] = []
    for i, (role, text) in enumerate(items):
        if i in markers:
            lines.append(markers[i])
        if role and text:
            speaker = "Kandidat" if role == "user" else "Pewawancara AI"
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)
