import requests
import sounddevice as sd
from pathlib import Path
import logging

from src.core.config import resolve_runtime_path

# --- Опциональные импорты ---
try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import torch
except ImportError:
    torch = None


class HybridTTS:
    """
    💬 Гибридный синтезатор речи для офлайн/онлайн режимов.
    Поддерживает Silero (если torch установлен) и pyttsx3.
    Может воспроизводить кастомные аудиофайлы из media/audios.
    """

    def __init__(self, config: dict = None):
        self.logger = logging.getLogger("HybridTTS")
        self.config = config or {}
        self.voice_enabled = self.config.get("voice_enabled", True)
        self.default_lang = self.config.get("assistant", {}).get("default_language", "ru")

        # 🧠 Безопасная инициализация torch
        self.device = "cuda" if (
            torch is not None
            and torch.cuda.is_available()
            and self.config.get("silero", {}).get("use_cuda", True)
        ) else "cpu"

        # Пути
        self.models_dir = self._resolve_project_path(
            self.config.get("paths", {}).get("tts_models", "data/models/tts")
        )
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir = self._resolve_project_path("data/media/audios")

        # Поддерживаемые языки
        self.supported_langs = {
            "ru": "v3_1_ru",
            "en": "v3_en",
        }

        # Голоса Silero
        self.silero_speakers = {
            "ru": ["aidar", "baya", "kseniya", "xenia", "eugene"],
            "en": ["en_0", "en_1", "en_2"],
        }

        # Текущие параметры
        self.current_lang = self.default_lang
        self.current_speaker = self.config.get("voice_speaker", "aidar")
        self.current_engine = self.config.get("voice_engine", "silero")
        self.model = None

        # pyttsx3 готов
        self.engine = None
        if pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", self.config.get("voice_speed", 160))
                self.engine.setProperty("volume", self.config.get("voice_volume", 1.0))
                gender = self.config.get("voice_gender", "female").lower()
                for v in self.engine.getProperty("voices"):
                    if gender in v.name.lower():
                        self.engine.setProperty("voice", v.id)
                        break
            except Exception as e:
                self.logger.warning(f"Ошибка инициализации pyttsx3 ({e}). Ответы будут выводиться текстом.")
                self.engine = None

        # Загрузка Silero только если он выбран в настройках.
        if self.current_engine == "silero" and torch is not None:
            try:
                self._prepare_silero_model(self.current_lang)
            except Exception as e:
                self._switch_to_pyttsx3(f"Ошибка загрузки Torch/Silero ({e}).")
        elif self.current_engine == "silero" and torch is None:
            self._switch_to_pyttsx3("Torch не установлен.")
        else:
            self.logger.info(f"Используется TTS-движок: {self.current_engine}.")

    def _resolve_project_path(self, path_value: str | Path) -> Path:
        return resolve_runtime_path(path_value, base="bundle")
    # ----------------------------- #
    # 🔹 Silero Model Management
    # ----------------------------- #

    def _model_path(self, lang: str) -> Path:
        model_name = self.supported_langs.get(lang, self.supported_langs["ru"])
        return self.models_dir / f"{model_name}.pt"

    def _is_model_file_ready(self, model_path: Path) -> bool:
        try:
            return model_path.exists() and model_path.stat().st_size > 0
        except OSError:
            return False

    def _prepare_silero_model(self, lang: str):
        model_path = self._model_path(lang)
        if not self._is_model_file_ready(model_path):
            if self.config.get("offline_mode", True):
                raise RuntimeError(f"локальная модель отсутствует или пуста: {model_path}")
            self._download_model(lang, model_path)
        if not self._is_model_file_ready(model_path):
            raise RuntimeError(f"модель не готова: {model_path}")
        self._load_model(lang, model_path)

    def _ensure_models_exist(self):
        """Проверяет и скачивает Silero модели при необходимости"""
        for lang in self.supported_langs:
            model_path = self._model_path(lang)
            if not self._is_model_file_ready(model_path) and not self.config.get("offline_mode", True):
                self._download_model(lang, model_path)

    def _download_model(self, lang: str, model_path: Path):
        model_name = model_path.stem
        url = f"https://models.silero.ai/models/tts/{lang}/{model_name}.pt"
        temp_path = model_path.with_suffix(".pt.download")
        self.logger.info(f"Скачиваю Silero модель ({model_name}) для {lang.upper()}...")
        try:
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                model_path.parent.mkdir(parents=True, exist_ok=True)
                with open(temp_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            file.write(chunk)
            if not self._is_model_file_ready(temp_path):
                raise RuntimeError("скачанный файл пуст")
            temp_path.replace(model_path)
            self.logger.info(f"Модель {model_name} установлена.")
        except Exception as e:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            self.logger.warning(f"Ошибка скачивания {model_name}: {e}")

    def _load_model(self, lang: str, model_path: Path | None = None):
        """Загружает модель Silero для нужного языка"""
        if torch is None:
            return
        try:
            model_path = model_path or self._model_path(lang)
            importer = torch.package.PackageImporter(str(model_path))
            self.model = importer.load_pickle("tts_models", "model")
            self.model.to(self.device)
            self.logger.info(f"Silero TTS загружен для языка {lang.upper()}.")        
        except Exception as e:
            self._switch_to_pyttsx3(f"Ошибка загрузки Silero ({lang}): {e}")

    def _switch_to_pyttsx3(self, reason: str):
        self.logger.warning(f"{reason} Используется pyttsx3.")
        self.model = None
        self.current_engine = "pyttsx3"

    # ----------------------------- #
    # 🔹 Speech & Playback
    # ----------------------------- #

    def speak(self, text: str, lang: str = None, speaker: str = None, engine: str = None):
        """Произносит текст с помощью Silero или pyttsx3"""
        if not text or not self.voice_enabled:
            self.logger.debug(f"Текст пустой или голос отключён: '{text}'")
            return

        lang = lang or self.current_lang
        speaker = speaker or self.current_speaker
        engine = engine or self.current_engine

        # Silero
        if engine == "silero" and self.model and torch is not None:
            try:
                speakers = self.silero_speakers.get(lang) or self.silero_speakers.get("ru", [])
                if speakers and speaker not in speakers:
                    speaker = speakers[0]
                self.logger.info(f"[SILERO] [{lang}:{speaker}] {text}")
                audio = self.model.apply_tts(
                    text=text,
                    speaker=speaker,
                    sample_rate=self.config.get("silero", {}).get("sample_rate", 48000),
                    put_accent=True,
                    put_yo=True,
                )
                sd.play(audio, self.config.get("silero", {}).get("sample_rate", 48000))
                sd.wait()
                return
            except Exception as e:
                self.logger.warning(f"[Silero error] {e}")
                self._switch_to_pyttsx3("Silero недоступен во время озвучивания.")
                engine = self.current_engine

        # pyttsx3 fallback
        if self.engine and engine == "pyttsx3":
            self.logger.info(f"[pyttsx3] {text}")
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                self.logger.warning(f"[TTS error] {e}")

        # Если нет ни одного TTS
        elif not self.engine:
            print(f"💭 {text}")

    def play_audio_file(self, file_path: Path):
        """Проигрывает WAV-файл."""
        if not file_path.exists():
            print(f"⚠️ Аудиофайл не найден: {file_path}")
            return
        if sf is None:
            print(f"⚠️ Для воспроизведения нужен модуль soundfile.")
            return
        try:
            data, fs = sf.read(str(file_path))
            sd.play(data, fs)
            sd.wait()
        except Exception as e:
            print(f"⚠️ Ошибка при воспроизведении {file_path}: {e}")

    def play_audio(self, audio_file: str):
        """
        Алиас для play_audio_file для совместимости.
        Проигрывает аудиофайл из media/audios.
        """
        if isinstance(audio_file, str):
            file_path = self.media_dir / audio_file
        else:
            file_path = audio_file
        return self.play_audio_file(file_path)

    # ----------------------------- #
    # 🔹 Settings
    # ----------------------------- #

    def set_language(self, lang: str):
        if lang not in self.supported_langs:
            print(f"⚠️ Язык {lang} не поддерживается.")
            return
        self.current_lang = lang
        if self.current_engine == "silero" and torch:
            try:
                self._prepare_silero_model(lang)
            except Exception as e:
                self._switch_to_pyttsx3(f"Ошибка переключения языка Silero ({e}).")

    def set_voice(self, speaker: str):
        self.current_speaker = speaker
        print(f"🎤 Голос изменён на: {speaker}")

    def set_engine(self, engine: str):
        if engine not in ("silero", "pyttsx3"):
            print(f"⚠️ Неизвестный движок: {engine}")
            return
        self.current_engine = engine
        if engine == "silero" and torch:
            try:
                self._prepare_silero_model(self.current_lang)
            except Exception as e:
                self._switch_to_pyttsx3(f"Ошибка включения Silero ({e}).")
        elif engine == "silero":
            self._switch_to_pyttsx3("Torch не установлен.")
        print(f"⚙️ Движок изменён на: {self.current_engine}")

    def test(self):
        """Тест всех языков и режимов"""
        self.speak("Привет, я офлайн-ассистент!", "ru")
        self.speak("Hello, I can speak English!", "en")
