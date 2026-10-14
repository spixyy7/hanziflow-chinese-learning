# Security review and source cleanup

Local review date: 2026-10-15. HanziFlow is a discontinued desktop prototype with unresolved bugs and unfinished features. This is a record of specific findings and changes, not a security certification or complete penetration test.

## Removed private material

- Real credentials from `.env` and the previously populated `.env.template`.
- All existing local accounts, email addresses, password hashes, profiles, friends, messages, queued events, notifications, and writing cache.
- Remembered session, leaderboard records, logs, and per-user pronunciation caches.
- Old executable/build outputs, Python bytecode, and backup source copies.
- Local Claude/editor state, internal development plan, and the entire former website directory.

`.env.example` and `.env.template` now contain empty credential fields and example settings only. No old password or credential is included in this report.

**Deleting local files does not revoke provider credentials or remove other project copies, previously shared executables, conversation history, cloud backups, or recoverable disk contents. Previously exposed OpenRouter and Google keys must be revoked or rotated by their owner.** This cleanup is not secure disk erasure.

## Changes and remaining limits

| Finding | Handling |
| --- | --- |
| Executable build embedded `.env` and cached audio | Removed private build resources; retained public metadata and license |
| Full and partial API credentials in logs | Removed credential-value logging |
| Gemini credential in URL and network error details | Moved key into a header; request failures log exception type |
| Raw AI responses and HTTP error bodies in logs | Removed content from those logging branches |
| Broad parent-directory `.env` search | Restricted loading to the external application `.env`; existing variables win |
| Fast SHA-256 password hashing | PBKDF2-HMAC-SHA256, random salt, bounded input/work factor, constant-time comparison and legacy migration |
| Unchecked usernames used in paths | Validated profile, message, notification, audio and writing-cache paths; reserved-name and duplicate-account checks |
| Unauthenticated LAN and reversible XOR | Disabled by default; added connection timeout and rejection of chat from non-friends; protocol remains insecure |
| Automatic unsigned EXE replacement | Disabled by default; explicit repository configuration and initial URL restriction; signature verification remains absent |
| Recreated private data could be published | `.gitignore` and a read-only source checker |

Password storage uses Python's standard [hashlib key-derivation API](https://docs.python.org/3/library/hashlib.html#key-derivation). The source license follows the [Open Source Initiative MIT text](https://opensource.org/license/mit); third-party dependencies retain their own terms.

## Unresolved issues

- Local profiles, messages, and remembered sessions are not encrypted or protected from another process with access to those files.
- The experimental LAN protocol cannot authenticate peers and does not provide secure encryption, even on a LAN.
- The opt-in updater lacks release signature verification and independently controlled redirect handling.
- Optional OneDrive ranking has no authoritative application server to validate results.
- Existing UI, interaction, and reliability bugs remain; there is no complete bug inventory or full end-to-end pass.
- Multiple instances, every Tkinter callback, imported-document parsers, and the full dependency CVE surface have not been audited.
- AI and gTTS actions use external services and can transmit user-provided content.

Disabling a risky feature reduces default exposure; it does not claim to repair that feature's design. Do not use this prototype as a secure multi-user service or rely on it for sensitive records.

## Validation

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/check_public.py
```

The 13 regression tests passed locally. They exercise passwords and legacy migration, filename checks, configuration, disabled LAN/update behavior, API logging, Gemini authentication placement, and all nine SFX as valid WAV data. Tests use disposable workspace storage and mock provider requests.

The scanner checks recognizable credential patterns, private Windows home paths, runtime/build artifacts, environment templates, and Python syntax. Virtual environments, Git history, and temporary test directories are excluded. It cannot recognize every possible secret or verify provider-side revocation.

Not verified: a new executable build, the actual desktop UI, audible device playback, microphone recording, live provider/Graph calls, LAN between devices, and dependency vulnerability databases. Git was initialized only after cleanup, so the local repository's initial source commit does not import prior project history. Network restrictions may prevent GitHub publication; publication status must be verified separately.
