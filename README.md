# HanziFlow ? Chinese Learning App

**Python ? Tkinter desktop application ? MIT license ? Discontinued prototype**

HanziFlow is an older desktop project for learning Chinese. I stopped working on it when I shifted my focus to building a web application. This repository preserves the desktop prototype for reference, experimentation, and learning.

**The application has known, unfixed bugs and unfinished features. It is not production-ready, actively maintained, or guaranteed to work reliably.** The UI, implementation, and overall experience are rough in places. The cleanup for this release removes private data and addresses specific security issues; it does not turn the prototype into a finished product. No website source is included.

## Language, framework, and features

- **Language:** Python, with Python 3.11 used for the local checks.
- **GUI framework:** Tkinter/ttk, with tkinterdnd2 and tkcalendar widgets.
- **Audio:** pygame, PyAudio, gTTS, and optional Gemini TTS.
- **Other libraries:** requests, Pillow, PyPDF2, and python-docx.
- **Packaging:** PyInstaller for optional Windows executable builds.
- **Storage:** local JSON files; there is no application backend or SQL database.

The prototype includes vocabulary import, adaptive quizzes, grammar, writing, pronunciation exercises, XP, streaks, achievements, an arena, and a leaderboard. The interface supports English and Serbian. Friends/chat and automatic updates are experimental integrations, disabled by default.

## Run locally on Windows

Install Python 3.11 or newer with Tkinter. An audio device is needed for playback and a microphone for speaking exercises. Some dependencies, particularly PyAudio, may need platform-specific installation support.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

If a working `.venv` already exists, use the last command. Create your own local account on the first run. No real users, passwords, API keys, or personal records are supplied.

## Optional configuration

Both `.env.example` and `.env.template` contain empty credential fields and safe example settings. Copy either file to `.env` and enter your own credentials locally:

```powershell
Copy-Item .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | AI text and image processing, generated exercises, and coaching |
| `GEMINI_API_KEY` | Gemini text-to-speech and recorded-speech evaluation |
| `HANZIFLOW_ONEDRIVE_TOKEN` | Optional leaderboard sync through Microsoft Graph |
| `HANZIFLOW_ENABLE_LAN` | Defaults to `0`; `1` enables the experimental LAN protocol |
| `HANZIFLOW_ENABLE_UPDATES` | Defaults to `0`; `1` enables the experimental updater |
| `HANZIFLOW_UPDATE_REPOSITORY` | GitHub `owner/repository`, only for explicitly enabled updates |

Existing process environment variables take precedence. Only the external `.env` beside the project or packaged EXE is loaded. Credentials are not bundled into executable builds or printed in the modified API logging paths.

AI features require the relevant provider key. Existing local learning content and sound effects do not. Pronunciation playback may still use the network through gTTS without a Gemini key. Text, images, speech recordings, and selected learning statistics used by online features may be sent to the configured providers; this is not a fully offline application.

## Project structure

```text
main.py                  Desktop entry point
hanziflow/config.py      Local configuration and username validation
hanziflow/core/          Models, JSON storage, learning, AI, audio, SFX, LAN, updater
hanziflow/ui/            Tkinter controller, theme, widgets, and views
scripts/check_public.py Source publication checks
tests/test_security.py  Isolated security regressions and sound-generation checks
build_exe.py             Optional Windows EXE builder
ARCHITECTURE.md          Components, data flow, and trust boundaries
LICENSE                  MIT license for this project's code
```

`hanziflow/` is the application itself and must remain. The former `website/` directory has been removed. All nine procedural sound effects are preserved in `hanziflow/core/sounds.py`; they are separate from the deleted pronunciation cache.

## Local data and publication

Running the application can recreate `users/`, `audio_cache/`, `session.json`, `leaderboard.json`, and `hanziflow.log`. These may contain email addresses, password hashes, messages, learning records, and audio. They are ignored by Git, together with local virtual environments, editor state, generated binaries, and temporary test directories. Share the reviewed source tree rather than your entire used working folder.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B scripts/check_public.py
```

The source scanner checks recognizable credential formats, private Windows home paths, runtime artifacts, environment templates, and Python syntax. It excludes virtual environments, Git history, and temporary test directories. It cannot detect every possible secret or revoke credentials at a provider.

Local validation: **13 tests passed**, including password handling, filename validation, safe configuration, disabled network integrations, logging checks, and all nine SFX as WAV data. Tests use mocked provider requests; they do not prove live provider functionality or device playback. The actual desktop UI, microphone, multiplayer, and a rebuilt EXE have not been verified during this cleanup.

## Known unfinished work and bugs

- The prototype has unfixed UI, interaction, and reliability bugs; there is no complete bug inventory or full end-to-end verification.
- Local JSON profiles and remembered sessions are not protected against another process with filesystem access.
- The experimental LAN protocol lacks authentication and uses reversible XOR obfuscation, not secure encryption.
- The experimental updater does not verify release signatures; enabling it does not create a secure update channel.
- Multiple application instances and all Tkinter thread callbacks have not been fully audited.
- Some exercises depend on provider responses, network availability, and API model support.

This repository is provided as-is; future fixes or support are not promised.

## Optional Windows build

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe build_exe.py
```

The builder deletes previous `build/` and `dist/` outputs. It includes public metadata and the license, not `.env`, users, or cached pronunciation audio. Configure your own external `.env` beside the EXE. No new executable was built or distributed during the cleanup.

## License

This project's code is available under the [MIT license](LICENSE). Dependencies and external services retain their own licenses and terms.
