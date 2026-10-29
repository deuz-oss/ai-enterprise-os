# avatar-worker — Wajah Video Pewawancara AI (PoC self-hosted)

PoC wajah video untuk AI Interview suara real-time, **tanpa vendor avatar**
(tanpa Tavus). Otak interview tetap milik Aeos: STT/LLM/TTS, alur pertanyaan
(`agent/interview_flow.py`), rubrik, dan penilaian di backend **tidak
berubah**. Worker ini hanya "wajah": ia menerima audio TTS dari agen lalu
mempublikasikan video + audio yang tersinkron ke kandidat.

**Opt-in.** Default `AVATAR_PROVIDER=none` = voice-only seperti sebelum
fitur ini ada.

## Arsitektur

```
browser kandidat ⇄ LiveKit ⇄ agent (STT/LLM/TTS + alur — tidak berubah)
                              │ audio TTS: DataStreamAudioOutput (topik lk.audio_stream)
                              ▼
                        avatar-worker  (peserta "ai-interview-avatar", kind agent,
                        atribut lk.publish_on_behalf = identitas agen)
                        DataStreamAudioReceiver → RendererVideoGenerator → AvatarRunner
                              │ AVATAR_RENDERER
                    ┌─────────┴──────────┐
              StaticRenderer        FlashHeadRenderer ──WebSocket──► flashhead-server (GPU)
              (CPU, foto+indikator)                                  (../flashhead-server)
```

1. Sebelum sesi dimulai, agen (`agent/avatar.py`) memanggil
   `POST /sessions` (ditandatangani HMAC `LIVEKIT_API_SECRET` atas nama room).
2. Worker menyiapkan renderer. Kalau penuh atau gagal, worker menjawab `503`
   dan agen jalan **voice-only**. Kalau berhasil, worker menjawab `201` lalu
   join room.
3. Agen menunggu avatar join dan mempublikasikan video (`AVATAR_JOIN_TIMEOUT`,
   default 15 dtk). Baru setelah itu output audio sesi diganti ke
   `DataStreamAudioOutput`.
4. Worker keluar saat agen keluar dari room, saat menerima `DELETE /sessions/{room}`,
   atau setelah `AVATAR_MAX_SESSION_SEC`.

### API LiveKit yang dipakai (diverifikasi, bukan ditebak)

Kelas, parameter, dan perilakunya dibaca langsung dari source
**livekit-agents 1.7.1**, versi yang sudah dikunci di `agent/`, jadi **tidak
perlu upgrade**. Turn handling, TurnDetector v1-mini, dan perekam `audio.ogg`
tidak tersentuh.

| Sisi | Kelas (modul) |
|---|---|
| agen | `DataStreamAudioOutput(room, destination_identity=, sample_rate=, wait_playback_start=True)` (`livekit.agents.voice.avatar`) |
| worker | `DataStreamAudioReceiver`, `AvatarRunner`, `AvatarOptions`, `VideoGenerator`, `AudioSegmentEnd` (`livekit.agents.voice.avatar`) |
| penanda avatar | `ATTRIBUTE_PUBLISH_ON_BEHALF = "lk.publish_on_behalf"` (`livekit.agents.voice.room_io`); cara frontend mengenali avatar mengikuti docs.livekit.io |
| RPC | `lk.playback_started`, `lk.playback_finished`, `lk.clear_buffer` (dikelola LiveKit) |

Contoh resmi LiveKit untuk avatar lokal (`examples/avatar_agents/audio_wave`)
sudah tidak ada di `main` maupun di tag 1.7.1. Karena itu wiring di sini
disusun dari kelas-kelas di atas, bukan disalin dari contoh.

## Renderer (pluggable)

Satu interface, `AvatarRenderer` (`renderers.py`):

| Metode | Arti |
|---|---|
| `start(reference_image)` | siapkan sesi; `RendererUnavailable` → worker 503 → voice-only |
| `push_audio(pcm)` / `end_segment()` | audio TTS int16 mono 24 kHz, per ucapan |
| `clear()` | kandidat memotong: buang audio yang belum diputar |
| `frames()` | aliran `RenderedFrame(image, audio)` / `SEGMENT_END`, frame diam saat tidak bicara |

- **`static`** (default): foto referensi dengan cincin indikator bicara
  (berdasarkan RMS audio), murni CPU, 512×512 @ 25 fps. Gunanya menguji wiring
  end-to-end di mesin dev tanpa GPU. Tanpa foto, yang tampil siluet netral.
- **`flashhead`**: klien `flashhead-server` (SoulX-FlashHead di GPU, lihat
  `../flashhead-server/README.md`). Kalau server putus, sebuah chunk melebihi
  `FLASHHEAD_CHUNK_TIMEOUT`, atau antrean tertinggal lebih dari
  `FLASHHEAD_MAX_BACKLOG` chunk, renderer **turun ke StaticRenderer di tengah
  sesi**. Audio yang belum dirender dipindah utuh, jadi kandidat tetap
  mendengar pewawancara. Tanpa mekanisme ini agen akan menunggu laporan
  "selesai diputar" yang tidak pernah datang, dan sesi menggantung.

Video selalu membawa label tetap **"Pewawancara AI - avatar, bukan orang
sungguhan"**. Avatar tidak boleh tampil seolah manusia.

## Menyalakan di CPU (StaticRenderer)

```
# .env: AVATAR_PROVIDER=self (AVATAR_RENDERER kosong = static)
docker compose --profile voice --profile avatar up -d --build
```

Profile `avatar` **selalu** dipakai bersama `voice`, karena butuh service
`livekit`. `docker compose up` biasa dan `--profile voice` saja tidak
menyalakan worker ini.

## Env

| Variabel | Default | Arti |
|---|---|---|
| `AVATAR_PROVIDER` (agen) | `none` | `none` = voice-only, `self` = worker ini. Nilai lain (mis. `tavus`) diperlakukan sebagai `none` + warning; integrasi Tavus tidak ada di repo |
| `AVATAR_JOIN_TIMEOUT` (agen) | `15` | batas tunggu avatar join + video sebelum sesi jatuh ke voice-only |
| `AVATAR_CANDIDATE_TIMEOUT` (agen) | `120` | batas tunggu kandidat masuk room sebelum sapaan (mode avatar); lewat → job diakhiri, slot avatar dilepas |
| `AVATAR_RENDERER` | `static` | `static` \| `flashhead` |
| `AVATAR_MAX_SESSIONS` | `2` | sesi avatar paralel. Penuh → sesi baru **voice-only** (tidak ditolak, tidak antre) |
| `AVATAR_REFERENCE_IMAGE` | kosong | path **di dalam container**, mis. `/srv/avatar/reference.jpg` (file ditaruh di `./deploy/avatar/`, isinya di-gitignore) |
| `FLASHHEAD_URL` | `ws://flashhead-server:8010/stream` | diisi di compose |
| `FLASHHEAD_CHUNK_TIMEOUT` / `FLASHHEAD_MAX_BACKLOG` | `5` / `3` | ambang turun ke StaticRenderer |
| `AVATAR_START_TIMEOUT` / `AVATAR_MAX_SESSION_SEC` | `15` / `3600` | batas siap renderer / durasi sesi |

### Foto referensi: wajib milik sendiri atau berizin tertulis

Wajah di foto referensi adalah data pribadi **orang di foto**. Pakai hanya
foto milik sendiri, atau foto yang orangnya sudah memberi **izin tertulis**
untuk dijadikan avatar AI. Untuk varian FlashHead `lite`, lisensi VAE LTX
juga melarang impersonasi tanpa persetujuan (Attachment A #8). Foto di-mount
read-only dari `./deploy/avatar/` dan tidak pernah di-commit.

Konfigurasi foto **per tenant belum ada**: itu butuh kolom DB baru, sedangkan
PoC ini sengaja tidak mengubah skema. Untuk saat ini satu foto per deployment
lewat env.

## Kapasitas & fallback

Semua jalur gagal berakhir di **voice-only**. Tidak ada yang membuat agen
crash atau sesi kandidat menggantung.

| Kondisi | Hasil | Diuji |
|---|---|---|
| `AVATAR_PROVIDER=none` / nilai tak dikenal | voice-only (perilaku lama) | unit test |
| worker mati / tak terjangkau | voice-only, keputusan ≤ 3 dtk (`ConnectTimeout`) | unit + **E2E** |
| kapasitas penuh (`AVATAR_MAX_SESSIONS`) | worker 503 → voice-only | unit test |
| renderer gagal start (mis. flashhead-server mati) | worker 503 → voice-only | unit test |
| avatar tidak join dalam `AVATAR_JOIN_TIMEOUT` | slot dilepas → voice-only | unit (logika tunggu) |
| **worker mati di tengah sesi** | sink audio di dasar rantai output ditukar ke track audio agen sendiri (`_AudioSinkProxy.set_next_in_chain`); cadangan: sesi diakhiri rapi + transkrip parsial terkirim | unit + **E2E** |
| flashhead-server putus/lambat di tengah sesi | turun ke StaticRenderer, audio utuh | unit (server palsu) |

Fallback di tengah sesi memakai dua kelas **privat** LiveKit 1.7.1
(`_AudioSinkProxy`, `_ParticipantAudioOutput`). `agent/tests` gagal kalau
keduanya hilang. Setiap upgrade livekit-agents wajib mengecek ulang
`agent/avatar.py`.

## Uji

```
cd avatar-worker && python -m pytest tests     # 21 test: renderer, adapter, kapasitas, HTTP, klien FlashHead
cd agent && python -m pytest tests             # termasuk flag & fallback avatar
```

**E2E wiring dengan kandidat sintetis** (`scripts/e2e_synthetic_candidate.py`,
pola uji Fase 66). Skrip membuat template + kandidat lewat API, bergabung
sebagai peserta LiveKit sungguhan, memutar jawaban TTS, lalu memeriksa
transkrip, skor, dan kedua kanal `audio.ogg`.

Hasil 2026-10-23, Docker Desktop, CPU, StaticRenderer:

| Skenario | Video avatar | Suara pewawancara dari | Transkrip / skor | `audio.ogg` kanal 0 (kandidat) / 1 (AI) |
|---|---|---|---|---|
| avatar normal | ✅ 1707 frame, `kind=agent`, atribut benar | avatar | utuh / 90 | 15 / 34 dtk aktif |
| worker mati sejak awal | — | agen (voice-only) | utuh / 90 | 15,5 / 23 dtk |
| worker dimatikan setelah giliran 1 + kandidat telat masuk 40 dtk | ✅ lalu hilang | avatar → agen (detik yang sama) | utuh / 90 | 17 / 36,5 dtk |

**`audio.ogg` terbukti masih berisi suara kandidat DAN suara AI** setelah
audio dialihkan ke avatar. Ini diukur dari energi per kanal hasil dekode file
yang diunduh dari backend, bukan diasumsikan.

Bug yang ditemukan uji ini dan sudah diperbaiki:
- **Sapaan diucapkan ke room kosong.** Di mode avatar, kandidat yang masuk
  50 dtk setelah avatar tidak pernah mendengar sapaan maupun pertanyaan
  pertama. Kini agen menunggu kandidat masuk dulu.
- **Worker yang mati menunda sapaan.** DNS Docker untuk container yang mati
  baru gagal setelah ~9 dtk; kini koneksi dibatasi 3 dtk.
- **Waktu mulai bicara AI tidak akurat.** Kini memakai `lk.playback_started`
  dari avatar, jadi offset transkrip & posisi suara di rekaman ikut tepat.

Temuan yang **tidak** terkait avatar (terjadi juga di voice-only murni):
jeda antar-kalimat TTS OpenAI di jaringan dev bisa lebih dari 6 dtk di
tengah sapaan. Kandidat sintetis dengan ambang hening 3–6 dtk memotong
pertanyaan yang belum selesai, sehingga skrip kini memakai ambang 8 dtk.
Kandidat manusia juga bisa mengalaminya. Ini masalah latensi TTS, belum
ditangani.

## Keterbatasan — catatan kejujuran

- E2E di atas memakai **kandidat sintetis di CPU**, bukan manusia dengan
  mikrofon dan kamera browser sungguhan. Tampilan video di
  `AIInterviewVoiceCall.tsx` lolos `tsc` + build, tapi **belum dilihat di
  browser** saat sesi avatar berjalan.
- **FlashHeadRenderer hanya diuji terhadap server palsu** (protokol sama,
  tanpa model). Kualitas lip-sync Bahasa Indonesia, latensi nyata, dan jumlah
  sesi paralel di GPU **belum teruji sama sekali**. Lihat
  `../flashhead-server/README.md`.
- Mode avatar mematikan `resume_false_interruption` LiveKit
  (`DataStreamAudioOutput` tidak bisa pause; library mencatat warning). Kalau
  kandidat bersuara sebentar, ucapan AI berhenti dan tidak dilanjutkan
  seperti di voice-only. Dampaknya ke rasa percakapan belum dinilai manusia.
- Persetujuan kandidat yang diberikan **sebelum** consent `2026-10-23.1`
  tidak diminta ulang (`_require_consent` hanya mengecek ada/tidaknya
  persetujuan, bukan versinya). Perilaku lama ini sengaja dipertahankan.

## Versi dependensi

Dikunci di `requirements.lock`, dengan versi LiveKit dipaksa sama dengan
`agent/requirements.lock`. Regenerasi dari folder ini:

```
uv pip compile pyproject.toml --universal --python-version 3.12 -c ../agent/requirements.lock -o requirements.lock
uv pip compile pyproject.toml --universal --python-version 3.12 -c ../agent/requirements.lock --extra dev -o requirements-dev.lock
```
