"""Tes alur interview terstruktur (Fase 4 roadmap). Modul murni -- jalan
tanpa LiveKit: `python -m pytest agent/tests`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from interview_flow import (  # noqa: E402
    CLOSING_LINE,
    MARKER_PREFIX,
    InterviewFlow,
    TurnClock,
    build_instructions,
    format_transcript,
)

QUESTIONS = [
    {"id": "q2", "order": 2, "prompt": "Bagaimana Anda mengatur prioritas?", "follow_up_max": 0},
    {
        "id": "q1",
        "order": 1,
        "prompt": "Ceritakan pengalaman menangani komplain.",
        "follow_up_max": 2,
        "follow_up_focus": "hasil yang terukur",
    },
]


def test_questions_asked_in_order_one_at_a_time():
    flow = InterviewFlow(questions=list(QUESTIONS))
    first = flow.next_question(history_len=1, user_turns=0)
    assert "pertanyaan 1 dari 2" in first and "komplain" in first
    assert flow.remaining == 1
    second = flow.next_question(history_len=5, user_turns=1)
    assert "pertanyaan 2 dari 2" in second and "prioritas" in second
    done = flow.next_question(history_len=9, user_turns=2)
    assert "Semua pertanyaan sudah diajukan" in done
    assert flow.current is None and flow.remaining == 0
    # Penanda dicatat di posisi riwayat saat pertanyaan diambil.
    assert flow.markers == {
        1: f"{MARKER_PREFIX}Pertanyaan 1: Ceritakan pengalaman menangani komplain.",
        5: f"{MARKER_PREFIX}Pertanyaan 2: Bagaimana Anda mengatur prioritas?",
    }


def test_cannot_skip_ahead_without_candidate_answer():
    """Regresi uji model sungguhan: LLM memanggil next_question beruntun lalu
    end_interview dalam satu respons -- interview terlewati tanpa jawaban."""
    flow = InterviewFlow(questions=list(QUESTIONS))
    flow.opening_instruction(history_len=0)  # pertanyaan 1 diajukan
    skipped = flow.next_question(history_len=2, user_turns=0)
    assert "belum menjawab pertanyaan 1" in skipped and flow.index == 0
    assert "belum menjawab" in flow.end_refusal(False, user_turns=0)
    assert "belum menjawab" in flow.request_follow_up(user_turns=0)
    # Kandidat minta berhenti tetap selalu boleh.
    assert flow.end_refusal(True, user_turns=0) is None


def test_last_question_must_be_answered_before_end():
    flow = InterviewFlow(questions=list(QUESTIONS))
    flow.next_question(0, user_turns=0)
    flow.next_question(3, user_turns=1)  # pertanyaan 2 diajukan, remaining 0
    assert "belum menjawab pertanyaan 2" in flow.end_refusal(False, user_turns=1)
    assert flow.end_refusal(False, user_turns=2) is None


def test_opening_embeds_first_question():
    flow = InterviewFlow(questions=list(QUESTIONS))
    text = flow.opening_instruction(history_len=0)
    assert "ada 2 pertanyaan" in text and "Ceritakan pengalaman menangani komplain." in text
    assert "JANGAN memanggil tool" in text
    assert flow.index == 0 and 0 in flow.markers
    empty = InterviewFlow(questions=[])
    assert "end_interview" in empty.opening_instruction(0)


def test_follow_up_quota_enforced_per_question():
    flow = InterviewFlow(questions=list(QUESTIONS))
    assert "Tidak ada pertanyaan aktif" in flow.request_follow_up(user_turns=0)
    flow.next_question(0, user_turns=0)
    first = flow.request_follow_up(user_turns=1)
    assert first.startswith("Boleh") and "hasil yang terukur" in first
    # Susulan juga harus dijawab dulu sebelum susulan berikutnya.
    assert "belum menjawab" in flow.request_follow_up(user_turns=1)
    assert flow.request_follow_up(user_turns=2).startswith("Boleh")
    assert "sudah habis" in flow.request_follow_up(user_turns=3)
    flow.next_question(4, user_turns=3)
    # q2: follow_up_max 0 -> langsung ditolak.
    assert "sudah habis" in flow.request_follow_up(user_turns=4)


def test_follow_up_default_focus_asks_for_concrete_example():
    flow = InterviewFlow(questions=[{"id": "a", "prompt": "Ceritakan diri Anda."}])
    flow.next_question(0, user_turns=0)
    assert "contoh konkret" in flow.request_follow_up(user_turns=1)


def test_end_refused_until_all_questions_asked_unless_candidate_stops():
    flow = InterviewFlow(questions=list(QUESTIONS))
    flow.next_question(0, user_turns=0)
    refusal = flow.end_refusal(False, user_turns=1)
    assert refusal and "masih ada 1 pertanyaan" in refusal
    assert flow.end_refusal(True, user_turns=1) is None
    flow.next_question(3, user_turns=1)
    assert flow.end_refusal(False, user_turns=2) is None


def test_closing_is_canned_unless_candidate_stopped():
    flow = InterviewFlow(questions=[])
    assert CLOSING_LINE in flow.closing_instruction(False)
    assert CLOSING_LINE not in flow.closing_instruction(True)


def test_no_questions_can_end_immediately():
    flow = InterviewFlow(questions=[])
    assert flow.end_refusal(False, user_turns=0) is None
    assert "Semua pertanyaan" in flow.next_question(0, user_turns=0)


def test_transcript_includes_markers_and_skips_tool_items():
    items = [
        ("assistant", "Halo, saya pewawancara AI."),
        ("", ""),  # pemanggilan tool next_question: tanpa teks
        ("assistant", "Ceritakan pengalaman menangani komplain."),
        ("user", "Saya dengarkan pelanggan dulu."),
    ]
    text, offsets = format_transcript(items, {1: "## Pertanyaan 1: Komplain"})
    assert text.splitlines() == [
        "Pewawancara AI: Halo, saya pewawancara AI.",
        "## Pertanyaan 1: Komplain",
        "Pewawancara AI: Ceritakan pengalaman menangani komplain.",
        "Kandidat: Saya dengarkan pelanggan dulu.",
    ]
    assert offsets == [None, None, None, None]  # tanpa waktu -> tidak ada offset


def test_transcript_offsets_relative_to_recording_start():
    items = [
        ("assistant", "Halo.", 1000.5),
        ("", "", None),
        ("user", "Saya dengarkan pelanggan dulu.", 1012.25),
        ("user", "Tanpa waktu.", None),
    ]
    text, offsets = format_transcript(items, {1: "## Pertanyaan 1: Komplain"}, t0=1000.0)
    assert len(offsets) == len(text.splitlines())
    assert offsets == [0.5, None, 12.25, None]


def test_multiline_message_stays_one_line_so_offsets_align():
    """Regresi uji E2E: ucapan LLM berisi baris baru -> offset tidak sejajar."""
    items = [("assistant", "Selamat datang.\n\nCeritakan pengalaman Anda.", 1001.0)]
    text, offsets = format_transcript(items, {}, t0=1000.0)
    assert text == "Pewawancara AI: Selamat datang. Ceritakan pengalaman Anda."
    assert offsets == [1.0]


def test_turn_clock_uses_first_speaking_start_of_each_turn():
    """Satu giliran kandidat bisa berisi beberapa potongan bicara (jeda
    berpikir); waktu mulai = potongan PERTAMA sejak item sebelumnya."""
    clock = TurnClock()
    clock.speaking("assistant", 5.0)
    clock.item_added("a1", "assistant")
    clock.speaking("user", 10.0)
    clock.speaking("user", 14.0)  # lanjut bicara setelah jeda
    clock.item_added("u1", "user")
    clock.item_added("u2", "user")  # item tanpa event bicara -> tidak ada waktu
    clock.speaking("user", 30.0)
    clock.item_added("u3", "user")
    assert clock.starts == {"a1": 5.0, "u1": 10.0, "u3": 30.0}


def _g(condition: str, response: str, *, locked: bool, source: str) -> dict:
    return {"condition": condition, "response": response, "locked": locked, "source": source}


def test_instructions_order_locked_then_template_then_defaults():
    context = {
        "title": "Customer Service",
        "objective": "Menilai komunikasi.",
        "questions": QUESTIONS,
        "guidelines": [
            _g("Topik agama", "Jangan tanya.", locked=True, source="sistem"),
            _g("Tanya gaji", "Dijelaskan tim.", locked=False, source="sistem"),
            _g("Tanya shift", "Shift 3x8 jam.", locked=False, source="template"),
        ],
    }
    text = build_instructions(context)
    assert "2 pertanyaan wajib" in text
    locked = text.index("ATURAN TERKUNCI")
    custom = text.index("PEDOMAN DARI TIM REKRUTMEN")
    defaults = text.index("JAWABAN BAKU DEFAULT")
    assert locked < custom < defaults
    assert "- JIKA Tanya shift: Shift 3x8 jam." in text
    # Daftar pertanyaan TIDAK dibocorkan ke prompt -- hanya lewat tool.
    assert "prioritas" not in text
