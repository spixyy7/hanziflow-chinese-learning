"""Security regressions run in temporary storage, without real API calls."""
import hashlib
import io
import logging
import os
from pathlib import Path
import sys
import shutil
import uuid
import unittest
from unittest.mock import Mock, patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hanziflow import config
from hanziflow.core import ai_client, sounds
from hanziflow.core.database import Database
from hanziflow.core.models import UserProfile
from hanziflow.core.lan_server import LANServer, _friends_path
from hanziflow.core.notifications import _path as notification_path
from hanziflow.core import updater


class WorkspaceTemporaryDirectory:
    """Use inherited Windows ACLs for an isolated, disposable test directory."""
    def __init__(self):
        self.path = Path(__file__).resolve().parents[1] / ("hanziflow-test-" + uuid.uuid4().hex)
        self.path.mkdir(mode=0o777)
        self.name = str(self.path)

    def cleanup(self):
        root = Path(__file__).resolve().parents[1]
        if self.path.resolve().parent != root or not self.path.name.startswith("hanziflow-test-"):
            raise RuntimeError("Unsafe temporary directory")
        shutil.rmtree(self.path)


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = WorkspaceTemporaryDirectory()
        self.original_cwd = Path.cwd()
        os.chdir(self.temp.name)
        Database._instance = None
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()

    def tearDown(self):
        Database._instance = None
        self.environment.stop()
        os.chdir(self.original_cwd)
        self.temp.cleanup()

    def test_password_roundtrip_wrong_password_and_random_salt(self):
        password = "example-passphrase"
        first = UserProfile.hash_password(password)
        self.assertTrue(first.startswith("pbkdf2_sha256$600000$"))
        self.assertNotEqual(first, UserProfile.hash_password(password))
        self.assertTrue(UserProfile.verify_password_hash(password, first))
        self.assertFalse(UserProfile.verify_password_hash("incorrect", first))

    def test_invalid_hashes_fail_closed(self):
        for value in (None, "", "pbkdf2_sha256$999999999$bad$bad", "pbkdf2_sha256$600000$zz$bad"):
            with self.subTest(value=value):
                self.assertFalse(UserProfile.verify_password_hash("example", value))

    def test_oversized_password_rejected(self):
        with self.assertRaises(ValueError):
            UserProfile.hash_password("x" * 1025)
        self.assertFalse(UserProfile.verify_password_hash("x" * 1025, "invalid"))

    def test_legacy_password_migrates_after_successful_login(self):
        db = Database()
        profile = db.create_user("learner", "example@example.invalid", "example-passphrase")
        for legacy in (
            hashlib.sha256(b"example-passphrase").hexdigest(),
            "salt$" + hashlib.sha256(b"saltexample-passphrase").hexdigest(),
        ):
            profile.password_hash = legacy
            db.save_user(profile)
            self.assertFalse(db.verify_password("learner", "wrong"))
            self.assertEqual(db.get_user("learner").password_hash, legacy)
            self.assertTrue(db.verify_password("learner", "example-passphrase"))
            self.assertTrue(db.get_user("learner").password_hash.startswith("pbkdf2_sha256$"))

    def test_case_insensitive_duplicate_does_not_overwrite_profile(self):
        db = Database()
        db.create_user("Learner", "example@example.invalid", "example-passphrase")
        with self.assertRaises(ValueError):
            db.create_user("learner", "other@example.invalid", "another-passphrase")
        self.assertTrue(db.verify_password("Learner", "example-passphrase"))

    def test_invalid_username_paths_rejected(self):
        for name in ("../escape", "a/b", "a\\b", "", "_index", "person_friends", "CON", "LPT1", "x" * 65):
            for fn in (config.validate_username, _friends_path, notification_path):
                with self.subTest(name=name, fn=fn.__name__), self.assertRaises(ValueError):
                    fn(name)

    def test_environment_uses_only_app_file_and_preserves_existing_values(self):
        home = Path(self.temp.name) / "app"
        home.mkdir()
        (home / ".env").write_text("OPENROUTER_API_KEY=local-value\nUNRELATED=ignored\n", encoding="utf-8")
        os.environ["OPENROUTER_API_KEY"] = "process-value"
        with patch.object(config, "application_dir", return_value=home):
            config.load_environment()
        self.assertEqual(os.environ["OPENROUTER_API_KEY"], "process-value")
        self.assertNotIn("UNRELATED", os.environ)

    def test_parent_environment_file_is_not_loaded(self):
        home = Path(self.temp.name) / "app"
        home.mkdir()
        (home.parent / ".env").write_text("GEMINI_API_KEY=parent-value\n", encoding="utf-8")
        with patch.object(config, "application_dir", return_value=home):
            self.assertEqual(config.secret("GEMINI_API_KEY"), "")

    def test_lan_default_creates_no_threads_or_connections(self):
        profile = Mock(username="learner")
        server = LANServer(profile, Mock())
        with patch("hanziflow.core.lan_server.threading.Thread") as thread:
            server.start()
            thread.assert_not_called()
        self.assertFalse(server._running)
        with patch("hanziflow.core.lan_server.socket.socket") as socket:
            self.assertFalse(server._send_tcp("friend", {}))
            server.broadcast_presence()
            socket.assert_not_called()

    def test_updates_default_performs_no_requests_or_downloads(self):
        with patch("urllib.request.urlopen") as request:
            self.assertIsNone(updater.check_for_update())
            on_error = Mock()
            updater.download_and_apply("https://example.invalid/update", on_error=on_error)
            on_error.assert_called_once()
            request.assert_not_called()

    def test_openrouter_error_does_not_log_credentials_or_response_body(self):
        client = ai_client.GeminiClient()
        credential = "sk-or-v1-" + "synthetic" * 4
        client._session.post = Mock(return_value=Mock(status_code=401, text=credential))
        with patch.object(ai_client, "API_KEY", credential), self.assertLogs(ai_client.logger, level="ERROR") as logs:
            self.assertIsNone(client._post_openrouter("example"))
        self.assertNotIn(credential, "\n".join(logs.output))

    def test_gemini_key_in_header_not_url(self):
        client = ai_client.GeminiClient()
        client._session.post = Mock(return_value=Mock(status_code=400))
        with patch.object(ai_client, "GEMINI_KEY", "synthetic-value"):
            self.assertIsNone(client.tts("example"))
        args, kwargs = client._session.post.call_args
        self.assertNotIn("key=", args[0])
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "synthetic-value")

    def test_sfx_all_nine_effects_generate_valid_wav(self):
        for name in ("click", "hover", "correct", "wrong", "xp_gain", "level_up", "achievement", "streak", "coach"):
            with self.subTest(name=name):
                data = sounds._get_sound(name)
                with wave.open(io.BytesIO(data), "rb") as wav:
                    self.assertGreater(wav.getnframes(), 0)
                    self.assertEqual(wav.getsampwidth(), 2)


if __name__ == "__main__":
    unittest.main()
