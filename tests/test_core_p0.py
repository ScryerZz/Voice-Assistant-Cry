import queue
import threading
import logging
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from main import _recognition_result_parts, recognizer_worker
from src.core.config import Settings
from src.core import tts as tts_module
from src.core.executor import Executor
from src.core.matcher import SmartMatcher
from src.core.recognizer import Recognizer
from src.core.storage import AssistantStorage


class DummySkills:
    def __init__(self):
        self.calls = []

    def execute(self, action: str, text: str = None, **kwargs):
        self.calls.append((action, text, kwargs))
        return f"ran {action}"


class FakeRecognizer:
    def __init__(self, results=None, stop_event=None, config=None, default_lang="ru"):
        self.results = list(results or [])
        self.stop_event = stop_event
        self.config = config or {
            "recognition": {
                "miss_threshold": 99,
                "repeat_prompt_enabled": False,
                "recover_after_errors": 3,
            }
        }
        self.default_lang = default_lang
        self.listen_calls = 0
        self.recover_calls = 0

    def listen_text(self):
        self.listen_calls += 1
        if not self.results:
            if self.stop_event:
                self.stop_event.set()
            return None

        result = self.results.pop(0)
        if not self.results and self.stop_event:
            self.stop_event.set()
        if isinstance(result, BaseException):
            raise result
        return result

    def recover(self):
        self.recover_calls += 1


def _queue_items(items_queue):
    items = []
    while True:
        try:
            items.append(items_queue.get_nowait())
        except queue.Empty:
            return items


def _dataset():
    return {
        "skills": {
            "test": {
                "description": "Test commands",
                "commands": [
                    {
                        "patterns": ["safe command"],
                        "action": "test.safe",
                        "response": {"en": "safe"},
                    },
                    {
                        "patterns": ["danger command"],
                        "action": "test.danger",
                        "response": {"en": "danger"},
                    },
                ],
            }
        }
    }


def _config():
    return {
        "debug": False,
        "matcher": {"threshold": 90, "partial_threshold": 95, "smalltalk_threshold": 80},
        "safety": {
            "confirm_dangerous_commands": True,
            "confirmation_timeout_seconds": 15,
            "dangerous_actions": ["test.danger"],
        },
    }


class RecognitionContractTests(unittest.TestCase):
    def test_empty_tuple_result_is_a_miss(self):
        text, lang = _recognition_result_parts(("", "ru"), "ru")

        self.assertEqual(text, "")
        self.assertEqual(lang, "ru")

    def test_none_result_is_a_miss(self):
        text, lang = _recognition_result_parts(None, "en")

        self.assertEqual(text, "")
        self.assertEqual(lang, "en")

    def test_text_tuple_is_normalized(self):
        text, lang = _recognition_result_parts(("  safe command  ", "en"), "ru")

        self.assertEqual(text, "safe command")
        self.assertEqual(lang, "en")


class RecognizerModelPathTests(unittest.TestCase):
    def _make_vosk_model(self, root: Path, folder: str) -> Path:
        model = root / folder
        for relative in (
            Path("am") / "final.mdl",
            Path("conf") / "model.conf",
            Path("graph") / "HCLr.fst",
            Path("graph") / "Gr.fst",
        ):
            path = model / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("ok", encoding="utf-8")
        return model

    def test_configured_stt_models_path_has_priority(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            configured = root / "stt"
            legacy = root / "models"
            folder = "vosk-model-small-ru-0.22"
            configured_model = self._make_vosk_model(configured, folder)
            self._make_vosk_model(legacy, folder)

            recognizer = Recognizer.__new__(Recognizer)
            recognizer.models_dir = configured
            recognizer.legacy_models_dir = legacy
            recognizer.logger = logging.getLogger("Recognizer.test")

            self.assertEqual(recognizer._resolve_vosk_model_path("ru", folder), configured_model)

    def test_legacy_stt_model_is_used_when_configured_path_missing(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            configured = root / "stt"
            legacy = root / "models"
            folder = "vosk-model-small-ru-0.22"
            legacy_model = self._make_vosk_model(legacy, folder)

            recognizer = Recognizer.__new__(Recognizer)
            recognizer.models_dir = configured
            recognizer.legacy_models_dir = legacy
            recognizer.logger = logging.getLogger("Recognizer.test")

            self.assertEqual(recognizer._resolve_vosk_model_path("ru", folder), legacy_model)

    def test_missing_stt_model_resolves_to_configured_path_for_downloads(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            configured = root / "stt"
            legacy = root / "models"
            folder = "vosk-model-small-ru-0.22"

            recognizer = Recognizer.__new__(Recognizer)
            recognizer.models_dir = configured
            recognizer.legacy_models_dir = legacy
            recognizer.logger = logging.getLogger("Recognizer.test")

            self.assertEqual(recognizer._resolve_vosk_model_path("ru", folder), configured / folder)


class RecognizerWorkerTests(unittest.TestCase):
    def _run_worker(self, results, config=None):
        stop_event = threading.Event()
        output_queue = queue.Queue()
        prompt_queue = queue.Queue()
        recognizer = FakeRecognizer(results, stop_event=stop_event, config=config)

        recognizer_worker(
            recognizer,
            stop_event=stop_event,
            output_queue=output_queue,
            prompt_queue=prompt_queue,
            voice_enabled=lambda default=True: True,
            sleep=lambda _seconds: None,
        )

        return recognizer, _queue_items(output_queue), _queue_items(prompt_queue)

    def test_worker_treats_none_empty_tuple_and_whitespace_as_misses(self):
        for result in (None, (), "   "):
            with self.subTest(result=result):
                _recognizer, output_items, prompt_items = self._run_worker([result])

                self.assertEqual(output_items, [])
                self.assertEqual(prompt_items, [])

    def test_worker_enqueues_valid_text(self):
        _recognizer, output_items, prompt_items = self._run_worker(["  safe command  "])

        self.assertEqual(output_items, [("safe command", "ru")])
        self.assertEqual(prompt_items, [])

    def test_worker_stop_event_exits_without_listening(self):
        stop_event = threading.Event()
        stop_event.set()
        recognizer = FakeRecognizer(stop_event=stop_event)
        output_queue = queue.Queue()
        prompt_queue = queue.Queue()

        thread = threading.Thread(
            target=recognizer_worker,
            kwargs={
                "recognizer": recognizer,
                "stop_event": stop_event,
                "output_queue": output_queue,
                "prompt_queue": prompt_queue,
                "voice_enabled": lambda default=True: True,
                "sleep": lambda _seconds: None,
            },
        )
        thread.start()
        thread.join(timeout=0.5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(recognizer.listen_calls, 0)
        self.assertEqual(_queue_items(output_queue), [])
        self.assertEqual(_queue_items(prompt_queue), [])

    def test_worker_recovers_after_exception_series_and_continues(self):
        recognizer, output_items, prompt_items = self._run_worker(
            [
                RuntimeError("first"),
                RuntimeError("second"),
                RuntimeError("third"),
                ("  recovered command  ", "en"),
            ]
        )

        self.assertEqual(recognizer.recover_calls, 1)
        self.assertEqual(output_items, [("recovered command", "en")])
        self.assertEqual(prompt_items, [])


class SafetyPreflightTests(unittest.TestCase):
    def test_analyze_reports_match_without_side_effects(self):
        skills = DummySkills()
        executor = Executor(_dataset(), skills, config=_config())

        analysis = executor.analyze("safe command then danger command", lang="en")

        self.assertEqual(analysis["status"], "confirmation_required")
        self.assertEqual(analysis["actions"], ["test.safe", "test.danger"])
        self.assertEqual(analysis["dangerous_actions"], ["test.danger"])
        self.assertEqual(skills.calls, [])

    def test_compound_command_waits_before_any_side_effect(self):
        skills = DummySkills()
        executor = Executor(_dataset(), skills, config=_config())

        response = executor.handle("safe command then danger command", lang="en")

        self.assertIn("test.danger", response)
        self.assertEqual(executor.last_trace["status"], "confirmation_required")
        self.assertEqual(skills.calls, [])

        confirmed = executor.handle("confirm", lang="en")

        self.assertEqual(executor.last_trace["status"], "confirmed")
        self.assertIn("ran test.safe", confirmed)
        self.assertIn("ran test.danger", confirmed)
        self.assertEqual([call[0] for call in skills.calls], ["test.safe", "test.danger"])

    def test_generic_yes_does_not_confirm_dangerous_action(self):
        skills = DummySkills()
        executor = Executor(_dataset(), skills, config=_config())

        executor.handle("danger command", lang="en")
        response = executor.handle("yes", lang="en")

        self.assertEqual(executor.last_trace["status"], "confirmation_rejected")
        self.assertIn("canceled", response.lower())
        self.assertEqual(skills.calls, [])

    def test_low_confidence_dangerous_action_is_rejected_before_confirmation(self):
        config = _config()
        config["safety"]["dangerous_min_score"] = 90
        skills = DummySkills()
        executor = Executor(_dataset(), skills, config=config)
        executor.matcher.find_matches = lambda _text: [{
            "pattern": "danger command",
            "category": "skills",
            "key": "test",
            "action": "test.danger",
            "response": {"en": "danger"},
            "score": 70,
        }]

        response = executor.handle("maybe danger", lang="en")

        self.assertEqual(executor.last_trace["status"], "dangerous_low_confidence")
        self.assertIn("not recognized confidently", response)
        self.assertIsNone(executor.confirmations.pending)
        self.assertEqual(skills.calls, [])


class MatcherOneWordTests(unittest.TestCase):
    def test_one_word_pattern_still_matches_exact_phrase(self):
        dataset = {
            "skills": {
                "help": {
                    "commands": [
                        {"patterns": ["help"], "action": "help.show", "response": {"en": "help"}},
                    ]
                }
            }
        }
        matcher = SmartMatcher(dataset, threshold=70, config={"matcher": {"threshold": 70}})

        matches = matcher.find_matches("help")

        self.assertEqual(matches[0]["action"], "help.show")
        self.assertEqual(matches[0]["score"], 100)

    def test_one_word_pattern_is_not_fuzzy_candidate_for_long_phrase(self):
        dataset = {
            "skills": {
                "search": {
                    "commands": [
                        {"patterns": ["search"], "action": "search.short", "response": {"en": "search"}},
                        {"patterns": ["search online"], "action": "search.online", "response": {"en": "online"}},
                    ]
                }
            }
        }
        matcher = SmartMatcher(dataset, threshold=70, config={"matcher": {"threshold": 70, "partial_threshold": 80}})

        matches = matcher.find_matches("search local project files")

        self.assertTrue(not matches or matches[0]["action"] != "search.short")

    def test_multi_word_pattern_remains_fuzzy_candidate_for_long_phrase(self):
        dataset = {
            "skills": {
                "search": {
                    "commands": [
                        {"patterns": ["search"], "action": "search.short", "response": {"en": "search"}},
                        {"patterns": ["search online"], "action": "search.online", "response": {"en": "online"}},
                    ]
                }
            }
        }
        matcher = SmartMatcher(dataset, threshold=70, config={"matcher": {"threshold": 70, "partial_threshold": 80}})

        matches = matcher.find_matches("search online project files")

        self.assertEqual(matches[0]["action"], "search.online")


class TTSFallbackTests(unittest.TestCase):
    def test_tts_uses_configured_model_directory(self):
        old_pyttsx3 = tts_module.pyttsx3
        try:
            tts_module.pyttsx3 = None
            with TemporaryDirectory() as temp_dir:
                tts = tts_module.HybridTTS({
                    "voice_engine": "pyttsx3",
                    "paths": {"tts_models": temp_dir},
                })

                self.assertEqual(tts._model_path("ru"), Path(temp_dir) / "v3_1_ru.pt")
        finally:
            tts_module.pyttsx3 = old_pyttsx3

    def test_empty_silero_model_in_offline_mode_falls_back_without_network(self):
        class FakeCuda:
            @staticmethod
            def is_available():
                return False

        class FakeTorch:
            cuda = FakeCuda()

        class FakeRequests:
            def __init__(self):
                self.called = False

            def get(self, *_args, **_kwargs):
                self.called = True
                raise AssertionError("network should not be used in offline mode")

        old_torch = tts_module.torch
        old_pyttsx3 = tts_module.pyttsx3
        old_requests = tts_module.requests
        fake_requests = FakeRequests()
        try:
            tts_module.torch = FakeTorch()
            tts_module.pyttsx3 = None
            tts_module.requests = fake_requests
            with TemporaryDirectory() as temp_dir:
                (Path(temp_dir) / "v3_1_ru.pt").write_bytes(b"")

                with self.assertLogs("HybridTTS", level="WARNING"):
                    tts = tts_module.HybridTTS({
                        "voice_engine": "silero",
                        "offline_mode": True,
                        "assistant": {"default_language": "ru"},
                        "paths": {"tts_models": temp_dir},
                        "silero": {"use_cuda": False},
                    })

                self.assertEqual(tts.current_engine, "pyttsx3")
                self.assertIsNone(tts.model)
                self.assertFalse(fake_requests.called)
        finally:
            tts_module.torch = old_torch
            tts_module.pyttsx3 = old_pyttsx3
            tts_module.requests = old_requests

    def test_silero_runtime_failure_switches_current_engine_to_pyttsx3(self):
        class FakeModel:
            calls = 0

            def apply_tts(self, **_kwargs):
                self.calls += 1
                raise RuntimeError("broken model")

        class FakePyttsx3Engine:
            def __init__(self):
                self.spoken = []
                self.run_count = 0

            def say(self, text):
                self.spoken.append(text)

            def runAndWait(self):
                self.run_count += 1

        old_torch = tts_module.torch
        try:
            fake_model = FakeModel()
            fake_engine = FakePyttsx3Engine()
            tts = tts_module.HybridTTS.__new__(tts_module.HybridTTS)
            tts.logger = tts_module.logging.getLogger("HybridTTS.test")
            tts.config = {"silero": {"sample_rate": 48000}}
            tts.voice_enabled = True
            tts.current_lang = "ru"
            tts.current_speaker = "kseniya"
            tts.current_engine = "silero"
            tts.model = fake_model
            tts.engine = fake_engine
            tts.silero_speakers = {"ru": ["kseniya"]}
            tts_module.torch = object()

            tts.speak("проверка")
            tts.speak("ещё раз")

            self.assertEqual(tts.current_engine, "pyttsx3")
            self.assertIsNone(tts.model)
            self.assertEqual(fake_model.calls, 1)
            self.assertEqual(fake_engine.spoken, ["проверка", "ещё раз"])
            self.assertEqual(fake_engine.run_count, 2)
        finally:
            tts_module.torch = old_torch


class ConfigDatasetMergeTests(unittest.TestCase):
    def test_settings_merge_user_commands_into_dataset(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.yaml"
            base_path = root / "commands.yaml"
            user_path = root / "user_commands.yaml"
            config_path.write_text(
                "paths:\n"
                f"  datasets: {base_path.as_posix()}\n"
                f"  user_commands: {user_path.as_posix()}\n",
                encoding="utf-8",
            )
            base_path.write_text(
                "skills:\n"
                "  base:\n"
                "    description: Base\n"
                "    commands:\n"
                "      - patterns: [base phrase]\n"
                "        action: assistant_info.list_capabilities\n",
                encoding="utf-8",
            )
            user_path.write_text(
                "skills:\n"
                "  user_custom:\n"
                "    description: User\n"
                "    commands:\n"
                "      - patterns: [custom phrase]\n"
                "        action: assistant_info.list_capabilities\n",
                encoding="utf-8",
            )

            settings = Settings(config_path=config_path, dataset_path=base_path)

            skills = settings.dataset["skills"]
            self.assertIn("base", skills)
            self.assertIn("user_custom", skills)
            self.assertEqual(skills["user_custom"]["commands"][0]["patterns"], ["custom phrase"])


class StorageManagementTests(unittest.TestCase):
    def test_delete_note_removes_only_selected_note(self):
        storage = AssistantStorage(":memory:")
        first_id = storage.add_note("first")
        second_id = storage.add_note("second")

        deleted = storage.delete_note(first_id)

        notes = storage.list_notes(limit=10)
        self.assertEqual(deleted, 1)
        self.assertEqual([note["id"] for note in notes], [second_id])

    def test_reminder_management_lists_completes_and_deletes(self):
        storage = AssistantStorage(":memory:")
        reminder_id = storage.add_reminder("reminder", "call", datetime.now() + timedelta(minutes=5))

        pending = storage.list_reminders(include_completed=False)
        self.assertEqual([item["id"] for item in pending], [reminder_id])

        storage.complete_reminders([reminder_id])
        self.assertEqual(storage.list_reminders(include_completed=False), [])
        completed = storage.list_reminders(include_completed=True)
        self.assertIsNotNone(completed[0]["completed_at"])

        removed = storage.clear_completed_reminders()
        self.assertEqual(removed, 1)
        self.assertEqual(storage.list_reminders(include_completed=True), [])

    def test_command_history_filters_by_source_status_and_query(self):
        storage = AssistantStorage(":memory:")
        storage.add_command_history(
            raw_text="open browser",
            normalized_text="open browser",
            language="en",
            status="matched",
            source="chat",
            actions=["system.open_browser"],
            patterns=["open browser"],
            scores=["100"],
            response="opened",
        )
        storage.add_command_history(
            raw_text="unknown phrase",
            normalized_text="unknown phrase",
            language="en",
            status="no_match",
            source="voice",
            response="not understood",
        )

        chat_rows = storage.list_command_history(source="chat")
        no_match_rows = storage.list_command_history(status="no_match")
        browser_rows = storage.list_command_history(query="browser")

        self.assertEqual([row["raw_text"] for row in chat_rows], ["open browser"])
        self.assertEqual([row["raw_text"] for row in no_match_rows], ["unknown phrase"])
        self.assertEqual([row["actions"] for row in browser_rows], ["system.open_browser"])


if __name__ == "__main__":
    unittest.main()
