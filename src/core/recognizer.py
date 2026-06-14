import os
import json
import queue
import requests
import zipfile
import sounddevice as sd
import io
import tempfile
import logging
import time
from pathlib import Path
from tqdm import tqdm
from vosk import Model, KaldiRecognizer, SetLogLevel
import speech_recognition as sr
from scipy.io.wavfile import write as wav_write

from src.core.config import resolve_runtime_path


VOSK_MODEL_FOLDERS = {
    "ru": "vosk-model-small-ru-0.22",
    "en": "vosk-model-small-en-us-0.15",
}


class Recognizer:
    """
    Постоянно активный Recognizer:
    - Онлайн (Google Speech)
    - Оффлайн (Vosk)
    - Микрофон не выключается между фразами
    """

    def __init__(self, config):
        self.logger = logging.getLogger("Recognizer")
        self.config = config
        self.recognition_config = config.get("recognition", {}) or {}
        self.default_lang = config.get("assistant", {}).get("default_language", "ru")
        self.language_map = {"ru": "ru-RU", "en": "en-US"}
        self.offline_mode = bool(config.get("offline_mode", False))
        self.auto_switch_mode = bool(config.get("auto_switch_mode", True))
        self.sample_rate = 16000
        self.blocksize = 8000
        self.audio_queue_timeout = float(self.recognition_config.get("audio_queue_timeout_seconds", 1.0))
        self.offline_listen_timeout = float(self.recognition_config.get("offline_listen_timeout_seconds", 8))

        paths_config = config.get("paths", {}) or {}
        self.models_dir = self._resolve_project_path(paths_config.get("stt_models", "data/models/stt"))
        self.legacy_models_dir = self._resolve_project_path("data/models")
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.vosk_models = {
            lang: self._resolve_vosk_model_path(lang, folder_name)
            for lang, folder_name in VOSK_MODEL_FOLDERS.items()
        }

        self.vosk_urls = {
            "ru": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
            "en": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        }

        SetLogLevel(-1)
        self.online_available = False if self.offline_mode else self._check_internet()
        self._ensure_vosk_models()
        self.vosk_recognizers = self._load_vosk_recognizers()

        self.mode = "online" if self.online_available else "offline"
        print(f"Mode: {self.mode.upper()}")
        print(f"Recognition language: {self.default_lang.upper()}")

        # Очередь аудио и постоянный поток
        self.audio_queue = queue.Queue()
        self.stream = None
        if self.mode == "offline":
            self._start_microphone_stream()

    def _resolve_project_path(self, path_value: str | Path) -> Path:
        return resolve_runtime_path(path_value, base="bundle")

    def _resolve_vosk_model_path(self, lang: str, folder_name: str) -> Path:
        configured_path = self.models_dir / folder_name
        if self._is_vosk_model_ready(configured_path):
            return configured_path

        legacy_path = self.legacy_models_dir / folder_name
        if self._is_vosk_model_ready(legacy_path):
            self.logger.info(f"Используется legacy Vosk-модель {lang.upper()}: {legacy_path}")
            return legacy_path

        return configured_path

    # === Интернет ===
    def _check_internet(self):
        try:
            requests.get("https://www.google.com", timeout=3)
            return True
        except requests.RequestException:
            return False

    # === Проверяем модели ===
    def _ensure_vosk_models(self):
        for lang, path in self.vosk_models.items():
            if not self._is_vosk_model_ready(path) and self.online_available:
                print(f"Downloading Vosk model for {lang.upper()}...")
                try:
                    self._download_model(self.vosk_urls[lang])
                except Exception as e:
                    self.logger.warning(f"Не удалось скачать Vosk-модель {lang.upper()}: {e}")
            elif not self._is_vosk_model_ready(path):
                self.logger.warning(f"Vosk-модель {lang.upper()} не найдена или повреждена: {path}")

    def _is_vosk_model_ready(self, path: Path) -> bool:
        required = [
            path / "am" / "final.mdl",
            path / "conf" / "model.conf",
            path / "graph" / "HCLr.fst",
            path / "graph" / "Gr.fst",
        ]
        return path.exists() and all(item.exists() for item in required)

    def _download_model(self, url):
        tmp_file = Path(tempfile.gettempdir()) / "vosk_model.zip"
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0))
            with open(tmp_file, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as bar:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

        with zipfile.ZipFile(tmp_file, "r") as zf:
            zf.extractall(self.models_dir)
        os.remove(tmp_file)
        print("Vosk model installed.")

    # === Загружаем модели Vosk ===
    def _load_vosk_recognizers(self):
        recs = {}
        for lang, path in self.vosk_models.items():
            if self._is_vosk_model_ready(path):
                try:
                    model = Model(str(path))
                    recs[lang] = KaldiRecognizer(model, self.sample_rate)
                    self.logger.info(f"Vosk-модель {lang.upper()} загружена: {path}")
                except Exception as e:
                    self.logger.warning(f"Ошибка загрузки Vosk-модели {lang.upper()}: {e}")
        return recs

    # === Постоянный аудиопоток ===
    def _start_microphone_stream(self):
        if self.stream:
            try:
                if getattr(self.stream, "active", False):
                    return True
            except Exception:
                pass
            self.stop()

        def callback(indata, frames, time_, status):
            if status:
                self.logger.warning(f"[AUDIO WARNING] {status}")
            self.audio_queue.put(bytes(indata))

        try:
            print("Microphone stream is active.")
            self.stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.blocksize,
                dtype="int16",
                channels=1,
                callback=callback,
            )
            self.stream.start()
            return True
        except Exception as e:
            self.stream = None
            self.logger.error(f"Не удалось открыть микрофон: {e}")
            return False

    # === Главный метод ===
    def listen_text(self):
        """
        Слушает микрофон постоянно и возвращает текст, когда распознана фраза.
        """
        try:
            if self.mode == "online":
                return self._listen_online()
            return self._listen_offline()
        except Exception as e:
            self.logger.warning(f"Сбой распознавания, пытаюсь продолжить: {e}")
            self.recover()
            return "", self.default_lang

    def recover(self):
        """Мягко восстанавливает микрофонный поток и сбрасывает буферы."""
        self.stop()
        if self.mode == "offline":
            self._start_microphone_stream()

    # === Онлайн (Google) ===
    def _listen_online(self):
        print("(Online) Listening...")

        samplerate = self.sample_rate
        duration = int(self.config.get("recognition", {}).get("online_listen_seconds", 5))

        try:
            with sd.InputStream(samplerate=samplerate, channels=1, dtype="int16") as stream:
                audio_data = stream.read(int(samplerate * duration))[0]
        except Exception as e:
            self.logger.warning(f"Ошибка онлайн аудио-потока: {e}")
            return "", self.default_lang

        # Конвертация в wav и Google Speech
        wav_bytes = io.BytesIO()
        wav_write(wav_bytes, samplerate, audio_data)
        wav_bytes.seek(0)

        r = sr.Recognizer()
        with sr.AudioFile(wav_bytes) as source:
            audio = r.record(source)

        lang_code = self.language_map.get(self.default_lang, "ru")
        try:
            text = r.recognize_google(audio, language=lang_code)
            print(f"Recognized ({self.default_lang.upper()}): {text}")
            return text, self.default_lang
        except sr.UnknownValueError:
            print("Speech was not recognized.")
            return "", self.default_lang
        except sr.RequestError:
            self.logger.warning("Интернет или сервис распознавания недоступен.")
            if self.auto_switch_mode:
                self.mode = "offline"
                self._start_microphone_stream()
                return self._listen_offline()
            return "", self.default_lang

    # === Офлайн (Vosk) ===
    def _listen_offline(self):
        if not self._start_microphone_stream():
            time.sleep(0.5)
            return "", self.default_lang

        lang = self.default_lang
        recognizer = self.vosk_recognizers.get(lang)
        if not recognizer:
            self.logger.warning(f"Нет Vosk-модели для {lang.upper()}")
            if self.auto_switch_mode and self._check_internet():
                self.mode = "online"
                return self._listen_online()
            time.sleep(1.0)
            return "", lang

        started_at = time.monotonic()
        last_partial = ""
        while time.monotonic() - started_at < self.offline_listen_timeout:
            try:
                data = self.audio_queue.get(timeout=self.audio_queue_timeout)
            except queue.Empty:
                continue

            try:
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    recognizer.Reset()
                    if text:
                        print(f"Recognized: {text}")
                        return text, lang
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                    if partial:
                        last_partial = partial
            except Exception as e:
                self.logger.warning(f"Ошибка Vosk-распознавания: {e}")
                recognizer.Reset()
                return "", lang

        if last_partial:
            recognizer.Reset()
            print(f"Recognized partial: {last_partial}")
            return last_partial, lang
        return "", lang

    # === Сбор данных ===
    def _collect_audio(self, seconds=5):
        """Собирает аудио блоки за указанное время."""
        frames = []
        duration = seconds
        while True:
            try:
                frames.append(self.audio_queue.get(timeout=seconds))
                if len(frames) * 0.5 > duration:  # приблизительно seconds
                    break
            except queue.Empty:
                break
        if not frames:
            return None
        import numpy as np
        return np.frombuffer(b"".join(frames), dtype="int16")

    def stop(self):
        """Останавливает микрофон и очищает очередь."""
        try:
            if self.stream:
                try:
                    self.stream.stop()
                finally:
                    self.stream.close()
                self.stream = None
            with self.audio_queue.mutex:
                self.audio_queue.queue.clear()
            print("Recognition stopped.")
        except Exception as e:
            print(f"Recognizer stop error: {e}")

    def set_language(self, lang: str):
        """Меняет язык распознавания во время работы."""
        if lang not in self.language_map:
            print(f"Language {lang} is not supported.")
            return False

        self.default_lang = lang
        if self.mode == "offline" and lang not in self.vosk_recognizers:
            print(f"No Vosk model for {lang.upper()}")
            return False

        print(f"Recognition language changed to: {lang.upper()}")
        return True
