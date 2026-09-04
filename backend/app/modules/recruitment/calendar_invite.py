"""Invite kalender `.ics` untuk interview (PRD Fase 21 item 5).

Keputusan eksplisit (lihat PRD §Fase 21): invite `.ics` lampiran email,
BUKAN OAuth Google Calendar — kandidat/interviewer tambahkan sendiri ke
kalender apa pun (Google/Outlook/dll) tanpa perlu connect/login akun
Google, dan tanpa infrastruktur OAuth client baru di backend.
"""

from datetime import UTC, datetime, timedelta

from icalendar import Calendar, Event

from app.modules.recruitment.models import InterviewSchedule


def build_interview_ics(
    interview: InterviewSchedule,
    *,
    candidate_name: str,
    job_order_title: str,
    organizer_email: str | None = None,
    attendee_emails: list[str] | None = None,
    duration_minutes: int = 60,
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//AI Enterprise OS//Interview Invite//ID")
    cal.add("version", "2.0")
    cal.add("method", "REQUEST")

    event = Event()
    event.add("uid", f"interview-{interview.id}@aeos")
    event.add("summary", f"Interview {candidate_name} — {job_order_title}")
    description = f"Interview kandidat {candidate_name} untuk posisi {job_order_title}."
    if interview.meeting_url:
        description += f"\nLink meeting: {interview.meeting_url}"
    event.add("description", description)
    event.add("dtstart", interview.scheduled_at)
    event.add("dtend", interview.scheduled_at + timedelta(minutes=duration_minutes))
    event.add("dtstamp", datetime.now(UTC))
    if interview.location:
        event.add("location", interview.location)
    elif interview.meeting_url:
        event.add("location", interview.meeting_url)
    if organizer_email:
        event.add("organizer", f"mailto:{organizer_email}")
    for email in attendee_emails or []:
        event.add("attendee", f"mailto:{email}")
    cal.add_component(event)
    return cal.to_ical()
