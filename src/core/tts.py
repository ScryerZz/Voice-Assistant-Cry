import requests
import sounddevice as sd
from pathlib import Path
import logging

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
        self.models_dir = Path("data/models/tts")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir = Path("data/media/audios")

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
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.config.get("voice_speed", 160))
            self.engine.setProperty("volume", self.config.get("voice_volume", 1.0))
            gender = self.config.get("voice_gender", "female").lower()
            for v in self.engine.getProperty("voices"):
                if gender in v.name.lower():
                    self.engine.setProperty("voice", v.id)
                    break

        # Загрузка Silero, если torch установлен
        if torch is not None:
            try:
                self._ensure_models_exist()
                self._load_model(self.current_lang)
            except Exception as e:
                self.logger.warning(f"Ошибка загрузки Torch/Silero ({e}). Используется pyttsx3.")                
                self.model = None
                self.current_engine = "pyttsx3"
        else:
            self.logger.info("Torch не установлен — используется pyttsx3.")
    # ----------------------------- #
    # 🔹 Silero Model Management
    # ----------------------------- #

    def _ensure_models_exist(self):
        """Проверяет и скачивает Silero модели при необходимости"""
        base_url = "https://models.silero.ai/models/tts"
        for lang, model_name in self.supported_langs.items():
            model_path = self.models_dir / f"{model_name}.pt"
            if not model_path.exists():
                self.logger.info(f"Скачиваю Silero модель ({model_name}) для {lang.upper()}...")                
                try:
                    url = f"{base_url}/{lang}/{model_name}.pt"
                    r = requests.get(url, stream=True, timeout=20)
                    with open(model_path, "wb") as f:
                        f.write(r.content)
                    self.logger.info(f"Модель {model_name} установлена.")                
                except Exception as e:
                    self.logger.warning(f"Ошибка скачивания {model_name}: {e}")

    def _load_model(self, lang: str):
        """Загружает модель Silero для нужного языка"""
        if torch is None:
            return
        try:
            model_name = self.supported_langs.get(lang, "v3_1_ru")
            self.model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language=lang,
                speaker=model_name,
            )
            self.model.to(self.device)
            self.logger.info(f"Silero TTS загружен для языка {lang.upper()}.")        
        except Exception as e:
            self.logger.warning(f"Ошибка загрузки Silero ({lang}): {e}")            
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
                if speaker not in self.silero_speakers.get(lang, []):
                    speaker = self.silero_speakers[lang][0]
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
                engine = "pyttsx3"

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
        if torch:
            self._load_model(lang)

    def set_voice(self, speaker: str):
        self.current_speaker = speaker
        print(f"🎤 Голос изменён на: {speaker}")

    def set_engine(self, engine: str):
        if engine not in ("silero", "pyttsx3"):
            print(f"⚠️ Неизвестный движок: {engine}")
            return
        self.current_engine = engine
        print(f"⚙️ Движок изменён на: {engine}")

    def test(self):
        """Тест всех языков и режимов"""
        self.speak("Привет, я офлайн-ассистент!", "ru")
        self.speak("Hello, I can speak English!", "en")
