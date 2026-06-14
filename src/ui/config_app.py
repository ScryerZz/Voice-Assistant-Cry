from __future__ import annotations

import ctypes
import importlib.util
import signal
import threading
import tkinter as tk
import tkinter.font as tkfont
import subprocess
import sys
import re
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from shutil import copy2
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable

import yaml

from src.core.autostart import apply_startup_config, is_launch_on_login_enabled
from src.core.config import BASE_DIR, EXECUTABLE_DIR, IS_FROZEN, PROJECT_ROOT, get_settings, resolve_runtime_path
from src.core.executor import Executor
from src.core.logs import clear_log, get_log_file, read_recent_log_lines
from src.core.runtime_control import is_voice_listening_enabled, set_voice_listening_enabled
from src.core.skill_manager import SkillManager
from src.core.storage import AssistantStorage
from src.core.support import (
    apply_assistant_profile,
    build_crash_summary,
    build_diagnostic_report,
    capture_assistant_profile,
    clear_config_secrets,
    format_health_snapshot,
    make_profile_key,
    secret_status_rows,
    write_diagnostic_report,
)
from src.core import tts as tts_module
from src.ui.tray import TrayController

COLORS = {
    "bg": "#eef3fb",
    "surface": "#ffffff",
    "surface_alt": "#f7faff",
    "glass": "#ffffff",
    "line": "#dbe4f2",
    "text": "#111827",
    "muted": "#667085",
    "primary": "#007aff",
    "primary_dark": "#005ecb",
    "success": "#34c759",
    "warning": "#ff9f0a",
    "danger": "#ff3b30",
    "chat_bg": "#f7faff",
    "input_bg": "#ffffff",
    "bubble_user": "#007aff",
    "bubble_assistant": "#ffffff",
    "bubble_voice": "#fff4df",
    "bubble_system": "#eef2f7",
}


def enable_high_dpi_awareness():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def set_initial_window_size(
    window: tk.Toplevel | tk.Tk,
    preferred_width: int,
    preferred_height: int,
    min_width: int,
    min_height: int,
    top_margin: int = 48,
) -> None:
    screen_width = max(1024, int(window.winfo_screenwidth()))
    screen_height = max(720, int(window.winfo_screenheight()))
    usable_width = max(min_width, screen_width - 96)
    usable_height = max(min_height, screen_height - 120)
    width = min(preferred_width, usable_width)
    height = min(preferred_height, usable_height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, min(top_margin, (screen_height - height) // 3))
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.minsize(min(min_width, width), min(min_height, height))


def _csv_to_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _list_to_csv(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value or "")


LANGUAGE_LABELS = {
    "ru": "Русский",
    "en": "Английский",
}
LANGUAGE_CODES = {label: code for code, label in LANGUAGE_LABELS.items()}

MODE_LABELS = {
    "offline": "Офлайн",
    "online": "Онлайн",
    "hybrid": "Гибридный",
}
MODE_CODES = {label: code for code, label in MODE_LABELS.items()}

VOICE_GENDER_LABELS = {
    "female": "Женский",
    "male": "Мужской",
}
VOICE_GENDER_CODES = {label: code for code, label in VOICE_GENDER_LABELS.items()}

PERSONALITY_LABELS = {
    "friendly": "Дружелюбный",
    "professional": "Профессиональный",
    "funny": "Весёлый",
}
PERSONALITY_CODES = {label: code for code, label in PERSONALITY_LABELS.items()}

HISTORY_SOURCE_LABELS = {
    "all": "Все",
    "voice": "Голос",
    "chat": "Чат",
}
HISTORY_SOURCE_CODES = {label: code for code, label in HISTORY_SOURCE_LABELS.items()}

HISTORY_STATUS_LABELS = {
    "all": "Все",
    "matched": "Выполнено",
    "no_match": "Не распознано",
    "dangerous_low_confidence": "Низкая уверенность",
    "confirmation_required": "Требуется подтверждение",
    "confirmed": "Подтверждено",
    "confirmation_rejected": "Отклонено",
    "confirmation_cancelled": "Отменено",
    "confirmation_timeout": "Истекло ожидание",
    "ai_fallback": "Ответ ИИ",
    "error": "Ошибка",
    "unknown": "Неизвестно",
}
HISTORY_STATUS_CODES = {label: code for code, label in HISTORY_STATUS_LABELS.items()}


def _label_from_mapping(value: Any, labels: dict[str, str]) -> str:
    key = str(value or "").strip()
    return labels.get(key, key)


def _code_from_mapping(value: Any, codes: dict[str, str]) -> str:
    text = str(value or "").strip()
    return codes.get(text, text)


def _language_label(value: Any) -> str:
    return _label_from_mapping(value, LANGUAGE_LABELS)


def _language_code(value: Any) -> str:
    return _code_from_mapping(value, LANGUAGE_CODES)


def _mode_label(value: Any) -> str:
    return _label_from_mapping(value, MODE_LABELS)


def _mode_code(value: Any) -> str:
    return _code_from_mapping(value, MODE_CODES)


def _voice_gender_label(value: Any) -> str:
    return _label_from_mapping(value, VOICE_GENDER_LABELS)


def _voice_gender_code(value: Any) -> str:
    return _code_from_mapping(value, VOICE_GENDER_CODES)


def _personality_label(value: Any) -> str:
    return _label_from_mapping(value, PERSONALITY_LABELS)


def _personality_code(value: Any) -> str:
    return _code_from_mapping(value, PERSONALITY_CODES)


def _history_source_label(value: Any) -> str:
    return _label_from_mapping(value, HISTORY_SOURCE_LABELS)


def _history_source_code(value: Any) -> str:
    return _code_from_mapping(value, HISTORY_SOURCE_CODES)


def _history_status_label(value: Any) -> str:
    return _label_from_mapping(value, HISTORY_STATUS_LABELS)


def _history_status_code(value: Any) -> str:
    return _code_from_mapping(value, HISTORY_STATUS_CODES)


class ConfigField:
    def __init__(
        self,
        path: tuple[str, ...],
        label: str,
        variable: tk.Variable,
        reader: Callable[[Any], Any] = lambda value: value,
        writer: Callable[[Any], Any] = lambda value: value,
    ):
        self.path = path
        self.label = label
        self.variable = variable
        self.reader = reader
        self.writer = writer

    def load(self, config: dict):
        value = config
        for key in self.path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        self.variable.set(self.reader(value))

    def dump(self) -> Any:
        return self.writer(self.variable.get())


class ScrollableFrame(ttk.Frame):
    def __init__(self, master: tk.Widget):
        super().__init__(master)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, background=COLORS["bg"])
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = ttk.Frame(self.canvas)

        self.content.bind(
            "<Configure>",
            lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", self._resize_content)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _resize_content(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)


class GradientFrame(tk.Canvas):
    def __init__(self, master: tk.Widget, color1: str, color2: str, **kwargs):
        super().__init__(master, highlightthickness=0, bd=0, **kwargs)
        self.color1 = color1
        self.color2 = color2
        self.bind("<Configure>", self._draw_gradient)

    def _draw_gradient(self, event=None):
        self.delete("gradient")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 0 or height <= 0:
            return
        r1, g1, b1 = self.winfo_rgb(self.color1)
        r2, g2, b2 = self.winfo_rgb(self.color2)
        r_ratio = (r2 - r1) / max(height, 1)
        g_ratio = (g2 - g1) / max(height, 1)
        b_ratio = (b2 - b1) / max(height, 1)
        for y in range(height):
            nr = int(r1 + (r_ratio * y)) >> 8
            ng = int(g1 + (g_ratio * y)) >> 8
            nb = int(b1 + (b_ratio * y)) >> 8
            self.create_line(0, y, width, y, tags=("gradient",), fill=f"#{nr:02x}{ng:02x}{nb:02x}")
        self.lower("gradient")


class RoundedPanel(tk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        fill: str = COLORS["glass"],
        radius: int = 24,
        padding: int = 16,
        outline: str = COLORS["line"],
        background: str = COLORS["bg"],
        min_width: int = 0,
        min_height: int = 0,
    ):
        super().__init__(master, bg=background, highlightthickness=0, bd=0)
        self.fill = fill
        self.radius = radius
        self.padding = padding
        self.outline = outline
        self.min_width = min_width
        self.min_height = min_height
        self.canvas = tk.Canvas(
            self,
            bg=background,
            highlightthickness=0,
            bd=0,
            width=max(1, min_width),
            height=max(1, min_height),
        )
        self.canvas.pack(fill="both", expand=True)
        self.content = tk.Frame(self.canvas, bg=fill, highlightthickness=0, bd=0)
        self.window_id = self.canvas.create_window(
            padding,
            padding,
            window=self.content,
            anchor="nw",
        )
        self.canvas.bind("<Configure>", self._draw)
        self.content.bind("<Configure>", self._resize_to_content)

    def _resize_to_content(self, _event=None):
        width = max(self.min_width, self.content.winfo_reqwidth() + self.padding * 2)
        height = max(self.min_height, self.content.winfo_reqheight() + self.padding * 2)
        self.configure(width=width, height=height)
        self.canvas.configure(width=width, height=height)

    def _draw(self, event):
        width = max(event.width, 2)
        height = max(event.height, 2)
        self.canvas.delete("panel")
        self._rounded_rect(
            1,
            1,
            width - 2,
            height - 2,
            radius=min(self.radius, width // 2, height // 2),
            fill=self.fill,
            outline=self.outline,
        )
        self.canvas.tag_lower("panel")
        self.canvas.itemconfigure(
            self.window_id,
            width=max(1, width - self.padding * 2),
            height=max(1, height - self.padding * 2),
        )

    def _rounded_rect(self, x1, y1, x2, y2, radius, fill, outline):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        self.canvas.create_polygon(
            points,
            fill=fill,
            outline=outline,
            smooth=True,
            splinesteps=18,
            tags=("panel",),
        )


class RoundedButton(tk.Canvas):
    VARIANTS = {
        "default": {"fill": COLORS["glass"], "hover": "#eef6ff", "text": COLORS["text"], "outline": COLORS["line"]},
        "accent": {"fill": COLORS["primary"], "hover": "#2990ff", "text": "#ffffff", "outline": COLORS["primary"]},
        "danger": {"fill": "#fff0ef", "hover": "#fff6f5", "text": COLORS["danger"], "outline": "#ffd9d6"},
        "nav": {"fill": COLORS["glass"], "hover": "#eef6ff", "text": COLORS["text"], "outline": COLORS["glass"]},
        "nav_selected": {"fill": "#e8f2ff", "hover": "#e8f2ff", "text": COLORS["primary"], "outline": "#cfe3ff"},
    }

    def __init__(
        self,
        master: tk.Widget,
        text: str,
        command: Callable[[], None],
        variant: str = "default",
        width: int | None = None,
        height: int = 38,
        radius: int = 19,
        background: str = COLORS["bg"],
    ):
        self.text = text
        self.command = command
        self.variant = variant
        self.radius = radius
        self.enabled = True
        self.hover = False
        self.selected = False
        font = tkfont.Font(name="AppSmallBold" if variant in {"accent", "danger"} else "AppBody", exists=True)
        measured_width = font.measure(text) + 34
        super().__init__(
            master,
            width=width or max(96, measured_width),
            height=height,
            highlightthickness=0,
            bd=0,
            background=background,
            cursor="hand2",
        )
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.draw()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.draw()

    def set_selected(self, selected: bool):
        self.selected = selected
        self.draw()

    def _on_enter(self, _event):
        self.hover = True
        self.draw()

    def _on_leave(self, _event):
        self.hover = False
        self.draw()

    def _on_click(self, _event):
        if self.enabled:
            self.command()

    def draw(self):
        self.delete("all")
        variant = "nav_selected" if self.variant == "nav" and self.selected else self.variant
        palette = self.VARIANTS.get(variant, self.VARIANTS["default"])
        fill = palette["hover"] if self.hover and self.enabled else palette["fill"]
        text_color = palette["text"] if self.enabled else "#98a2b3"
        outline = palette["outline"] if self.enabled else "#e5eaf2"
        width = int(self["width"])
        height = int(self["height"])
        self._rounded_rect(1, 1, width - 1, height - 1, self.radius, fill, outline)
        font_name = "AppSmallBold" if variant in {"accent", "danger", "nav_selected"} else "AppBody"
        self.create_text(
            width // 2,
            height // 2,
            text=self.text,
            fill=text_color,
            font=font_name,
        )

    def _rounded_rect(self, x1, y1, x2, y2, radius, fill, outline):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        self.create_polygon(points, fill=fill, outline=outline, smooth=True, splinesteps=18)


class IOSToggle(tk.Canvas):
    def __init__(self, master: tk.Widget, command: Callable[[], None], width: int = 52, height: int = 30):
        super().__init__(master, width=width, height=height, highlightthickness=0, bd=0, background=COLORS["bg"])
        self.command = command
        self.enabled = True
        self.bind("<Button-1>", lambda _event: self.command())
        self.configure(cursor="hand2")
        self.draw(True)

    def draw(self, enabled: bool):
        self.enabled = enabled
        self.delete("all")
        track = COLORS["success"] if enabled else "#c8d0dc"
        knob_x = 37 if enabled else 15
        self.create_oval(1, 1, 29, 29, fill=track, outline=track)
        self.create_oval(23, 1, 51, 29, fill=track, outline=track)
        self.create_rectangle(15, 1, 37, 29, fill=track, outline=track)
        self.create_oval(knob_x - 12, 3, knob_x + 12, 27, fill="#ffffff", outline="#ffffff")


class ConfigApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=16)
        self.master = master
        self.settings = get_settings()
        self.fields: list[ConfigField] = []
        self.assistant_process: subprocess.Popen | None = None
        self.assistant_output_handle = None
        self.log_window: LogWindow | None = None
        self.chat_storage: AssistantStorage | None = None
        self.chat_skills: SkillManager | None = None
        self.chat_executor: Executor | None = None
        self.last_voice_history_id = 0
        self.nav_buttons: list[tuple[tk.Widget, RoundedButton]] = []
        self.tray = TrayController(self.master, self)
        self.start_minimized_requested = "--minimized" in sys.argv

        self.master.title("Голосовой ассистент Cry")
        set_initial_window_size(self.master, 1500, 930, 1280, 800)
        self.master.configure(background=COLORS["bg"])
        self.master.option_add("*tearOff", False)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self._setup_style()
        self._build()
        self.load_config()
        self._configure_tray()
        self._select_tab(self.home_tab)
        self._poll_assistant_process()
        self._poll_voice_history()
        if not self.settings.get("first_run_completed", default=False):
            self.master.after(300, self.open_first_run_wizard)
        else:
            self._schedule_startup_behaviour()

    def _setup_style(self):
        self._setup_fonts()
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font="AppBody", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Surface.TFrame", background=COLORS["surface"], borderwidth=1, relief="solid")
        style.configure("Glass.TFrame", background=COLORS["glass"], borderwidth=1, relief="solid")
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("Surface.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("HeaderInner.TFrame", background=COLORS["glass"], borderwidth=0, relief="flat")
        style.configure("Card.TFrame", background=COLORS["surface"], borderwidth=1, relief="solid")
        style.configure("CardTitle.TLabel", font="AppSmallBold", background=COLORS["surface"], foreground=COLORS["muted"])
        style.configure("CardValue.TLabel", font="AppMetric", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("CardHint.TLabel", font="AppSmall", background=COLORS["surface"], foreground=COLORS["muted"])
        style.configure("Title.TLabel", font="AppTitle", background=COLORS["bg"])
        style.configure("HeaderTitle.TLabel", font="AppTitle", background=COLORS["glass"])
        style.configure("HeaderSubtitle.TLabel", font="AppSmall", foreground=COLORS["muted"], background=COLORS["glass"])
        style.configure("Subtitle.TLabel", font="AppSmall", foreground=COLORS["muted"], background=COLORS["bg"])
        style.configure("Section.TLabel", font="AppSection", background=COLORS["bg"])
        style.configure("PanelSection.TLabel", font="AppSection", background=COLORS["glass"], foreground=COLORS["text"])
        style.configure("Hint.TLabel", foreground=COLORS["muted"], background=COLORS["bg"])
        style.configure("Pill.TLabel", padding=(10, 4), font="AppSmallBold")
        style.configure("Running.Pill.TLabel", background="#e6f4ea", foreground=COLORS["success"], padding=(10, 4))
        style.configure("Stopped.Pill.TLabel", background="#fce8e6", foreground=COLORS["danger"], padding=(10, 4))
        style.configure("VoiceOn.Pill.TLabel", background="#e8f0fe", foreground=COLORS["primary"], padding=(10, 4))
        style.configure("VoiceOff.Pill.TLabel", background="#fef7e0", foreground=COLORS["warning"], padding=(10, 4))
        style.configure(
            "TButton",
            padding=(14, 8),
            relief="flat",
            borderwidth=0,
            background=COLORS["glass"],
            foreground=COLORS["text"],
            focuscolor=COLORS["glass"],
        )
        style.map(
            "TButton",
            background=[("pressed", "#dcecff"), ("active", "#eef6ff"), ("disabled", "#eef2f7")],
            foreground=[("disabled", "#98a2b3")],
        )
        style.configure(
            "Accent.TButton",
            padding=(16, 9),
            relief="flat",
            borderwidth=0,
            background=COLORS["primary"],
            foreground="#ffffff",
            focuscolor=COLORS["primary"],
        )
        style.map("Accent.TButton", background=[("pressed", COLORS["primary_dark"]), ("active", "#2990ff")])
        style.configure(
            "Danger.TButton",
            padding=(14, 8),
            relief="flat",
            borderwidth=0,
            background="#fff0ef",
            foreground=COLORS["danger"],
            focuscolor="#fff0ef",
        )
        style.map("Danger.TButton", background=[("pressed", "#ffd9d6"), ("active", "#fff6f5")])
        style.configure(
            "TEntry",
            padding=(10, 7),
            relief="flat",
            borderwidth=1,
            fieldbackground=COLORS["input_bg"],
            foreground=COLORS["text"],
            insertcolor=COLORS["primary"],
        )
        style.configure("TCombobox", padding=(10, 7), fieldbackground=COLORS["input_bg"], foreground=COLORS["text"])
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0, tabmargins=(0, 4, 0, 0))
        style.configure("TNotebook.Tab", padding=(18, 9), font="AppBody", background=COLORS["surface_alt"], borderwidth=0)
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["surface"]), ("active", "#ffffff")],
            foreground=[("selected", COLORS["primary"]), ("active", COLORS["primary_dark"])],
        )
        style.configure("Hidden.TNotebook", background=COLORS["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure(
            "Hidden.TNotebook",
            background=COLORS["bg"],
            borderwidth=0,
            relief="flat",
            bordercolor=COLORS["bg"],
            lightcolor=COLORS["bg"],
            darkcolor=COLORS["bg"],
        )
        style.configure("Hidden.TNotebook.Tab", padding=(0, 0), borderwidth=0)
        try:
            style.layout("Hidden.TNotebook.Tab", [])
        except tk.TclError:
            pass
        style.configure(
            "Treeview",
            rowheight=32,
            borderwidth=0,
            relief="flat",
            font="AppSmall",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
        )
        style.configure("Treeview.Heading", font="AppSmallBold", background=COLORS["surface_alt"], foreground=COLORS["muted"])

    def _setup_fonts(self):
        family = self._preferred_font_family()
        dpi = max(96, int(self.master.winfo_fpixels("1i")))
        self.master.tk.call("tk", "scaling", dpi / 72)

        tkfont.nametofont("TkDefaultFont").configure(family=family, size=10)
        tkfont.nametofont("TkTextFont").configure(family=family, size=10)
        tkfont.nametofont("TkMenuFont").configure(family=family, size=10)
        tkfont.nametofont("TkHeadingFont").configure(family=family, size=10, weight="bold")
        tkfont.nametofont("TkCaptionFont").configure(family=family, size=9)
        tkfont.nametofont("TkSmallCaptionFont").configure(family=family, size=9)

        self.master.option_add("*Font", "AppBody")
        self.fonts = {
            "AppBody": tkfont.Font(name="AppBody", family=family, size=10),
            "AppSmall": tkfont.Font(name="AppSmall", family=family, size=9),
            "AppSmallBold": tkfont.Font(name="AppSmallBold", family=family, size=9, weight="bold"),
            "AppSection": tkfont.Font(name="AppSection", family=family, size=11, weight="bold"),
            "AppTitle": tkfont.Font(name="AppTitle", family=family, size=20, weight="bold"),
            "AppMetric": tkfont.Font(name="AppMetric", family=family, size=17, weight="bold"),
            "AppChat": tkfont.Font(name="AppChat", family=family, size=11),
            "AppChatLabel": tkfont.Font(name="AppChatLabel", family=family, size=9, weight="bold"),
            "AppMono": tkfont.Font(name="AppMono", family="Cascadia Mono", size=10),
        }

    def _preferred_font_family(self) -> str:
        families = set(tkfont.families(self.master))
        for family in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"):
            if family in families:
                return family
        return "Arial"

    def _build(self):
        self.pack(fill="both", expand=True)

        header_panel = RoundedPanel(self, fill=COLORS["glass"], radius=28, padding=16)
        header_panel.pack(fill="x", pady=(0, 12))
        header = header_panel.content
        title_block = ttk.Frame(header, style="HeaderInner.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="Голосовой ассистент Cry", style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(title_block, text=str(self.settings.config_path), style="HeaderSubtitle.TLabel").pack(anchor="w", pady=(2, 0))

        status_block = ttk.Frame(header, style="HeaderInner.TFrame")
        status_block.pack(side="right")
        self.process_status_label = ttk.Label(status_block, text="Не запущен", style="Stopped.Pill.TLabel")
        self.process_status_label.pack(side="left", padx=(0, 8))
        self.voice_status_label = ttk.Label(status_block, text="Голос включен", style="VoiceOn.Pill.TLabel")
        self.voice_status_label.pack(side="left")

        actions_panel = RoundedPanel(self, fill=COLORS["glass"], radius=24, padding=12)
        actions_panel.pack(fill="x", pady=(0, 12))
        actions = actions_panel.content
        self.start_button = RoundedButton(
            actions,
            text="Запустить ассистента",
            command=self.start_assistant,
            variant="accent",
            width=214,
            background=COLORS["glass"],
        )
        self.start_button.pack(side="left")
        self.stop_button = RoundedButton(
            actions,
            text="Остановить",
            command=self.stop_assistant,
            variant="danger",
            width=136,
            background=COLORS["glass"],
        )
        self.stop_button.pack(side="left", padx=(8, 0))
        self.stop_button.set_enabled(False)
        RoundedButton(actions, text="Живой журнал", command=self.open_log_window, width=152, background=COLORS["glass"]).pack(
            side="left", padx=(8, 0)
        )
        RoundedButton(
            actions,
            text="Мастер первого запуска",
            command=self.open_first_run_wizard,
            width=226,
            background=COLORS["glass"],
        ).pack(side="left", padx=(8, 0))
        RoundedButton(actions, text="Перезагрузить", command=self.load_config, width=154, background=COLORS["glass"]).pack(
            side="right", padx=(8, 0)
        )
        RoundedButton(
            actions,
            text="Сохранить",
            command=self.save_config,
            variant="accent",
            width=132,
            background=COLORS["glass"],
        ).pack(side="right")

        workspace = ttk.Frame(self)
        workspace.pack(fill="both", expand=True)
        workspace.columnconfigure(0, weight=0, minsize=256)
        workspace.columnconfigure(1, weight=1)
        workspace.rowconfigure(0, weight=1)

        self.sidebar_panel = RoundedPanel(
            workspace,
            fill=COLORS["glass"],
            radius=28,
            padding=14,
            min_width=256,
            min_height=560,
        )
        self.sidebar_panel.grid(column=0, row=0, sticky="nsew", padx=(0, 12))

        content = ttk.Frame(workspace)
        content.grid(column=1, row=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(content, style="Hidden.TNotebook")
        self.notebook.grid(column=0, row=0, sticky="nsew")

        self._build_home_tab()
        self._build_chat_tab()
        self._build_status_tab()
        self._build_profiles_tab()
        self._build_voice_tab()
        self._build_assistant_tab()
        self._build_integrations_tab()
        self._build_safety_tab()
        self._build_apps_tab()
        self._build_paths_tab()
        self._build_commands_tab()
        self._build_notes_tab()
        self._build_reminders_tab()
        self._build_history_tab()
        self._build_diagnostics_tab()
        self._build_raw_tab()
        self._build_sidebar()
        self.notebook.bind("<<NotebookTabChanged>>", self._refresh_nav_selection)
        self.after_idle(self._refresh_rounded_panels)

    def _build_sidebar(self):
        sidebar = self.sidebar_panel.content
        sidebar.columnconfigure(0, weight=1)
        sidebar.grid_columnconfigure(0, minsize=224)

        tk.Label(
            sidebar,
            text="Голосовой ассистент Cry",
            font="AppSection",
            bg=COLORS["glass"],
            fg=COLORS["text"],
        ).grid(column=0, row=0, sticky="w", padx=4, pady=(0, 8))

        sections = (
            ("Работа", (("Главная", self.home_tab), ("Чат", self.chat_tab))),
            (
                "Контроль",
                (
                    ("Состояние", self.status_tab),
                    ("История", self.history_tab),
                    ("Команды", self.commands_tab),
                    ("Заметки", self.notes_tab),
                    ("Напоминания", self.reminders_tab),
                ),
            ),
            (
                "Настройки",
                (
                    ("Ассистент", self.assistant_tab),
                    ("Профили", self.profiles_tab),
                    ("Голос", self.voice_tab),
                    ("Интеграции", self.integrations_tab),
                    ("Безопасность", self.safety_tab),
                    ("Приложения", self.apps_tab),
                    ("Пути", self.paths_tab),
                ),
            ),
            ("Сервис", (("Диагностика", self.diagnostics_tab), ("Конфиг", self.raw_tab))),
        )

        row = 1
        for title, items in sections:
            row = self._add_nav_group(sidebar, row, title, items)
        self.sidebar_panel._resize_to_content()

    def _add_nav_group(self, parent: tk.Widget, row: int, title: str, items: tuple[tuple[str, tk.Widget], ...]) -> int:
        tk.Label(
            parent,
            text=title,
            font="AppSmallBold",
            bg=COLORS["glass"],
            fg=COLORS["muted"],
        ).grid(column=0, row=row, sticky="w", padx=4, pady=(4 if row > 1 else 0, 2))
        row += 1

        for label, tab in items:
            button = RoundedButton(
                parent,
                text=label,
                command=lambda target=tab: self._select_tab(target),
                variant="nav",
                width=224,
                height=28,
                radius=14,
                background=COLORS["glass"],
            )
            button.grid(column=0, row=row, sticky="ew", pady=(0, 2))
            self.nav_buttons.append((tab, button))
            row += 1
        return row

    def _select_tab(self, tab: tk.Widget):
        self.notebook.select(tab)
        self._refresh_nav_selection()
        self.after_idle(self._refresh_rounded_panels)

    def _refresh_nav_selection(self, _event=None):
        current = self.notebook.select()
        for tab, button in self.nav_buttons:
            button.set_selected(str(tab) == current)
        self.after_idle(self._refresh_rounded_panels)

    def _refresh_rounded_panels(self):
        for panel in self._iter_rounded_panels(self):
            panel._resize_to_content()

    def _iter_rounded_panels(self, widget: tk.Widget):
        for child in widget.winfo_children():
            if isinstance(child, RoundedPanel):
                yield child
            yield from self._iter_rounded_panels(child)

    def _build_home_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.home_tab = frame
        self.notebook.add(frame, text="Главная")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)

        hero_panel = RoundedPanel(frame, fill=COLORS["glass"], radius=28, padding=18)
        hero_panel.grid(column=0, row=0, columnspan=2, sticky="ew", pady=(0, 12))
        hero = hero_panel.content
        hero.columnconfigure(0, weight=1)
        ttk.Label(hero, text="Голосовой ассистент готов к работе", style="HeaderTitle.TLabel").grid(
            column=0, row=0, sticky="w"
        )
        ttk.Label(
            hero,
            text="Управляйте ассистентом голосом или текстом, проверяйте состояние и меняйте настройки без PowerShell.",
            style="HeaderSubtitle.TLabel",
            wraplength=760,
        ).grid(column=0, row=1, sticky="w", pady=(4, 0))
        RoundedButton(
            hero,
            text="Открыть чат",
            command=lambda: self._select_tab(self.chat_tab),
            variant="accent",
            width=138,
            background=COLORS["glass"],
        ).grid(
            column=1, row=0, rowspan=2, sticky="e", padx=(20, 0)
        )

        cards = ttk.Frame(frame)
        cards.grid(column=0, row=1, columnspan=2, sticky="ew", pady=(0, 12))
        for index in range(4):
            cards.columnconfigure(index, weight=1, uniform="home_cards")

        self.home_cards = {}
        for index, key in enumerate(("process", "voice", "mode", "history")):
            card_panel = RoundedPanel(cards, fill=COLORS["surface"], radius=22, padding=16)
            card_panel.grid(column=index, row=0, sticky="nsew", padx=(0 if index == 0 else 8, 0))
            card = card_panel.content
            title = ttk.Label(card, text="", style="CardTitle.TLabel")
            title.pack(anchor="w")
            value = ttk.Label(card, text="", style="CardValue.TLabel")
            value.pack(anchor="w", pady=(6, 2))
            hint = ttk.Label(card, text="", style="CardHint.TLabel", wraplength=180)
            hint.pack(anchor="w")
            self.home_cards[key] = (title, value, hint)

        left_panel = RoundedPanel(frame, fill=COLORS["glass"], radius=26, padding=14)
        left_panel.grid(column=0, row=2, sticky="nsew", padx=(0, 6))
        left = left_panel.content
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="Быстрые действия", style="PanelSection.TLabel").grid(column=0, row=0, sticky="w")
        ttk.Label(left, text="Самые частые операции собраны здесь.", style="HeaderSubtitle.TLabel").grid(
            column=0, row=1, sticky="w", pady=(2, 12)
        )
        quick_actions = (
            ("Запустить ассистента", self.start_assistant, "accent"),
            ("Остановить", self.stop_assistant, "danger"),
            ("Проверить проект", self.run_project_diagnostics, "default"),
            ("Живой журнал", self.open_log_window, "default"),
        )
        for row, (label, command, variant) in enumerate(quick_actions, start=2):
            RoundedButton(
                left,
                text=label,
                command=command,
                variant=variant,
                width=260,
                height=30,
                radius=15,
                background=COLORS["glass"],
            ).grid(
                column=0, row=row, sticky="ew", pady=(0, 4)
            )

        right_panel = RoundedPanel(frame, fill=COLORS["glass"], radius=26, padding=14)
        right_panel.grid(column=1, row=2, sticky="nsew", padx=(6, 0))
        right = right_panel.content
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Команды для старта", style="PanelSection.TLabel").grid(column=0, row=0, sticky="w")
        ttk.Label(right, text="Нажмите фразу, чтобы отправить её в чат.", style="HeaderSubtitle.TLabel").grid(
            column=0, row=1, sticky="w", pady=(2, 12)
        )
        for row, phrase in enumerate(("что ты умеешь", "последние команды", "проверь ассистента"), start=2):
            RoundedButton(
                right,
                text=phrase,
                command=lambda value=phrase: self._home_send_chat(value),
                width=260,
                height=30,
                radius=15,
                background=COLORS["glass"],
            ).grid(
                column=0, row=row, sticky="ew", pady=(0, 4)
            )

    def _build_status_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.status_tab = frame
        self.notebook.add(frame, text="Состояние")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.Frame(frame)
        header.grid(column=0, row=0, sticky="ew", pady=(0, 10))
        ttk.Label(header, text="Готовность ассистента", style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="Обновить", command=self.refresh_status_view).pack(side="right")
        ttk.Button(header, text="Диагностика", command=self.run_project_diagnostics).pack(side="right", padx=(0, 8))

        self.status_summary = ttk.Label(frame, text="", style="Hint.TLabel", wraplength=860)
        self.status_summary.grid(column=0, row=1, sticky="ew", pady=(0, 8))

        self.status_tree = ttk.Treeview(
            frame,
            columns=("status", "details"),
            show="tree headings",
        )
        self.status_tree.heading("#0", text="Проверка")
        self.status_tree.heading("status", text="Статус")
        self.status_tree.heading("details", text="Детали")
        self.status_tree.column("#0", width=240, stretch=False)
        self.status_tree.column("status", width=120, stretch=False)
        self.status_tree.column("details", width=560, stretch=True)
        self.status_tree.tag_configure("ok", foreground="#176b35")
        self.status_tree.tag_configure("warn", foreground="#8a5a00")
        self.status_tree.tag_configure("fail", foreground="#9b1c1c")
        self.status_tree.grid(column=0, row=2, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.status_tree.yview)
        scrollbar.grid(column=1, row=2, sticky="ns")
        self.status_tree.configure(yscrollcommand=scrollbar.set)

    def _build_chat_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.chat_tab = frame
        self.notebook.add(frame, text="Чат")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.Frame(frame)
        header.grid(column=0, row=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="Чат с ассистентом", style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="Очистить экран", command=self.clear_chat).pack(side="right")
        ttk.Button(header, text="Обновить контекст", command=self.reset_chat_runtime).pack(side="right", padx=(0, 8))
        toggle_wrap = ttk.Frame(header)
        toggle_wrap.pack(side="right", padx=(0, 10))
        ttk.Label(toggle_wrap, text="Голос", style="Hint.TLabel").pack(side="left", padx=(0, 8))
        self.voice_toggle_button = IOSToggle(toggle_wrap, command=self.toggle_voice_listening)
        self.voice_toggle_button.pack(side="left")
        self._refresh_voice_toggle_button()

        quick = ttk.Frame(frame)
        quick.grid(column=0, row=1, sticky="ew", pady=(0, 8))
        for label, command in (
            ("Что ты умеешь", "что ты умеешь"),
            ("Последние команды", "последние команды"),
            ("Проверить ассистента", "проверь ассистента"),
        ):
            ttk.Button(quick, text=label, command=lambda value=command: self.send_quick_chat(value)).pack(
                side="left", padx=(0, 8)
            )

        chat_panel_outer = RoundedPanel(frame, fill=COLORS["chat_bg"], radius=26, padding=2)
        chat_panel_outer.grid(column=0, row=2, sticky="nsew")
        chat_panel = chat_panel_outer.content
        chat_panel.columnconfigure(0, weight=1)
        chat_panel.rowconfigure(0, weight=1)

        self.chat_text = tk.Text(
            chat_panel,
            wrap="word",
            font="AppChat",
            state="disabled",
            background=COLORS["chat_bg"],
            foreground=COLORS["text"],
            relief="flat",
            borderwidth=0,
            padx=16,
            pady=14,
            insertbackground=COLORS["primary"],
            selectbackground="#d2e3fc",
            selectforeground=COLORS["text"],
        )
        self.chat_text.grid(column=0, row=0, sticky="nsew")
        self.chat_text.tag_configure("user_label", foreground=COLORS["primary"], font="AppChatLabel", spacing1=10)
        self.chat_text.tag_configure("voice_label", foreground=COLORS["warning"], font="AppChatLabel", spacing1=10)
        self.chat_text.tag_configure("assistant_label", foreground=COLORS["success"], font="AppChatLabel", spacing1=10)
        self.chat_text.tag_configure("system_label", foreground=COLORS["muted"], font="AppChatLabel", spacing1=10)
        self.chat_text.tag_configure(
            "user_message",
            foreground="#ffffff",
            background=COLORS["primary"],
            lmargin1=18,
            lmargin2=18,
            rmargin=120,
            spacing1=3,
            spacing3=10,
        )
        self.chat_text.tag_configure(
            "assistant_message",
            foreground=COLORS["text"],
            background=COLORS["bubble_assistant"],
            lmargin1=18,
            lmargin2=18,
            rmargin=80,
            spacing1=3,
            spacing3=10,
        )
        self.chat_text.tag_configure(
            "voice_message",
            foreground=COLORS["text"],
            background=COLORS["bubble_voice"],
            lmargin1=18,
            lmargin2=18,
            rmargin=80,
            spacing1=3,
            spacing3=10,
        )
        self.chat_text.tag_configure(
            "system_message",
            foreground=COLORS["muted"],
            background=COLORS["bubble_system"],
            lmargin1=18,
            lmargin2=18,
            rmargin=80,
            spacing1=3,
            spacing3=10,
        )

        scrollbar = ttk.Scrollbar(chat_panel, orient="vertical", command=self.chat_text.yview)
        scrollbar.grid(column=1, row=0, sticky="ns")
        self.chat_text.configure(yscrollcommand=scrollbar.set)

        input_row = ttk.Frame(frame)
        input_row.grid(column=0, row=3, sticky="ew", pady=(10, 0))
        input_row.columnconfigure(0, weight=1)
        self.chat_input = ttk.Entry(input_row)
        self.chat_input.grid(column=0, row=0, sticky="ew", ipady=5)
        self.chat_input.bind("<Return>", lambda _event: self.send_chat_message())
        RoundedButton(
            input_row,
            text="Отправить",
            command=self.send_chat_message,
            variant="accent",
            width=124,
            background=COLORS["bg"],
        ).grid(
            column=1, row=0, padx=(8, 0)
        )

        self._append_chat("system", "Можно писать обычные команды: например, 'открой браузер', 'последние команды', 'что ты умеешь'.")

    def _home_send_chat(self, text: str):
        self._select_tab(self.chat_tab)
        self.send_quick_chat(text)

    def _build_profiles_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.profiles_tab = frame
        self.notebook.add(frame, text="Профили")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.Frame(frame)
        header.grid(column=0, row=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="Профили ассистента", style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="Удалить", command=self.delete_selected_profile).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Импорт", command=self.import_profile_ui).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Экспорт", command=self.export_selected_profile).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Применить", command=self.apply_selected_profile).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Сохранить текущие", command=self.save_current_profile).pack(side="right")

        ttk.Label(
            frame,
            text=(
                "Профиль хранит имя, язык, голос, слова активации, режим работы и приватность. "
                "API-ключи и пути приложений в профиль не попадают."
            ),
            style="Hint.TLabel",
            wraplength=860,
        ).grid(column=0, row=1, sticky="ew", pady=(0, 10))

        self.profiles_tree = ttk.Treeview(
            frame,
            columns=("active", "language", "voice", "privacy", "created_at"),
            show="tree headings",
            height=10,
        )
        self.profiles_tree.heading("#0", text="Название")
        self.profiles_tree.heading("active", text="Активен")
        self.profiles_tree.heading("language", text="Язык")
        self.profiles_tree.heading("voice", text="Голос")
        self.profiles_tree.heading("privacy", text="Приватность")
        self.profiles_tree.heading("created_at", text="Создан")
        self.profiles_tree.column("#0", width=220, stretch=True)
        self.profiles_tree.column("active", width=80, stretch=False, anchor="center")
        self.profiles_tree.column("language", width=110, stretch=False)
        self.profiles_tree.column("voice", width=150, stretch=False)
        self.profiles_tree.column("privacy", width=170, stretch=False)
        self.profiles_tree.column("created_at", width=160, stretch=False)
        self.profiles_tree.grid(column=0, row=2, sticky="nsew")
        self.profiles_tree.bind("<<TreeviewSelect>>", lambda _event: self.show_selected_profile_details())

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.profiles_tree.yview)
        scrollbar.grid(column=1, row=2, sticky="ns")
        self.profiles_tree.configure(yscrollcommand=scrollbar.set)

        detail = ttk.Frame(frame)
        detail.grid(column=0, row=3, sticky="ew", pady=(8, 0))
        detail.columnconfigure(0, weight=1)
        ttk.Label(detail, text="Детали профиля", style="Hint.TLabel").grid(column=0, row=0, sticky="w")
        self.profile_detail_text = tk.Text(
            detail,
            height=7,
            wrap="word",
            font="AppMono",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            bg=COLORS["surface_alt"],
            fg=COLORS["text"],
        )
        self.profile_detail_text.grid(column=0, row=1, sticky="ew", pady=(4, 0))
        self.profile_detail_text.configure(state="disabled")

    def _build_voice_tab(self):
        tab = self._add_scroll_tab("Голос", "voice_tab")
        self._section(tab, "Синтез речи", 0)
        row = 1
        row = self._checkbox(tab, row, ("voice_enabled",), "Озвучивать ответы")
        row = self._combo(tab, row, ("voice_engine",), "Движок озвучивания", ["silero", "pyttsx3"])
        row = self._scale(tab, row, ("voice_speed",), "Скорость pyttsx3", 80, 260, int)
        row = self._scale(tab, row, ("voice_volume",), "Громкость", 0.0, 1.0, float)
        row = self._combo(
            tab,
            row,
            ("voice_gender",),
            "Пол голоса",
            list(VOICE_GENDER_CODES.keys()),
            _voice_gender_code,
            _voice_gender_label,
        )
        row = self._entry(tab, row, ("voice_speaker",), "Спикер Silero")

        self._section(tab, "Silero", row)
        row += 1
        row = self._entry(tab, row, ("silero", "ru_speakers"), "Русские спикеры", _list_to_csv, _csv_to_list)
        row = self._entry(tab, row, ("silero", "en_speakers"), "Английские спикеры", _list_to_csv, _csv_to_list)
        row = self._combo(tab, row, ("silero", "sample_rate"), "Частота дискретизации", ["24000", "48000"], int)
        self._checkbox(tab, row, ("silero", "use_cuda"), "Использовать CUDA, если доступна")

    def _build_assistant_tab(self):
        tab = self._add_scroll_tab("Ассистент", "assistant_tab")
        self._section(tab, "Профиль", 0)
        row = 1
        row = self._entry(tab, row, ("assistant", "name"), "Имя ассистента")
        row = self._combo(
            tab,
            row,
            ("assistant", "default_language"),
            "Язык по умолчанию",
            list(LANGUAGE_CODES.keys()),
            _language_code,
            _language_label,
        )
        row = self._entry(tab, row, ("assistant", "voice"), "Профиль голоса")
        row = self._combo(
            tab,
            row,
            ("assistant", "personality"),
            "Стиль общения",
            list(PERSONALITY_CODES.keys()),
            _personality_code,
            _personality_label,
        )

        self._section(tab, "Распознавание и активация", row)
        row += 1
        row = self._combo(tab, row, ("language",), "Язык распознавания", ["ru-RU", "en-US"])
        row = self._entry(tab, row, ("wake_word",), "Основное слово активации")
        row = self._entry(tab, row, ("wake_words", "ru"), "Слова активации RU", _list_to_csv, _csv_to_list)
        row = self._entry(tab, row, ("wake_words", "en"), "Слова активации EN", _list_to_csv, _csv_to_list)
        row = self._scale(tab, row, ("recognition", "online_listen_seconds"), "Онлайн-запись, секунд", 2, 12, int)
        row = self._scale(
            tab,
            row,
            ("recognition", "offline_listen_timeout_seconds"),
            "Офлайн-окно распознавания, секунд",
            3,
            20,
            int,
        )
        row = self._scale(tab, row, ("recognition", "recover_after_errors"), "Ошибок до восстановления микрофона", 1, 10, int)
        row = self._scale(tab, row, ("recognition", "miss_threshold"), "Промахов до подсказки", 1, 10, int)
        row = self._checkbox(tab, row, ("recognition", "repeat_prompt_enabled"), "Говорить 'повторите' при промахах")

        self._section(tab, "Распознавание команд", row)
        row += 1
        row = self._scale(tab, row, ("matcher", "threshold"), "Порог совпадения команд", 40, 95, int)
        row = self._scale(tab, row, ("matcher", "partial_threshold"), "Порог частичного совпадения", 50, 100, int)
        row = self._scale(tab, row, ("matcher", "smalltalk_threshold"), "Порог коротких фраз", 25, 90, int)
        row = self._scale(tab, row, ("matcher", "min_partial_length"), "Минимум слов для частичного совпадения", 2, 10, int)

        self._section(tab, "Режимы работы", row)
        row += 1
        row = self._checkbox(tab, row, ("debug",), "Подробный лог")
        row = self._checkbox(tab, row, ("offline_mode",), "Офлайн-режим")
        row = self._checkbox(tab, row, ("auto_switch_mode",), "Автоматическое переключение онлайн/офлайн")
        row = self._checkbox(tab, row, ("first_run_completed",), "Первичная настройка завершена")

        self._section(tab, "Windows и трей", row)
        row += 1
        row = self._checkbox(tab, row, ("startup", "launch_on_login"), "Запускать Cry вместе с Windows")
        row = self._checkbox(tab, row, ("startup", "start_minimized_to_tray"), "При автозапуске открывать в трее")
        row = self._checkbox(tab, row, ("startup", "minimize_to_tray_on_close"), "Сворачивать в трей при закрытии окна")
        row = self._checkbox(tab, row, ("startup", "start_assistant_on_launch"), "Запускать голосового ассистента при открытии приложения")

        self._section(tab, "Приватность и support", row)
        row += 1
        row = self._checkbox(tab, row, ("privacy", "redact_secrets_in_exports"), "Скрывать секреты при экспорте")
        row = self._checkbox(tab, row, ("privacy", "include_logs_in_reports"), "Включать журнал в support-отчёт")
        row = self._checkbox(tab, row, ("privacy", "include_history_in_reports"), "Включать историю команд в support-отчёт")
        self._scale(tab, row, ("privacy", "crash_summary_lines"), "Строк журнала для crash summary", 20, 300, int)

    def _build_integrations_tab(self):
        tab = self._add_scroll_tab("Интеграции", "integrations_tab")
        self._section(tab, "ИИ / ЯндексGPT", 0)
        row = 1
        row = self._checkbox(tab, row, ("assistant", "ai_enabled"), "Отвечать через ИИ на неизвестные команды")
        row = self._entry(tab, row, ("assistant", "yandexgpt_api_key"), "API-ключ ЯндексGPT", show="*")
        row = self._entry(tab, row, ("assistant", "yandex_folder_id"), "ID каталога Яндекс Облака")

        self._section(tab, "Погода и новости", row)
        row += 1
        row = self._entry(tab, row, ("weather", "api_key"), "API-ключ OpenWeatherMap", show="*")
        row = self._entry(tab, row, ("weather", "default_city"), "Город по умолчанию")
        self._entry(tab, row, ("news", "api_key"), "API-ключ NewsAPI", show="*")

    def _build_safety_tab(self):
        tab = self._add_scroll_tab("Безопасность", "safety_tab")
        self._section(tab, "Подтверждение опасных команд", 0)
        row = 1
        row = self._checkbox(
            tab,
            row,
            ("safety", "confirm_dangerous_commands"),
            "Запрашивать голосовое подтверждение перед опасными командами",
        )
        row = self._scale(
            tab,
            row,
            ("safety", "confirmation_timeout_seconds"),
            "Тайм-аут подтверждения, секунд",
            5,
            60,
            int,
        )
        row = self._scale(
            tab,
            row,
            ("safety", "dangerous_min_score"),
            "Минимальная уверенность для опасных команд",
            60,
            100,
            int,
        )
        self._section(tab, "Команды, требующие подтверждения", row)
        row += 1
        self._entry(
            tab,
            row,
            ("safety", "dangerous_actions"),
            "Внутренние действия через запятую",
            _list_to_csv,
            _csv_to_list,
        )

    def _build_apps_tab(self):
        tab = self._add_scroll_tab("Приложения", "apps_tab")
        self.app_labels = {
            "telegram": "Telegram",
            "yamusic": "Яндекс Музыка",
            "discord": "Discord",
            "steam": "Steam",
            "flstudio": "FL Studio",
            "msword": "Microsoft Word",
            "msexcel": "Microsoft Excel",
            "mspowerpoint": "Microsoft PowerPoint",
        }
        self._section(tab, "Статусы приложений", 0)
        self.apps_tree = ttk.Treeview(
            tab,
            columns=("status", "path", "process"),
            show="tree headings",
            height=8,
        )
        self.apps_tree.heading("#0", text="Приложение")
        self.apps_tree.heading("status", text="Статус")
        self.apps_tree.heading("path", text="Путь")
        self.apps_tree.heading("process", text="Процесс")
        self.apps_tree.column("#0", width=180, stretch=False)
        self.apps_tree.column("status", width=140, stretch=False)
        self.apps_tree.column("path", width=460, stretch=True)
        self.apps_tree.column("process", width=160, stretch=False)
        self.apps_tree.tag_configure("ok", foreground="#176b35")
        self.apps_tree.tag_configure("warn", foreground="#8a5a00")
        self.apps_tree.grid(column=0, row=1, columnspan=3, sticky="ew", pady=(0, 8))

        app_actions = ttk.Frame(tab)
        app_actions.grid(column=0, row=2, columnspan=3, sticky="ew", pady=(0, 10))
        ttk.Button(app_actions, text="Обновить статусы", command=self.refresh_apps_view).pack(side="left")
        ttk.Button(app_actions, text="Подставить найденные пути", command=self.apply_discovered_app_paths).pack(
            side="left", padx=(8, 0)
        )

        self._section(tab, "Пути к приложениям", 3)
        row = 4
        for app_key, label in self.app_labels.items():
            row = self._path_entry(tab, row, ("apps", app_key, "path"), f"{label}: путь")
            row = self._entry(tab, row, ("apps", app_key, "process"), f"{label}: процесс")

    def _build_paths_tab(self):
        tab = self._add_scroll_tab("Пути", "paths_tab")
        self._section(tab, "Файлы и каталоги", 0)
        row = 1
        row = self._entry(tab, row, ("paths", "datasets"), "Команды")
        row = self._entry(tab, row, ("paths", "user_commands"), "Пользовательские команды")
        row = self._entry(tab, row, ("paths", "tts_models"), "Модели озвучивания")
        row = self._entry(tab, row, ("paths", "stt_models"), "STT модели")
        row = self._entry(tab, row, ("paths", "cache_dir"), "Кэш")
        self._entry(tab, row, ("paths", "database"), "База данных")

    def _build_commands_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.commands_tab = frame
        self.notebook.add(frame, text="Команды")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.Frame(frame)
        header.grid(column=0, row=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="Доступные голосовые команды", style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="Проверить фразу", command=self.test_command_phrase).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Подтверждать", command=lambda: self.set_selected_command_confirmation(True)).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(header, text="Без подтверждения", command=lambda: self.set_selected_command_confirmation(False)).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(header, text="Удалить свою фразу", command=self.delete_user_command_phrase).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Добавить фразу", command=self.add_user_command_phrase).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Обновить", command=self.refresh_commands_view).pack(side="right")

        search = ttk.Frame(frame)
        search.grid(column=0, row=1, sticky="ew", pady=(0, 8))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Поиск").grid(column=0, row=0, sticky="w")
        self.command_search_var = tk.StringVar()
        self.command_search_var.trace_add("write", lambda *_: self.refresh_commands_view())
        ttk.Entry(search, textvariable=self.command_search_var).grid(column=1, row=0, sticky="ew", padx=(10, 0), ipady=3)

        self.commands_tree = ttk.Treeview(
            frame,
            columns=("source", "confirm", "action", "patterns"),
            show="tree headings",
        )
        self.commands_tree.heading("#0", text="Раздел")
        self.commands_tree.heading("source", text="Источник")
        self.commands_tree.heading("confirm", text="Подтв.")
        self.commands_tree.heading("action", text="Действие")
        self.commands_tree.heading("patterns", text="Фразы")
        self.commands_tree.column("#0", width=160, stretch=False)
        self.commands_tree.column("source", width=110, stretch=False)
        self.commands_tree.column("confirm", width=70, stretch=False, anchor="center")
        self.commands_tree.column("action", width=190, stretch=False)
        self.commands_tree.column("patterns", width=390, stretch=True)
        self.commands_tree.tag_configure("custom", foreground=COLORS["primary"])
        self.commands_tree.grid(column=0, row=2, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.commands_tree.yview)
        scrollbar.grid(column=1, row=2, sticky="ns")
        self.commands_tree.configure(yscrollcommand=scrollbar.set)

    def _build_notes_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notes_tab = frame
        self.notebook.add(frame, text="Заметки")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.Frame(frame)
        header.grid(column=0, row=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="Заметки", style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="Обновить", command=self.refresh_notes_view).pack(side="right")
        ttk.Button(header, text="Очистить", command=self.clear_notes_ui).pack(side="right", padx=(0, 8))
        ttk.Button(header, text="Удалить", command=self.delete_selected_note).pack(side="right", padx=(0, 8))
        ttk.Button(header, text="Добавить", command=self.add_note_ui).pack(side="right", padx=(0, 8))

        search = ttk.Frame(frame)
        search.grid(column=0, row=1, sticky="ew", pady=(0, 8))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Поиск").grid(column=0, row=0, sticky="w")
        self.notes_search_var = tk.StringVar()
        self.notes_search_var.trace_add("write", lambda *_: self.refresh_notes_view())
        ttk.Entry(search, textvariable=self.notes_search_var).grid(column=1, row=0, sticky="ew", padx=(10, 0), ipady=3)

        self.notes_tree = ttk.Treeview(frame, columns=("id", "created_at", "text"), show="headings")
        for column, title, width in (
            ("id", "ID", 60),
            ("created_at", "Создано", 170),
            ("text", "Текст", 620),
        ):
            self.notes_tree.heading(column, text=title)
            self.notes_tree.column(column, width=width, stretch=column == "text")
        self.notes_tree.grid(column=0, row=2, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.notes_tree.yview)
        scrollbar.grid(column=1, row=2, sticky="ns")
        self.notes_tree.configure(yscrollcommand=scrollbar.set)

    def _build_reminders_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.reminders_tab = frame
        self.notebook.add(frame, text="Напоминания")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.Frame(frame)
        header.grid(column=0, row=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="Напоминания", style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="Обновить", command=self.refresh_reminders_view).pack(side="right")
        ttk.Button(header, text="Очистить завершенные", command=self.clear_completed_reminders_ui).pack(side="right", padx=(0, 8))
        ttk.Button(header, text="Удалить", command=self.delete_selected_reminder).pack(side="right", padx=(0, 8))
        ttk.Button(header, text="Завершить", command=self.complete_selected_reminder).pack(side="right", padx=(0, 8))
        ttk.Button(header, text="Добавить", command=self.add_reminder_ui).pack(side="right", padx=(0, 8))

        filter_row = ttk.Frame(frame)
        filter_row.grid(column=0, row=1, sticky="ew", pady=(0, 8))
        filter_row.columnconfigure(1, weight=1)
        ttk.Label(filter_row, text="Поиск").grid(column=0, row=0, sticky="w")
        self.reminders_search_var = tk.StringVar()
        self.reminders_search_var.trace_add("write", lambda *_: self.refresh_reminders_view())
        ttk.Entry(filter_row, textvariable=self.reminders_search_var).grid(column=1, row=0, sticky="ew", padx=(10, 12), ipady=3)
        self.show_completed_reminders = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            filter_row,
            text="Показывать завершенные",
            variable=self.show_completed_reminders,
            command=self.refresh_reminders_view,
        ).grid(column=2, row=0, sticky="e")

        self.reminders_tree = ttk.Treeview(
            frame,
            columns=("id", "status", "kind", "due_at", "text"),
            show="headings",
        )
        for column, title, width in (
            ("id", "ID", 60),
            ("status", "Статус", 105),
            ("kind", "Тип", 90),
            ("due_at", "Когда", 150),
            ("text", "Текст", 520),
        ):
            self.reminders_tree.heading(column, text=title)
            self.reminders_tree.column(column, width=width, stretch=column == "text")
        self.reminders_tree.tag_configure("done", foreground=COLORS["muted"])
        self.reminders_tree.tag_configure("overdue", foreground=COLORS["danger"])
        self.reminders_tree.grid(column=0, row=2, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.reminders_tree.yview)
        scrollbar.grid(column=1, row=2, sticky="ns")
        self.reminders_tree.configure(yscrollcommand=scrollbar.set)

    def _build_history_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.history_tab = frame
        self.notebook.add(frame, text="История")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.Frame(frame)
        header.grid(column=0, row=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="История распознанных команд", style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="Обновить", command=self.refresh_history_view).pack(side="right")
        ttk.Button(header, text="Очистить", command=self.clear_history).pack(side="right", padx=(0, 8))
        ttk.Button(header, text="Копировать детали", command=self.copy_selected_history).pack(side="right", padx=(0, 8))

        filters = ttk.Frame(frame)
        filters.grid(column=0, row=1, sticky="ew", pady=(0, 8))
        filters.columnconfigure(1, weight=1)
        self.history_query_var = tk.StringVar()
        self.history_query_var.trace_add("write", lambda *_: self.refresh_history_view())
        self.history_source_var = tk.StringVar(value=HISTORY_SOURCE_LABELS["all"])
        self.history_status_var = tk.StringVar(value=HISTORY_STATUS_LABELS["all"])

        ttk.Label(filters, text="Поиск").grid(column=0, row=0, sticky="w")
        ttk.Entry(filters, textvariable=self.history_query_var).grid(
            column=1, row=0, sticky="ew", padx=(8, 12), ipady=3
        )
        ttk.Label(filters, text="Источник").grid(column=2, row=0, sticky="w")
        source_box = ttk.Combobox(
            filters,
            textvariable=self.history_source_var,
            values=tuple(HISTORY_SOURCE_LABELS.values()),
            state="readonly",
            width=10,
        )
        source_box.grid(column=3, row=0, sticky="w", padx=(8, 12))
        source_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_history_view())

        ttk.Label(filters, text="Статус").grid(column=4, row=0, sticky="w")
        status_box = ttk.Combobox(
            filters,
            textvariable=self.history_status_var,
            values=tuple(HISTORY_STATUS_LABELS.values()),
            state="readonly",
            width=24,
        )
        status_box.grid(column=5, row=0, sticky="w", padx=(8, 12))
        status_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_history_view())
        ttk.Button(filters, text="Сброс", command=self.reset_history_filters).grid(column=6, row=0, sticky="e")

        self.history_tree = ttk.Treeview(
            frame,
            columns=("created_at", "source", "status", "text", "actions", "response"),
            show="headings",
        )
        for column, title, width in (
            ("created_at", "Время", 130),
            ("source", "Источник", 75),
            ("status", "Статус", 105),
            ("text", "Фраза", 180),
            ("actions", "Действие", 160),
            ("response", "Ответ", 270),
        ):
            self.history_tree.heading(column, text=title)
            self.history_tree.column(column, width=width, stretch=column in {"text", "response"})
        self.history_tree.grid(column=0, row=2, sticky="nsew")
        self.history_tree.bind("<<TreeviewSelect>>", lambda _event: self.show_selected_history_details())

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.history_tree.yview)
        scrollbar.grid(column=1, row=2, sticky="ns")
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        detail_frame = ttk.Frame(frame)
        detail_frame.grid(column=0, row=3, sticky="ew", pady=(8, 0))
        detail_frame.columnconfigure(0, weight=1)
        ttk.Label(detail_frame, text="Детали выбранной записи", style="Hint.TLabel").grid(column=0, row=0, sticky="w")
        self.history_detail_text = tk.Text(
            detail_frame,
            height=5,
            wrap="word",
            font="AppMono",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            bg=COLORS["surface_alt"],
            fg=COLORS["text"],
        )
        self.history_detail_text.grid(column=0, row=1, sticky="ew", pady=(4, 0))
        self.history_detail_text.configure(state="disabled")

        self.history_summary_label = ttk.Label(frame, text="", style="Hint.TLabel")
        self.history_summary_label.grid(column=0, row=4, sticky="w", pady=(8, 0))

    def _build_diagnostics_tab(self):
        tab = self._add_scroll_tab("Диагностика", "diagnostics_tab")
        self._section(tab, "Проверки", 0)
        ttk.Button(tab, text="Проверить конфигурацию", command=self.check_config).grid(
            column=0, row=1, sticky="w", pady=6
        )
        ttk.Button(tab, text="Запустить диагностику проекта", command=self.run_project_diagnostics).grid(
            column=0, row=2, sticky="w", pady=6
        )
        ttk.Button(tab, text="Показать последние записи журнала", command=self.show_recent_logs).grid(
            column=0, row=3, sticky="w", pady=6
        )
        ttk.Button(tab, text="Показать health snapshot", command=self.show_health_snapshot).grid(
            column=0, row=4, sticky="w", pady=6
        )
        ttk.Button(tab, text="Показать crash summary", command=self.show_crash_summary).grid(
            column=0, row=6, sticky="w", pady=6
        )

        self._section(tab, "Support и приватность", 7)
        ttk.Button(tab, text="Экспортировать отчёт для поддержки", command=self.export_support_report).grid(
            column=0, row=8, sticky="w", pady=6
        )
        ttk.Button(tab, text="Проверить заполненные секреты", command=self.show_secret_status).grid(
            column=0, row=9, sticky="w", pady=6
        )
        ttk.Button(tab, text="Очистить API-ключи", command=self.clear_api_keys_ui).grid(column=0, row=10, sticky="w", pady=6)
        ttk.Button(tab, text="Очистить журнал", command=self.clear_logs).grid(column=0, row=11, sticky="w", pady=6)

        self._section(tab, "Экспорт и импорт настроек", 12)
        ttk.Button(tab, text="Сделать резервную копию настроек", command=self.backup_config_ui).grid(
            column=0, row=13, sticky="w", pady=6
        )
        ttk.Button(tab, text="Восстановить настройки из файла", command=self.restore_config_ui).grid(
            column=0, row=14, sticky="w", pady=6
        )
        ttk.Button(tab, text="Проверить микрофон при следующем запуске", command=self.mark_first_run_incomplete).grid(
            column=0, row=15, sticky="w", pady=6
        )
        ttk.Label(
            tab,
            text=(
                "Диагностика микрофона и моделей выполняется в мастере первого запуска. "
                "Support-отчёт скрывает API-ключи и помогает передать состояние проекта без ручного копирования логов. "
                "Сборка в EXE будет отдельным финальным этапом."
            ),
            style="Hint.TLabel",
            wraplength=760,
        ).grid(column=0, row=16, columnspan=2, sticky="w", pady=(10, 0))

    def _build_raw_tab(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.raw_tab = frame
        self.notebook.add(frame, text="Конфиг")
        ttk.Label(frame, text="Текущий файл настроек после загрузки/сохранения", style="Section.TLabel").pack(anchor="w")
        self.raw_text = tk.Text(frame, height=24, wrap="none", font="AppMono")
        self.raw_text.pack(fill="both", expand=True, pady=(8, 0))

    def _add_scroll_tab(self, title: str, tab_attr: str | None = None) -> ttk.Frame:
        frame = ScrollableFrame(self.notebook)
        if tab_attr:
            setattr(self, tab_attr, frame)
        self.notebook.add(frame, text=title)
        frame.content.columnconfigure(1, weight=1)
        frame.content.configure(style="TFrame")
        return frame.content

    def _section(self, parent: ttk.Frame, text: str, row: int):
        ttk.Label(parent, text=text, style="Section.TLabel").grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(12, 8)
        )

    def _entry(
        self,
        parent: ttk.Frame,
        row: int,
        path: tuple[str, ...],
        label: str,
        reader: Callable[[Any], Any] = lambda value: "" if value is None else value,
        writer: Callable[[Any], Any] = lambda value: value,
        show: str | None = None,
    ) -> int:
        variable = tk.StringVar()
        self._label(parent, row, label)
        ttk.Entry(parent, textvariable=variable, show=show).grid(column=1, row=row, sticky="ew", padx=(12, 0), ipady=3)
        self.fields.append(ConfigField(path, label, variable, reader, writer))
        return row + 1

    def _path_entry(
        self,
        parent: ttk.Frame,
        row: int,
        path: tuple[str, ...],
        label: str,
    ) -> int:
        variable = tk.StringVar()
        self._label(parent, row, label)
        control = ttk.Frame(parent)
        control.grid(column=1, row=row, sticky="ew", padx=(12, 0))
        control.columnconfigure(0, weight=1)
        ttk.Entry(control, textvariable=variable).grid(column=0, row=0, sticky="ew", ipady=3)

        def browse():
            selected = filedialog.askopenfilename(
                title=f"Выберите файл для {label}",
                filetypes=[
                    ("Приложения и ярлыки", "*.exe *.lnk"),
                    ("Все файлы", "*.*"),
                ],
            )
            if selected:
                variable.set(selected)

        ttk.Button(control, text="Выбрать", command=browse).grid(column=1, row=0, padx=(8, 0))
        self.fields.append(ConfigField(path, label, variable, lambda value: "" if value is None else value))
        return row + 1

    def _combo(
        self,
        parent: ttk.Frame,
        row: int,
        path: tuple[str, ...],
        label: str,
        values: list[str],
        writer: Callable[[Any], Any] = lambda value: value,
        reader: Callable[[Any], Any] = lambda value: "" if value is None else str(value),
    ) -> int:
        variable = tk.StringVar()
        self._label(parent, row, label)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            column=1, row=row, sticky="ew", padx=(12, 0)
        )
        self.fields.append(ConfigField(path, label, variable, reader, writer))
        return row + 1

    def _checkbox(self, parent: ttk.Frame, row: int, path: tuple[str, ...], label: str) -> int:
        variable = tk.BooleanVar()
        ttk.Checkbutton(parent, text=label, variable=variable).grid(
            column=0, row=row, columnspan=2, sticky="w", pady=5
        )
        self.fields.append(ConfigField(path, label, variable, bool, bool))
        return row + 1

    def _scale(
        self,
        parent: ttk.Frame,
        row: int,
        path: tuple[str, ...],
        label: str,
        from_: float,
        to: float,
        writer: Callable[[Any], Any],
    ) -> int:
        variable = tk.DoubleVar()
        value_label = ttk.Label(parent, width=8)

        def update_label(*_):
            value = variable.get()
            value_label.configure(text=f"{value:.2f}" if writer is float else str(int(value)))

        variable.trace_add("write", update_label)
        self._label(parent, row, label)
        ttk.Scale(parent, variable=variable, from_=from_, to=to).grid(column=1, row=row, sticky="ew", padx=(12, 0))
        value_label.grid(column=2, row=row, sticky="e", padx=(10, 0))
        self.fields.append(ConfigField(path, label, variable, lambda value: value or from_, writer))
        return row + 1

    def _label(self, parent: ttk.Frame, row: int, text: str):
        ttk.Label(parent, text=text).grid(column=0, row=row, sticky="w", pady=7)

    def load_config(self):
        try:
            self.settings.reload()
            for field in self.fields:
                field.load(self.settings.config)
            self._refresh_raw()
            self.refresh_status_view()
            self.refresh_commands_view()
            self.refresh_profiles_view()
            self.refresh_notes_view()
            self.refresh_reminders_view()
            self.refresh_apps_view()
            self.refresh_history_view()
            self._prime_voice_history_position()
            self._refresh_voice_toggle_button()
            self.refresh_home_view()
            self._refresh_header_status()
            self._configure_tray()
        except Exception as exc:
            messagebox.showerror("Ошибка загрузки", str(exc))

    def save_config(self):
        try:
            config = self._config_from_fields()
            self.settings.save(config)
            self.settings.reload()
            self._sync_autostart(self.settings.config, silent=False)
            self._refresh_raw()
            self.refresh_commands_view()
            self.refresh_profiles_view()
            self.refresh_notes_view()
            self.refresh_reminders_view()
            self.refresh_apps_view()
            self.refresh_status_view()
            self.refresh_home_view()
            self._refresh_header_status()
            messagebox.showinfo("Сохранено", "Настройки записаны в config.yaml.")
        except Exception as exc:
            messagebox.showerror("Ошибка сохранения", str(exc))

    def _config_from_fields(self) -> dict:
        config = deepcopy(self.settings.config)
        for field in self.fields:
            self._set_nested(config, field.path, field.dump())
        return config

    def _set_field_value(self, path: tuple[str, ...], value: Any):
        for field in self.fields:
            if field.path == path:
                field.variable.set(value)
                return

    def _set_nested(self, config: dict, path: tuple[str, ...], value: Any):
        node = config
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = value

    def _refresh_raw(self):
        text = yaml.safe_dump(
            self.settings.config,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        self.raw_text.delete("1.0", tk.END)
        self.raw_text.insert("1.0", text)

    def refresh_profiles_view(self):
        if not hasattr(self, "profiles_tree"):
            return
        self.profile_items = {}
        for item in self.profiles_tree.get_children():
            self.profiles_tree.delete(item)

        profiles = self.settings.config.get("profiles", {}) or {}
        active = str(profiles.get("active") or "")
        items = profiles.get("items", {}) or {}
        for key, profile in items.items():
            if not isinstance(profile, dict):
                continue
            settings = profile.get("settings", {}) or {}
            language = _language_label(settings.get("assistant.default_language", ""))
            voice = settings.get("voice_engine", "")
            privacy = settings.get("privacy", {}) if isinstance(settings.get("privacy"), dict) else {}
            privacy_label = "Секреты скрываются" if privacy.get("redact_secrets_in_exports", True) else "Секреты не скрываются"
            item_id = self.profiles_tree.insert(
                "",
                "end",
                text=str(profile.get("label") or key),
                values=("✓" if key == active else "", language, voice, privacy_label, profile.get("created_at", "")),
            )
            self.profile_items[item_id] = (key, profile)
        self.show_selected_profile_details()

    def _selected_profile(self) -> tuple[str, dict] | tuple[None, None]:
        selection = self.profiles_tree.selection() if hasattr(self, "profiles_tree") else ()
        if not selection:
            return None, None
        return getattr(self, "profile_items", {}).get(selection[0], (None, None))

    def show_selected_profile_details(self):
        if not hasattr(self, "profile_detail_text"):
            return
        _key, profile = self._selected_profile()
        if profile:
            text = yaml.safe_dump(profile, allow_unicode=True, sort_keys=False)
        else:
            text = "Выберите профиль или сохраните текущие настройки как новый профиль."
        self.profile_detail_text.configure(state="normal")
        self.profile_detail_text.delete("1.0", tk.END)
        self.profile_detail_text.insert("1.0", text)
        self.profile_detail_text.configure(state="disabled")

    def save_current_profile(self):
        label = simpledialog.askstring("Профиль", "Название профиля:", parent=self.master)
        if not label:
            return
        config = self._config_from_fields()
        profiles = config.setdefault("profiles", {}).setdefault("items", {})
        key = make_profile_key(label, profiles.keys())
        profiles[key] = capture_assistant_profile(config, label)
        config.setdefault("profiles", {})["active"] = key
        self.settings.save(config)
        self.load_config()
        messagebox.showinfo("Профили", f"Профиль «{label}» сохранён.")

    def apply_selected_profile(self):
        key, profile = self._selected_profile()
        if not key or not profile:
            messagebox.showinfo("Профили", "Выберите профиль.")
            return
        label = profile.get("label") or key
        if not messagebox.askyesno("Профили", f"Применить профиль «{label}»?"):
            return
        config = apply_assistant_profile(self._config_from_fields(), profile)
        config.setdefault("profiles", {})["active"] = key
        self.settings.save(config)
        self.load_config()
        self.reset_chat_runtime()
        messagebox.showinfo("Профили", "Профиль применён. Перезапустите ассистента, если он уже запущен.")

    def export_selected_profile(self):
        key, profile = self._selected_profile()
        if not key or not profile:
            messagebox.showinfo("Профили", "Выберите профиль.")
            return
        default_name = f"assistant_profile_{key}.yaml"
        selected = filedialog.asksaveasfilename(
            title="Экспорт профиля",
            initialfile=default_name,
            defaultextension=".yaml",
            filetypes=[("Файлы YAML", "*.yaml *.yml"), ("Все файлы", "*.*")],
        )
        if not selected:
            return
        Path(selected).write_text(
            yaml.safe_dump({"profile": profile}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        messagebox.showinfo("Профили", f"Профиль экспортирован:\n{selected}")

    def import_profile_ui(self):
        selected = filedialog.askopenfilename(
            title="Импорт профиля",
            filetypes=[("Файлы YAML", "*.yaml *.yml"), ("Все файлы", "*.*")],
        )
        if not selected:
            return
        try:
            data = yaml.safe_load(Path(selected).read_text(encoding="utf-8")) or {}
            profile = data.get("profile", data) if isinstance(data, dict) else {}
            if not isinstance(profile, dict) or not isinstance(profile.get("settings"), dict):
                messagebox.showwarning("Профили", "Файл не похож на профиль ассистента.")
                return
            config = self._config_from_fields()
            profiles = config.setdefault("profiles", {}).setdefault("items", {})
            label = str(profile.get("label") or Path(selected).stem)
            key = make_profile_key(label, profiles.keys())
            profiles[key] = profile
            self.settings.save(config)
            self.load_config()
            messagebox.showinfo("Профили", f"Профиль «{label}» импортирован.")
        except Exception as exc:
            messagebox.showerror("Профили", str(exc))

    def delete_selected_profile(self):
        key, profile = self._selected_profile()
        if not key or not profile:
            messagebox.showinfo("Профили", "Выберите профиль.")
            return
        label = profile.get("label") or key
        if not messagebox.askyesno("Профили", f"Удалить профиль «{label}»?"):
            return
        config = self._config_from_fields()
        profiles = config.setdefault("profiles", {})
        items = profiles.setdefault("items", {})
        items.pop(key, None)
        if profiles.get("active") == key:
            profiles["active"] = ""
        self.settings.save(config)
        self.load_config()

    def refresh_commands_view(self):
        if not hasattr(self, "commands_tree"):
            return
        self.command_items = {}
        for item in self.commands_tree.get_children():
            self.commands_tree.delete(item)

        skills = (self.settings.dataset or {}).get("skills", {}) or {}
        query = ""
        if hasattr(self, "command_search_var"):
            query = self.command_search_var.get().strip().lower()
        dangerous_actions = set((self.settings.config.get("safety", {}) or {}).get("dangerous_actions", []) or [])

        for skill_key, data in skills.items():
            section = data.get("description") or skill_key
            parent = self.commands_tree.insert("", "end", text=section, values=("", "", "", ""))
            inserted = 0
            for command in data.get("commands", []) or []:
                patterns = command.get("patterns", []) or []
                preview = ", ".join(map(str, patterns[:4]))
                if len(patterns) > 4:
                    preview += ", ..."
                action = str(command.get("action", ""))
                source = "Пользовательская" if skill_key == "user_custom" else "Встроенная"
                confirm = "✓" if action in dangerous_actions else ""
                haystack = f"{section} {source} {action} {preview}".lower()
                if query and query not in haystack:
                    continue
                item_id = self.commands_tree.insert(
                    parent,
                    "end",
                    text="",
                    values=(source, confirm, action, preview),
                    tags=("custom",) if skill_key == "user_custom" else (),
                )
                self.command_items[item_id] = {
                    "skill_key": skill_key,
                    "command": command,
                    "action": action,
                    "custom": skill_key == "user_custom",
                }
                inserted += 1
            if inserted:
                self.commands_tree.item(parent, open=bool(query))
            else:
                self.commands_tree.delete(parent)

    def _selected_command_item(self) -> dict | None:
        if not hasattr(self, "commands_tree"):
            return None
        selection = self.commands_tree.selection()
        if not selection:
            return None
        return getattr(self, "command_items", {}).get(selection[0])

    def set_selected_command_confirmation(self, enabled: bool):
        item = self._selected_command_item()
        action = str((item or {}).get("action") or "")
        if not action:
            messagebox.showwarning("Команды", "Выберите конкретную команду с action.")
            return

        try:
            config = self._config_from_fields()
            safety = config.setdefault("safety", {})
            actions = {
                str(value)
                for value in (safety.get("dangerous_actions", []) or [])
                if str(value).strip()
            }
            if enabled:
                actions.add(action)
            else:
                actions.discard(action)
            safety["dangerous_actions"] = sorted(actions)

            self.settings.save(config)
            self.settings.reload()
            self.reset_chat_runtime()
            for field in self.fields:
                field.load(self.settings.config)
            self._refresh_raw()
            self.refresh_commands_view()
            self.refresh_status_view()
            self.refresh_home_view()
            state = "требует подтверждения" if enabled else "не требует подтверждения"
            messagebox.showinfo("Команды", f"{action}: {state}.")
        except Exception as exc:
            messagebox.showerror("Команды", str(exc))

    def _user_commands_path(self) -> Path:
        return getattr(self.settings, "user_commands_path", BASE_DIR / "data" / "user_commands.yaml")

    def _load_user_commands(self) -> dict:
        path = self._user_commands_path()
        if not path.exists():
            return {"skills": {"user_custom": {"description": "Пользовательские фразы", "commands": []}}}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("skills", {})
        data["skills"].setdefault("user_custom", {"description": "Пользовательские фразы", "commands": []})
        data["skills"]["user_custom"].setdefault("description", "Пользовательские фразы")
        data["skills"]["user_custom"].setdefault("commands", [])
        return data

    def _save_user_commands(self, data: dict):
        path = self._user_commands_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            copy2(path, path.with_suffix(".yaml.bak"))
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        self.settings.reload()
        self.reset_chat_runtime()
        self.refresh_commands_view()
        self.refresh_status_view()
        self.refresh_home_view()

    def add_user_command_phrase(self):
        item = self._selected_command_item()
        if not item or not item.get("action"):
            messagebox.showwarning("Команды", "Выберите команду, к которой нужно добавить свою фразу.")
            return

        phrase = simpledialog.askstring("Добавить фразу", "Новая фраза для выбранной команды:", parent=self)
        if phrase is None:
            return
        phrase = phrase.strip().lower()
        if not phrase:
            messagebox.showwarning("Команды", "Фраза не должна быть пустой.")
            return

        normalized_existing = {
            str(pattern).strip().lower()
            for data in ((self.settings.dataset or {}).get("skills", {}) or {}).values()
            for command in (data.get("commands", []) or [])
            for pattern in (command.get("patterns", []) or [])
        }
        if phrase in normalized_existing:
            messagebox.showwarning("Команды", "Такая фраза уже есть в наборе команд.")
            return

        user_data = self._load_user_commands()
        commands = user_data["skills"]["user_custom"]["commands"]
        source_command = item.get("command") or {}
        commands.append({
            "patterns": [phrase],
            "action": item["action"],
            "response": deepcopy(source_command.get("response") or {
                "ru": "Команда выполнена.",
                "en": "Command executed.",
            }),
        })
        self._save_user_commands(user_data)
        messagebox.showinfo("Команды", "Пользовательская фраза добавлена.")

    def delete_user_command_phrase(self):
        item = self._selected_command_item()
        if not item:
            messagebox.showwarning("Команды", "Выберите пользовательскую фразу для удаления.")
            return
        if not item.get("custom"):
            messagebox.showwarning("Команды", "Удалять можно только пользовательские фразы. Встроенные команды защищены.")
            return
        command = item.get("command") or {}
        patterns = command.get("patterns", []) or []
        if not messagebox.askyesno("Команды", "Удалить пользовательскую фразу: " + ", ".join(map(str, patterns)) + "?"):
            return

        user_data = self._load_user_commands()
        commands = user_data["skills"]["user_custom"]["commands"]
        action = item.get("action")
        target_patterns = [str(pattern).strip().lower() for pattern in patterns]
        user_data["skills"]["user_custom"]["commands"] = [
            entry
            for entry in commands
            if not (
                str(entry.get("action", "")) == action
                and [str(pattern).strip().lower() for pattern in (entry.get("patterns", []) or [])] == target_patterns
            )
        ]
        self._save_user_commands(user_data)
        messagebox.showinfo("Команды", "Пользовательская фраза удалена.")

    def test_command_phrase(self):
        phrase = simpledialog.askstring("Проверить фразу", "Введите фразу для проверки:", parent=self)
        if phrase is None:
            return
        phrase = phrase.strip()
        if not phrase:
            return
        try:
            class DryRunSkills:
                def execute(self, *_args, **_kwargs):
                    raise RuntimeError("Dry-run must not execute skills")

            lang = self.settings.config.get("assistant", {}).get("default_language", "ru")
            executor = Executor(self.settings.dataset, DryRunSkills(), config=self.settings.config)
            analysis = executor.analyze(phrase, lang=lang)
            matches = analysis.get("matches", [])
            if not matches:
                messagebox.showinfo(
                    "Проверить фразу",
                    "Совпадений не найдено.\nСтатус: Не распознано\nКоманда не будет выполнена.",
                )
                return
            top = matches[0]
            dangerous = ", ".join(analysis.get("dangerous_actions", [])) or "нет"
            messagebox.showinfo(
                "Проверить фразу",
                f"Статус: {_history_status_label(analysis.get('status'))}\n"
                f"Действие: {top.get('action') or top.get('group')}\n"
                f"Паттерн: {top.get('pattern')}\n"
                f"Оценка: {top.get('score')}\n"
                f"Опасные действия: {dangerous}\n\n"
                "Проверка выполнена без запуска навыка.",
            )
        except Exception as exc:
            messagebox.showerror("Проверить фразу", str(exc))

    def refresh_apps_view(self):
        if not hasattr(self, "apps_tree"):
            return
        for item in self.apps_tree.get_children():
            self.apps_tree.delete(item)

        try:
            from src.skills.apps import get_app_statuses

            statuses = get_app_statuses(self._config_from_fields())
        except Exception as exc:
            self.apps_tree.insert("", "end", text="Ошибка", values=("Ошибка", str(exc), ""), tags=("warn",))
            return

        for item in statuses:
            status = str(item.get("status", "warn"))
            status_label = "Готово" if status == "ok" else "Настроить"
            running = item.get("process_running")
            if running is True:
                status_label += ", запущено"
            elif running is False:
                status_label += ", не запущено"
            self.apps_tree.insert(
                "",
                "end",
                text=str(item.get("display_name") or item.get("key") or ""),
                values=(
                    status_label,
                    str(item.get("path") or item.get("details") or ""),
                    str(item.get("process") or ""),
                ),
                tags=("ok",) if status == "ok" else ("warn",),
            )

    def apply_discovered_app_paths(self):
        try:
            from src.skills.apps import get_app_statuses

            statuses = get_app_statuses(self._config_from_fields(), include_process=False)
        except Exception as exc:
            messagebox.showerror("Приложения", str(exc))
            return

        updated = 0
        for item in statuses:
            key = str(item.get("key") or "")
            path = str(item.get("path") or "")
            if not key or not path or item.get("path_source") != "discovered":
                continue
            self._set_field_value(("apps", key, "path"), path)
            updated += 1

        self.refresh_apps_view()
        if updated:
            messagebox.showinfo("Приложения", f"Подставлено найденных путей: {updated}. Нажмите «Сохранить».")
        else:
            messagebox.showinfo("Приложения", "Новых найденных путей нет.")

    def _storage(self) -> AssistantStorage:
        return AssistantStorage(self.settings.config.get("paths", {}).get("database"))

    def refresh_notes_view(self):
        if not hasattr(self, "notes_tree"):
            return
        for item in self.notes_tree.get_children():
            self.notes_tree.delete(item)

        query = self.notes_search_var.get().strip().lower() if hasattr(self, "notes_search_var") else ""
        try:
            notes = self._storage().list_notes(limit=500)
        except Exception as exc:
            messagebox.showerror("Заметки", str(exc))
            return

        for note in notes:
            text = str(note.get("text", ""))
            if query and query not in text.lower():
                continue
            self.notes_tree.insert(
                "",
                "end",
                values=(note.get("id", ""), note.get("created_at", ""), text),
            )

    def add_note_ui(self):
        text = simpledialog.askstring("Добавить заметку", "Текст заметки:", parent=self)
        if text is None:
            return
        text = text.strip()
        if not text:
            messagebox.showwarning("Заметки", "Заметка не должна быть пустой.")
            return
        try:
            self._storage().add_note(text)
            self.refresh_notes_view()
            self.refresh_status_view()
            self.refresh_home_view()
        except Exception as exc:
            messagebox.showerror("Заметки", str(exc))

    def _selected_tree_id(self, tree: ttk.Treeview, title: str) -> int | None:
        selection = tree.selection()
        if not selection:
            messagebox.showwarning(title, "Выберите запись.")
            return None
        values = tree.item(selection[0], "values")
        try:
            return int(values[0])
        except Exception:
            messagebox.showwarning(title, "Не удалось определить ID выбранной записи.")
            return None

    def delete_selected_note(self):
        note_id = self._selected_tree_id(self.notes_tree, "Заметки")
        if note_id is None:
            return
        if not messagebox.askyesno("Заметки", f"Удалить заметку #{note_id}?"):
            return
        try:
            self._storage().delete_note(note_id)
            self.refresh_notes_view()
            self.refresh_status_view()
            self.refresh_home_view()
        except Exception as exc:
            messagebox.showerror("Заметки", str(exc))

    def clear_notes_ui(self):
        if not messagebox.askyesno("Заметки", "Удалить все заметки?"):
            return
        try:
            count = self._storage().clear_notes()
            self.refresh_notes_view()
            self.refresh_status_view()
            self.refresh_home_view()
            messagebox.showinfo("Заметки", f"Удалено заметок: {count}.")
        except Exception as exc:
            messagebox.showerror("Заметки", str(exc))

    def refresh_reminders_view(self):
        if not hasattr(self, "reminders_tree"):
            return
        for item in self.reminders_tree.get_children():
            self.reminders_tree.delete(item)

        query = self.reminders_search_var.get().strip().lower() if hasattr(self, "reminders_search_var") else ""
        include_completed = self.show_completed_reminders.get() if hasattr(self, "show_completed_reminders") else True
        try:
            reminders = self._storage().list_reminders(limit=500, include_completed=include_completed)
        except Exception as exc:
            messagebox.showerror("Напоминания", str(exc))
            return

        now = datetime.now()
        for item in reminders:
            text = str(item.get("text", ""))
            kind = str(item.get("kind", ""))
            if query and query not in f"{text} {kind}".lower():
                continue
            completed = bool(item.get("completed_at"))
            due_text = str(item.get("due_at", ""))
            overdue = False
            try:
                overdue = not completed and datetime.strptime(due_text, "%Y-%m-%dT%H:%M:%S") < now
            except Exception:
                pass
            status = "Завершено" if completed else ("Просрочено" if overdue else "Ожидает")
            tags = ("done",) if completed else (("overdue",) if overdue else ())
            self.reminders_tree.insert(
                "",
                "end",
                values=(item.get("id", ""), status, kind, due_text, text),
                tags=tags,
            )

    def add_reminder_ui(self):
        text = simpledialog.askstring("Добавить напоминание", "О чём напомнить?", parent=self)
        if text is None:
            return
        text = text.strip()
        if not text:
            messagebox.showwarning("Напоминания", "Текст напоминания не должен быть пустым.")
            return
        due_input = simpledialog.askstring(
            "Добавить напоминание",
            "Когда напомнить? Например: 10m, 2h или 2026-06-04 18:30",
            parent=self,
        )
        if due_input is None:
            return
        due_at = self._parse_ui_due_at(due_input)
        if due_at is None:
            messagebox.showwarning("Напоминания", "Не понял время. Используйте 10m, 2h или YYYY-MM-DD HH:MM.")
            return
        try:
            self._storage().add_reminder("reminder", text, due_at)
            self.refresh_reminders_view()
            self.refresh_status_view()
            self.refresh_home_view()
        except Exception as exc:
            messagebox.showerror("Напоминания", str(exc))

    def _parse_ui_due_at(self, value: str) -> datetime | None:
        value = value.strip().lower()
        if not value:
            return None
        match = re.match(r"^(\d+)\s*(m|min|мин|минут|минуты|минуту)$", value)
        if match:
            return datetime.now() + timedelta(minutes=int(match.group(1)))
        match = re.match(r"^(\d+)\s*(h|hr|hour|hours|ч|час|часа|часов)$", value)
        if match:
            return datetime.now() + timedelta(hours=int(match.group(1)))
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%d.%m.%Y %H:%M", "%H:%M"):
            try:
                parsed = datetime.strptime(value, fmt)
                if fmt == "%H:%M":
                    now = datetime.now()
                    parsed = parsed.replace(year=now.year, month=now.month, day=now.day)
                    if parsed <= now:
                        parsed += timedelta(days=1)
                return parsed
            except ValueError:
                continue
        return None

    def complete_selected_reminder(self):
        reminder_id = self._selected_tree_id(self.reminders_tree, "Напоминания")
        if reminder_id is None:
            return
        try:
            self._storage().complete_reminders([reminder_id])
            self.refresh_reminders_view()
            self.refresh_status_view()
            self.refresh_home_view()
        except Exception as exc:
            messagebox.showerror("Напоминания", str(exc))

    def delete_selected_reminder(self):
        reminder_id = self._selected_tree_id(self.reminders_tree, "Напоминания")
        if reminder_id is None:
            return
        if not messagebox.askyesno("Напоминания", f"Удалить напоминание #{reminder_id}?"):
            return
        try:
            self._storage().delete_reminder(reminder_id)
            self.refresh_reminders_view()
            self.refresh_status_view()
            self.refresh_home_view()
        except Exception as exc:
            messagebox.showerror("Напоминания", str(exc))

    def clear_completed_reminders_ui(self):
        if not messagebox.askyesno("Напоминания", "Удалить все завершенные напоминания?"):
            return
        try:
            count = self._storage().clear_completed_reminders()
            self.refresh_reminders_view()
            self.refresh_status_view()
            self.refresh_home_view()
            messagebox.showinfo("Напоминания", f"Удалено завершенных напоминаний: {count}.")
        except Exception as exc:
            messagebox.showerror("Напоминания", str(exc))

    def refresh_status_view(self):
        if not hasattr(self, "status_tree"):
            return
        for item in self.status_tree.get_children():
            self.status_tree.delete(item)

        rows = self._collect_status_rows()
        failed = sum(1 for row in rows if row[1] == "fail")
        warnings = sum(1 for row in rows if row[1] == "warn")
        if failed:
            summary = f"Есть критичные проблемы: {failed}. Исправьте их перед запуском ассистента."
        elif warnings:
            summary = f"Ассистент может запускаться, но есть предупреждения: {warnings}."
        else:
            summary = "Базовая готовность в порядке. Можно запускать ассистента."
        self.status_summary.configure(text=summary)

        labels = {"ok": "OK", "warn": "Внимание", "fail": "Ошибка"}
        for name, status, details in rows:
            self.status_tree.insert("", "end", text=name, values=(labels.get(status, status), details), tags=(status,))

    def refresh_home_view(self):
        if not hasattr(self, "home_cards"):
            return
        config = self.settings.config
        mode = "Гибрид" if config.get("auto_switch_mode") else ("Офлайн" if config.get("offline_mode") else "Онлайн")
        try:
            storage = AssistantStorage(config.get("paths", {}).get("database"))
            history_count = storage.count_command_history()
        except Exception:
            history_count = 0
        assistant_running = self._assistant_running()
        voice_listening_enabled = is_voice_listening_enabled(default=True)
        if assistant_running and voice_listening_enabled:
            voice_value = "Слушает"
            voice_hint = "Ассистент запущен, микрофон принимает команды."
        elif voice_listening_enabled:
            voice_value = "Включен"
            voice_hint = "Будет слушать после запуска ассистента."
        else:
            voice_value = "Отключен"
            voice_hint = "Текстовый чат продолжает работать."

        cards = {
            "process": (
                "Процесс",
                "Запущен" if assistant_running else "Остановлен",
                f"PID {self.assistant_process.pid}" if assistant_running else "Запустите ассистента одной кнопкой.",
            ),
            "voice": (
                "Голос",
                voice_value,
                voice_hint,
            ),
            "mode": (
                "Режим",
                mode,
                f"Слова активации: {', '.join(sorted(self._wake_words_preview())) or 'не заданы'}",
            ),
            "history": (
                "История",
                str(history_count),
                "Распознанных и текстовых команд.",
            ),
        }
        for key, values in cards.items():
            title, value, hint = self.home_cards[key]
            title.configure(text=values[0])
            value.configure(text=values[1])
            hint.configure(text=values[2])

    def _wake_words_preview(self) -> set[str]:
        words = set()
        config = self.settings.config
        for item in (config.get("wake_words") or {}).values():
            if isinstance(item, list):
                words.update(str(word) for word in item if str(word).strip())
        if config.get("wake_word"):
            words.add(str(config.get("wake_word")))
        return words

    def _collect_status_rows(self) -> list[tuple[str, str, str]]:
        config = self.settings.config
        rows: list[tuple[str, str, str]] = []

        def add(name: str, status: str, details: str):
            rows.append((name, status, details))

        add(
            "Первичная настройка",
            "ok" if config.get("first_run_completed") else "warn",
            "Завершена" if config.get("first_run_completed") else "Откройте мастер первого запуска",
        )

        wake_words = []
        for words in (config.get("wake_words") or {}).values():
            if isinstance(words, list):
                wake_words.extend(str(word).strip() for word in words if str(word).strip())
        if config.get("wake_word"):
            wake_words.append(str(config.get("wake_word")).strip())
        wake_words = sorted(set(filter(None, wake_words)))
        add(
            "Слова активации",
            "ok" if wake_words else "fail",
            ", ".join(wake_words) if wake_words else "Не указано слово активации",
        )

        profiles = config.get("profiles", {}) or {}
        profile_items = profiles.get("items", {}) or {}
        active_profile = profiles.get("active") or "не выбран"
        add("Профили", "ok" if profile_items else "warn", f"профилей: {len(profile_items)}; активный: {active_profile}")

        privacy = config.get("privacy", {}) or {}
        add(
            "Приватность",
            "ok" if privacy.get("redact_secrets_in_exports", True) else "warn",
            (
                f"секреты в экспорте: {'скрываются' if privacy.get('redact_secrets_in_exports', True) else 'не скрываются'}; "
                f"журнал: {'включен' if privacy.get('include_logs_in_reports', True) else 'выключен'}; "
                f"история: {'включена' if privacy.get('include_history_in_reports', False) else 'выключена'}"
            ),
        )

        mode = "hybrid" if config.get("auto_switch_mode") else ("offline" if config.get("offline_mode") else "online")
        add("Режим работы", "ok", _mode_label(mode))

        startup = config.get("startup", {}) or {}
        launch_enabled = bool(startup.get("launch_on_login", False))
        shortcut_exists = is_launch_on_login_enabled()
        add(
            "Автозапуск Windows",
            "ok" if launch_enabled == shortcut_exists else "warn",
            (
                "включен" if launch_enabled and shortcut_exists else
                "выключен" if not launch_enabled and not shortcut_exists else
                "настройка и ярлык автозапуска не совпадают; нажмите «Сохранить»"
            ),
        )
        add(
            "Системный трей",
            "ok" if startup.get("minimize_to_tray_on_close", True) else "warn",
            "крестик сворачивает окно в трей" if startup.get("minimize_to_tray_on_close", True) else "крестик закрывает приложение",
        )

        assistant_running = self._assistant_running()
        voice_listening_enabled = is_voice_listening_enabled(default=True)

        if assistant_running:
            add("Процесс ассистента", "ok", f"Запущен, PID {self.assistant_process.pid}")
        else:
            add("Процесс ассистента", "warn", "Не запущен из GUI")

        if assistant_running and voice_listening_enabled:
            voice_status = "ok"
            voice_details = "ассистент запущен, микрофон принимает команды"
        elif voice_listening_enabled:
            voice_status = "warn"
            voice_details = "включено для следующего запуска; сейчас процесс не запущен"
        else:
            voice_status = "warn"
            voice_details = "отключено; текстовый чат доступен"
        add(
            "Голосовое считывание",
            voice_status,
            voice_details,
        )

        add(
            "Голосовой ответ",
            "ok" if config.get("voice_enabled") else "warn",
            f"{'включен' if config.get('voice_enabled') else 'выключен'}, движок: {config.get('voice_engine')}",
        )

        try:
            import sounddevice as sd

            input_device = sd.default.device[0]
            if input_device is None or input_device < 0:
                add("Микрофон", "fail", "Не выбран микрофон по умолчанию")
            else:
                device = sd.query_devices(input_device, "input")
                name = device.get("name", "неизвестно") if isinstance(device, dict) else str(device)
                add("Микрофон", "ok", str(name))
        except Exception as exc:
            add("Микрофон", "warn", str(exc))

        paths = config.get("paths", {}) or {}
        commands_path = self._resolve_project_path(paths.get("datasets", "data/commands.yaml"))
        add(
            "Файл команд",
            "ok" if commands_path.exists() else "fail",
            str(commands_path),
        )

        try:
            storage = AssistantStorage(paths.get("database"))
            notes = storage.count_notes()
            history = storage.count_command_history()
            pending = len(storage.pending_reminders())
            add("SQLite-база", "ok", f"{storage.db_path}; заметок: {notes}; напоминаний: {pending}; команд: {history}")
        except Exception as exc:
            add("SQLite-база", "fail", str(exc))

        log_file = get_log_file(config)
        add(
            "Журнал",
            "ok" if log_file.parent.exists() else "warn",
            str(log_file),
        )

        models_root = self._resolve_bundle_path(paths.get("stt_models", "data/models/stt"))
        ru_model = models_root / "vosk-model-small-ru-0.22"
        en_model = models_root / "vosk-model-small-en-us-0.15"
        if config.get("offline_mode"):
            status = "ok" if ru_model.exists() or en_model.exists() else "warn"
            details = []
            details.append(f"RU: {'есть' if ru_model.exists() else 'нет'}")
            details.append(f"EN: {'есть' if en_model.exists() else 'нет'}")
            add("Vosk-модели", status, "; ".join(details))
        else:
            add("Vosk-модели", "warn", "Офлайн-режим выключен; модели понадобятся при потере сети")

        assistant = config.get("assistant", {}) or {}
        if assistant.get("ai_enabled"):
            has_keys = bool(assistant.get("yandexgpt_api_key") and assistant.get("yandex_folder_id"))
            add(
                "ЯндексGPT",
                "ok" if has_keys else "fail",
                "Ключи заполнены" if has_keys else "Не заполнен API-ключ или ID каталога",
            )
        else:
            add("ЯндексGPT", "warn", "ИИ-ответы выключены")

        weather = config.get("weather", {}) or {}
        add(
            "Погода",
            "ok" if weather.get("api_key") else "warn",
            f"город: {weather.get('default_city') or 'не задан'}, API-ключ: {'есть' if weather.get('api_key') else 'нет'}",
        )

        news = config.get("news", {}) or {}
        add(
            "Новости",
            "ok" if news.get("api_key") else "warn",
            "API-ключ есть" if news.get("api_key") else "API-ключ не задан",
        )

        filled_secrets = sum(1 for _label, present in secret_status_rows(config) if present)
        add("Секреты", "ok" if filled_secrets else "warn", f"заполнено API-ключей: {filled_secrets}")

        apps = config.get("apps", {}) or {}
        configured_apps = 0
        missing_paths = []
        for app_name, app_config in apps.items():
            path = str((app_config or {}).get("path") or "").strip()
            if path:
                configured_apps += 1
                if not Path(path).exists():
                    missing_paths.append(app_name)
        if missing_paths:
            add("Пути приложений", "warn", "Не найдены: " + ", ".join(missing_paths))
        else:
            add("Пути приложений", "ok" if configured_apps else "warn", f"Заполнено путей: {configured_apps}")

        return rows

    def _resolve_project_path(self, path_value: str) -> Path:
        return resolve_runtime_path(path_value, base="bundle")

    def _resolve_bundle_path(self, path_value: str) -> Path:
        return resolve_runtime_path(path_value, base="bundle")

    def reset_chat_runtime(self):
        self.chat_storage = None
        self.chat_skills = None
        self.chat_executor = None
        self.settings.reload()
        self._append_chat("system", "Контекст чата обновлён.")

    def _ensure_chat_runtime(self):
        if self.chat_executor:
            return
        self.settings.reload()
        config = self.settings.config
        dataset = self.settings.dataset
        self.chat_storage = AssistantStorage(config.get("paths", {}).get("database"))
        context = {
            "config": config,
            "dataset": dataset,
            "storage": self.chat_storage,
            "chat_mode": True,
            "workers": [],
        }
        self.chat_skills = SkillManager(debug=bool(config.get("debug", False)), context=context)
        self.chat_executor = Executor(dataset, self.chat_skills, config=config)

    def send_chat_message(self):
        if not hasattr(self, "chat_input"):
            return
        text = self.chat_input.get().strip()
        if not text:
            return
        self.chat_input.delete(0, tk.END)
        self._send_chat_text(text)

    def send_quick_chat(self, text: str):
        if hasattr(self, "chat_input"):
            self.chat_input.delete(0, tk.END)
        self._send_chat_text(text)

    def _send_chat_text(self, text: str):
        self._append_chat("user", text)

        try:
            self._ensure_chat_runtime()
            lang = self.settings.config.get("assistant", {}).get("default_language", "ru")
            response = self.chat_executor.handle(text, lang=lang)
            response = response or "Команда выполнена."
            self._append_chat("assistant", response)
            self._record_chat_history(text, lang, response)
            self.refresh_notes_view()
            self.refresh_reminders_view()
            self.refresh_status_view()
            self.refresh_home_view()
            self.refresh_history_view()
        except Exception as exc:
            self._append_chat("assistant", f"Ошибка: {exc}")

    def _record_chat_history(self, text: str, lang: str, response: str):
        if not self.chat_storage or not self.chat_executor:
            return
        trace = self.chat_executor.last_trace or {}
        try:
            self.chat_storage.add_command_history(
                source="chat",
                raw_text=text,
                normalized_text=text.strip().lower(),
                language=lang,
                status=str(trace.get("status", "unknown")),
                actions=list(trace.get("actions", [])),
                patterns=list(trace.get("patterns", [])),
                scores=list(trace.get("scores", [])),
                response=response,
            )
        except Exception as exc:
            self._append_chat("system", f"Не удалось записать историю: {exc}")

    def toggle_voice_listening(self):
        enabled = not is_voice_listening_enabled(default=True)
        set_voice_listening_enabled(enabled)
        self._refresh_voice_toggle_button()
        self.refresh_status_view()
        self.refresh_home_view()
        if enabled and self._assistant_running():
            message = "Голосовое считывание команд включено. Ассистент сейчас слушает микрофон."
        elif enabled:
            message = "Голосовое считывание команд включено для следующего запуска ассистента."
        else:
            message = "Голосовое считывание команд отключено. Текстовый чат продолжает работать."
        self._append_chat("system", message)

    def _refresh_voice_toggle_button(self):
        if not hasattr(self, "voice_toggle_button"):
            return
        enabled = is_voice_listening_enabled(default=True)
        if hasattr(self.voice_toggle_button, "draw"):
            self.voice_toggle_button.draw(enabled)
        else:
            self.voice_toggle_button.configure(text="Отключить голос" if enabled else "Включить голос")
        self._refresh_header_status()

    def _poll_voice_history(self):
        try:
            self._append_new_voice_history()
        except Exception:
            pass
        if self.master.winfo_exists():
            self.master.after(1500, self._poll_voice_history)

    def _append_new_voice_history(self):
        if not hasattr(self, "chat_text"):
            return
        storage = AssistantStorage(self.settings.config.get("paths", {}).get("database"))
        rows = list(reversed(storage.list_command_history(limit=30)))
        for row in rows:
            row_id = int(row.get("id", 0) or 0)
            if row_id <= self.last_voice_history_id:
                continue
            self.last_voice_history_id = max(self.last_voice_history_id, row_id)
            if row.get("source", "voice") != "voice":
                continue
            text = row.get("normalized_text") or row.get("raw_text") or ""
            response = row.get("response") or ""
            if text:
                self._append_chat("voice", text)
            if response:
                self._append_chat("assistant", response)

    def _prime_voice_history_position(self):
        try:
            storage = AssistantStorage(self.settings.config.get("paths", {}).get("database"))
            rows = storage.list_command_history(limit=1)
            if rows:
                self.last_voice_history_id = max(self.last_voice_history_id, int(rows[0].get("id", 0) or 0))
        except Exception:
            pass

    def _append_chat(self, role: str, text: str):
        if not hasattr(self, "chat_text"):
            return
        labels = {
            "user": "Вы",
            "voice": "Голос",
            "assistant": self.settings.config.get("assistant", {}).get("name", "Cry"),
            "system": "Система",
        }
        label_tags = {
            "user": "user_label",
            "voice": "voice_label",
            "assistant": "assistant_label",
            "system": "system_label",
        }
        message_tags = {
            "user": "user_message",
            "voice": "voice_message",
            "assistant": "assistant_message",
            "system": "system_message",
        }
        message_tag = message_tags.get(role, "system_message")
        self.chat_text.configure(state="normal")
        self.chat_text.insert(tk.END, f"{labels.get(role, role)}\n", label_tags.get(role, "system_label"))
        self.chat_text.insert(tk.END, f"{text}\n", message_tag)
        self.chat_text.see(tk.END)
        self.chat_text.configure(state="disabled")
        self.refresh_home_view()

    def clear_chat(self):
        if not hasattr(self, "chat_text"):
            return
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.configure(state="disabled")
        self._append_chat("system", "Экран чата очищен.")

    def start_assistant(self):
        if self._assistant_running():
            messagebox.showinfo("Ассистент", "Ассистент уже запущен из этого окна.")
            return

        self.settings.reload()
        if not self.settings.config.get("first_run_completed", False):
            messagebox.showwarning("Ассистент", "Сначала завершите мастер первого запуска.")
            self.open_first_run_wizard()
            return

        try:
            log_file = get_log_file(self.settings.config)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            output_file = log_file.parent / "assistant_stdout.log"
            self.assistant_output_handle = open(output_file, "a", encoding="utf-8", errors="replace")
            self.assistant_output_handle.write("\n--- GUI launch ---\n")
            self.assistant_output_handle.flush()
            command = [sys.executable, "--assistant"] if IS_FROZEN else [sys.executable, "main.py"]
            cwd = EXECUTABLE_DIR if IS_FROZEN else PROJECT_ROOT
            self.assistant_process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=self.assistant_output_handle,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            self._set_assistant_buttons(running=True)
            self.refresh_status_view()
            self.refresh_home_view()
            self.open_log_window()
            messagebox.showinfo("Ассистент", f"Ассистент запущен. PID: {self.assistant_process.pid}")
        except Exception as exc:
            self._close_assistant_output()
            self.assistant_process = None
            messagebox.showerror("Запуск ассистента", str(exc))

    def stop_assistant(self):
        if not self._assistant_running():
            self.assistant_process = None
            self._close_assistant_output()
            self._set_assistant_buttons(running=False)
            self.refresh_status_view()
            self.refresh_home_view()
            return

        process = self.assistant_process
        try:
            if sys.platform == "win32" and hasattr(signal, "CTRL_BREAK_EVENT"):
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        except Exception as exc:
            messagebox.showerror("Остановка ассистента", str(exc))
            return
        finally:
            self.assistant_process = None
            self._close_assistant_output()
            self._set_assistant_buttons(running=False)
            self.refresh_status_view()
            self.refresh_home_view()

        messagebox.showinfo("Ассистент", "Ассистент остановлен.")

    def open_log_window(self):
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.lift()
            self.log_window.refresh()
            return
        self.log_window = LogWindow(self)

    def _poll_assistant_process(self):
        running = self._assistant_running()
        if self.assistant_process and not running:
            self.assistant_process = None
            self._close_assistant_output()
            self.refresh_status_view()
        self._set_assistant_buttons(running=running)
        self.master.after(2000, self._poll_assistant_process)

    def _assistant_running(self) -> bool:
        return bool(self.assistant_process and self.assistant_process.poll() is None)

    def _set_assistant_buttons(self, running: bool):
        if hasattr(self, "start_button"):
            if hasattr(self.start_button, "set_enabled"):
                self.start_button.set_enabled(not running)
            else:
                self.start_button.configure(state="disabled" if running else "normal")
        if hasattr(self, "stop_button"):
            if hasattr(self.stop_button, "set_enabled"):
                self.stop_button.set_enabled(running)
            else:
                self.stop_button.configure(state="normal" if running else "disabled")
        self._refresh_header_status()

    def _refresh_header_status(self):
        if hasattr(self, "process_status_label"):
            running = self._assistant_running()
            self.process_status_label.configure(
                text="Ассистент запущен" if running else "Ассистент остановлен",
                style="Running.Pill.TLabel" if running else "Stopped.Pill.TLabel",
            )
        if hasattr(self, "voice_status_label"):
            enabled = is_voice_listening_enabled(default=True)
            running = self._assistant_running()
            if running and enabled:
                text = "Голос слушает"
                style = "VoiceOn.Pill.TLabel"
            elif enabled:
                text = "Голос готов"
                style = "VoiceOff.Pill.TLabel"
            else:
                text = "Голос отключен"
                style = "VoiceOff.Pill.TLabel"
            self.voice_status_label.configure(
                text=text,
                style=style,
            )

    def _close_assistant_output(self):
        if self.assistant_output_handle:
            try:
                self.assistant_output_handle.close()
            except Exception:
                pass
            self.assistant_output_handle = None

    def _startup_config(self) -> dict:
        startup = self.settings.config.get("startup", {}) if isinstance(self.settings.config, dict) else {}
        return startup if isinstance(startup, dict) else {}

    def _configure_tray(self):
        startup = self._startup_config()
        should_use_tray = bool(
            startup.get("minimize_to_tray_on_close", True)
            or startup.get("start_minimized_to_tray", True)
            or self.start_minimized_requested
        )
        if should_use_tray:
            self.tray.start()

    def _schedule_startup_behaviour(self):
        startup = self._startup_config()
        if bool(startup.get("start_assistant_on_launch", False)):
            self.master.after(650, self._start_assistant_from_startup)
        if self.start_minimized_requested and bool(startup.get("start_minimized_to_tray", True)):
            self.master.after(250, self.hide_to_tray)

    def _start_assistant_from_startup(self):
        if not self.settings.config.get("first_run_completed", False):
            return
        if not self._assistant_running():
            self.start_assistant()

    def _sync_autostart(self, config: dict, silent: bool = True):
        result = apply_startup_config(config)
        if not result.ok and not silent:
            messagebox.showwarning("Автозапуск", result.message)
        self.refresh_status_view()
        return result

    def show_window(self):
        self.master.deiconify()
        self.master.lift()
        try:
            self.master.focus_force()
        except Exception:
            pass

    def hide_to_tray(self):
        if self.tray.start():
            self.master.withdraw()
            return
        self.master.iconify()

    def toggle_assistant_runtime(self):
        if self._assistant_running():
            self.stop_assistant()
        else:
            self.start_assistant()

    def exit_application(self, confirm: bool = True):
        if self._assistant_running():
            if confirm and not messagebox.askyesno("Закрыть Cry", "Ассистент запущен. Остановить его и выйти?"):
                return
            self.stop_assistant()
        self._close_assistant_output()
        self.tray.stop()
        self.master.destroy()

    def on_close(self):
        startup = self._startup_config()
        if bool(startup.get("minimize_to_tray_on_close", True)):
            self.hide_to_tray()
            return
        self.exit_application(confirm=True)

    def refresh_history_view(self):
        if not hasattr(self, "history_tree"):
            return
        self.history_items = {}
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        try:
            storage = AssistantStorage(self.settings.config.get("paths", {}).get("database"))
            source_filter = _history_source_code(self.history_source_var.get()) if hasattr(self, "history_source_var") else None
            status_filter = _history_status_code(self.history_status_var.get()) if hasattr(self, "history_status_var") else None
            rows = storage.list_command_history(
                limit=100,
                source=source_filter,
                status=status_filter,
                query=self.history_query_var.get() if hasattr(self, "history_query_var") else None,
            )
        except Exception as exc:
            messagebox.showerror("История команд", str(exc))
            return

        for row in rows:
            item_id = self.history_tree.insert(
                "",
                "end",
                values=(
                    row.get("created_at", ""),
                    _history_source_label(row.get("source", "voice")),
                    _history_status_label(row.get("status", "")),
                    row.get("normalized_text", ""),
                    row.get("actions", ""),
                    row.get("response", ""),
                ),
            )
            self.history_items[item_id] = row

        if hasattr(self, "history_summary_label"):
            self.history_summary_label.configure(text=f"Показано записей: {len(rows)}")
        self.show_selected_history_details()

    def reset_history_filters(self):
        if hasattr(self, "history_query_var"):
            self.history_query_var.set("")
        if hasattr(self, "history_source_var"):
            self.history_source_var.set(HISTORY_SOURCE_LABELS["all"])
        if hasattr(self, "history_status_var"):
            self.history_status_var.set(HISTORY_STATUS_LABELS["all"])
        self.refresh_history_view()

    def show_selected_history_details(self):
        if not hasattr(self, "history_detail_text"):
            return
        selection = self.history_tree.selection() if hasattr(self, "history_tree") else ()
        row = getattr(self, "history_items", {}).get(selection[0]) if selection else None
        text = self._format_history_detail(row) if row else "Выберите запись истории, чтобы увидеть исходную фразу, действие, шаблон, оценку и ответ."
        self.history_detail_text.configure(state="normal")
        self.history_detail_text.delete("1.0", tk.END)
        self.history_detail_text.insert("1.0", text)
        self.history_detail_text.configure(state="disabled")

    def copy_selected_history(self):
        selection = self.history_tree.selection() if hasattr(self, "history_tree") else ()
        row = getattr(self, "history_items", {}).get(selection[0]) if selection else None
        if not row:
            messagebox.showinfo("История команд", "Выберите запись истории.")
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(self._format_history_detail(row))
        messagebox.showinfo("История команд", "Детали команды скопированы.")

    def _format_history_detail(self, row: dict) -> str:
        return "\n".join([
            f"Время: {row.get('created_at', '')}",
            f"Источник: {_history_source_label(row.get('source', ''))}; статус: {_history_status_label(row.get('status', ''))}; язык: {row.get('language', '')}",
            f"Исходная фраза: {row.get('raw_text', '')}",
            f"Нормализовано: {row.get('normalized_text', '')}",
            f"Действие: {row.get('actions', '') or 'нет действия'}",
            f"Шаблон: {row.get('patterns', '') or 'нет совпадения'}",
            f"Оценка: {row.get('scores', '') or 'нет оценки'}",
            f"Ответ: {row.get('response', '')}",
        ])

    def clear_history(self):
        if not messagebox.askyesno("Очистить историю", "Очистить историю распознанных команд?"):
            return
        try:
            storage = AssistantStorage(self.settings.config.get("paths", {}).get("database"))
            count = storage.clear_command_history()
            self.refresh_history_view()
            messagebox.showinfo("История команд", f"Удалено записей: {count}.")
        except Exception as exc:
            messagebox.showerror("История команд", str(exc))

    def check_config(self):
        problems = []
        config = self.settings.config
        if not config.get("wake_word") and not config.get("wake_words"):
            problems.append("Не настроено слово активации.")
        if config.get("voice_engine") == "silero" and not config.get("voice_speaker"):
            problems.append("Для Silero не выбран спикер.")
        if config.get("assistant", {}).get("ai_enabled"):
            assistant = config.get("assistant", {})
            if not assistant.get("yandexgpt_api_key") or not assistant.get("yandex_folder_id"):
                problems.append("ИИ включён, но API-ключ ЯндексGPT или ID каталога не заполнены.")
        if problems:
            messagebox.showwarning("Проверка конфигурации", "\n".join(problems))
        else:
            messagebox.showinfo("Проверка конфигурации", "Базовая конфигурация выглядит корректно.")

    def _run_diagnostics_text(self) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, "diagnose.py"],
            cwd=str(self.settings.config_path.parent.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    def run_project_diagnostics(self):
        try:
            returncode, output = self._run_diagnostics_text()
            if returncode == 0:
                TextReportWindow(self, "Диагностика проекта", output.strip() or "Проверка пройдена.")
            else:
                TextReportWindow(self, "Диагностика проекта", output.strip() or "Проверка завершилась с ошибкой.")
        except Exception as exc:
            messagebox.showerror("Диагностика проекта", str(exc))

    def show_health_snapshot(self):
        rows = self._collect_status_rows()
        TextReportWindow(self, "Health snapshot", format_health_snapshot(rows))

    def show_crash_summary(self):
        config = self._config_from_fields()
        privacy = config.get("privacy", {}) or {}
        limit = int(privacy.get("crash_summary_lines", 80) or 80)
        TextReportWindow(self, "Crash summary", build_crash_summary(config, limit=limit))

    def show_secret_status(self):
        config = self._config_from_fields()
        lines = [f"{label}: {'заполнен' if present else 'не задан'}" for label, present in secret_status_rows(config)]
        messagebox.showinfo("Секреты", "\n".join(lines))

    def clear_api_keys_ui(self):
        if not messagebox.askyesno(
            "Очистить API-ключи",
            "Будут очищены ключи ЯндексGPT, погоды и новостей. ID каталога Яндекс Облака останется. Продолжить?",
        ):
            return
        config = clear_config_secrets(self._config_from_fields())
        self.settings.save(config)
        self.load_config()
        self.reset_chat_runtime()
        messagebox.showinfo("Секреты", "API-ключи очищены.")

    def export_support_report(self):
        try:
            config = self._config_from_fields()
            if not (config.get("privacy", {}) or {}).get("redact_secrets_in_exports", True):
                if not messagebox.askyesno(
                    "Отчёт поддержки",
                    "Маскировка секретов выключена. Отчёт может содержать API-ключи. Продолжить?",
                ):
                    return
            default_name = f"support_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            selected = filedialog.asksaveasfilename(
                title="Экспорт отчёта для поддержки",
                initialfile=default_name,
                defaultextension=".txt",
                filetypes=[("Текстовый отчёт", "*.txt"), ("Все файлы", "*.*")],
            )
            if not selected:
                return

            try:
                _returncode, diagnostics_output = self._run_diagnostics_text()
            except Exception as exc:
                diagnostics_output = f"Диагностику не удалось запустить: {exc}"

            history_rows = []
            if (config.get("privacy", {}) or {}).get("include_history_in_reports", False):
                try:
                    storage = AssistantStorage(config.get("paths", {}).get("database"))
                    history_rows = storage.list_command_history(limit=30)
                except Exception as exc:
                    history_rows = [{"error": str(exc)}]

            report = build_diagnostic_report(
                config,
                status_rows=self._collect_status_rows(),
                diagnostics_output=diagnostics_output,
                history_rows=history_rows,
            )
            path = write_diagnostic_report(config, report, selected)
            messagebox.showinfo("Отчёт поддержки", f"Отчёт сохранён:\n{path}")
        except Exception as exc:
            messagebox.showerror("Отчёт поддержки", str(exc))

    def show_recent_logs(self):
        log_file = get_log_file(self.settings.config)
        lines = read_recent_log_lines(self.settings.config, limit=30)
        if not lines:
            messagebox.showinfo("Журнал", f"Записей пока нет.\n{log_file}")
            return
        messagebox.showinfo("Последние записи журнала", f"{log_file}\n\n" + "\n".join(lines))

    def clear_logs(self):
        if not messagebox.askyesno("Очистить журнал", "Очистить файл журнала ассистента?"):
            return
        clear_log(self.settings.config)
        messagebox.showinfo("Журнал", "Журнал очищен.")

    def backup_config_ui(self):
        try:
            default_name = f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
            selected = filedialog.asksaveasfilename(
                title="Сохранить резервную копию настроек",
                initialfile=default_name,
                defaultextension=".yaml",
                filetypes=[("Файлы YAML", "*.yaml *.yml"), ("Все файлы", "*.*")],
            )
            if not selected:
                return
            copy2(self.settings.config_path, selected)
            messagebox.showinfo("Резервная копия", f"Настройки сохранены:\n{selected}")
        except Exception as exc:
            messagebox.showerror("Резервная копия", str(exc))

    def restore_config_ui(self):
        selected = filedialog.askopenfilename(
            title="Выберите файл настроек YAML",
            filetypes=[("Файлы YAML", "*.yaml *.yml"), ("Все файлы", "*.*")],
        )
        if not selected:
            return
        if not messagebox.askyesno(
            "Восстановить настройки",
            "Текущий config.yaml будет заменен выбранным файлом. Продолжить?",
        ):
            return
        try:
            loaded = yaml.safe_load(Path(selected).read_text(encoding="utf-8")) or {}
            if not isinstance(loaded, dict):
                messagebox.showwarning("Восстановить настройки", "Выбранный файл не похож на config.yaml.")
                return
            backup_path = self.settings.config_path.with_suffix(".yaml.before_restore")
            if self.settings.config_path.exists():
                copy2(self.settings.config_path, backup_path)
            copy2(selected, self.settings.config_path)
            self.load_config()
            messagebox.showinfo(
                "Восстановить настройки",
                f"Настройки восстановлены. Предыдущая версия сохранена:\n{backup_path}",
            )
        except Exception as exc:
            messagebox.showerror("Восстановить настройки", str(exc))

    def mark_first_run_incomplete(self):
        self._set_nested(self.settings.config, ("first_run_completed",), False)
        self.settings.save()
        self.settings.reload()
        for field in self.fields:
            if field.path == ("first_run_completed",):
                field.variable.set(False)
        self._refresh_raw()
        messagebox.showinfo("Готово", "Мастер первого запуска будет актуален при следующей настройке.")

    def open_first_run_wizard(self):
        FirstRunWizard(self)


class TextReportWindow(tk.Toplevel):
    def __init__(self, app: ConfigApp, title: str, content: str):
        super().__init__(app.master)
        self.title(title)
        set_initial_window_size(self, 1120, 720, 860, 520, top_margin=72)
        self.transient(app.master)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text=title, style="Section.TLabel").grid(column=0, row=0, sticky="w", pady=(0, 8))

        body = ttk.Frame(frame)
        body.grid(column=0, row=1, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self.text = tk.Text(body, wrap="word", font="AppMono", borderwidth=0, highlightthickness=1, highlightbackground=COLORS["line"])
        self.text.grid(column=0, row=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        scrollbar.grid(column=1, row=0, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")

        buttons = ttk.Frame(frame)
        buttons.grid(column=0, row=2, sticky="ew", pady=(10, 0))

        def copy_all():
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo(title, "Текст скопирован.")

        ttk.Button(buttons, text="Копировать", command=copy_all).pack(side="right")
        ttk.Button(buttons, text="Закрыть", command=self.destroy).pack(side="right", padx=(0, 8))


class LogWindow(tk.Toplevel):
    def __init__(self, app: ConfigApp):
        super().__init__(app.master)
        self.app = app
        self.title("Живой журнал Cry")
        set_initial_window_size(self, 1180, 760, 900, 560, top_margin=72)
        self.auto_refresh = tk.BooleanVar(value=True)
        self._build()
        self.refresh()
        self._schedule_refresh()

    def _build(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Журнал ассистента", style="Section.TLabel").pack(side="left")
        ttk.Checkbutton(header, text="Автообновление", variable=self.auto_refresh).pack(side="right")
        ttk.Button(header, text="Обновить", command=self.refresh).pack(side="right", padx=(0, 8))

        self.text = tk.Text(frame, wrap="word", font="AppMono", state="disabled")
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        scrollbar.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scrollbar.set)

    def refresh(self):
        config = self.app.settings.config
        log_file = get_log_file(config)
        output_file = log_file.parent / "assistant_stdout.log"
        sections = []

        lines = read_recent_log_lines(config, limit=160)
        if lines:
            sections.append(f"{log_file}\n" + "\n".join(lines))
        else:
            sections.append(f"{log_file}\nЗаписей в основном журнале пока нет.")

        if output_file.exists():
            stdout_lines = output_file.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            if stdout_lines:
                sections.append(f"{output_file}\n" + "\n".join(stdout_lines))

        content = "\n\n".join(sections)
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.text.see(tk.END)
        self.text.configure(state="disabled")

    def _schedule_refresh(self):
        if not self.winfo_exists():
            return
        if self.auto_refresh.get():
            self.refresh()
        self.after(2000, self._schedule_refresh)


class FirstRunWizard(tk.Toplevel):
    def __init__(self, app: ConfigApp):
        super().__init__(app.master)
        self.app = app
        self.title("Мастер первого запуска Cry")
        set_initial_window_size(self, 1180, 920, 1040, 820, top_margin=72)
        self.transient(app.master)
        self.grab_set()
        self.tts_preview_running = False
        self._build()

    def _build(self):
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Первичная настройка", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Пройдите эти шаги перед обычным запуском ассистента. "
                "Мастер не требует ручного редактирования файла и сохраняет настройки в config.yaml."
            ),
            wraplength=560,
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(6, 16))

        config = self.app.settings.config
        mode = "hybrid" if config.get("auto_switch_mode") else ("offline" if config.get("offline_mode") else "online")

        self.language = tk.StringVar(value=_language_label(self.app.settings.get("assistant", "default_language", default="ru")))
        self.mode = tk.StringVar(value=_mode_label(mode))
        self.wake_word = tk.StringVar(value=self.app.settings.get("wake_word", default="край"))
        self.city = tk.StringVar(value=self.app.settings.get("weather", "default_city", default="Казань"))
        self.voice_enabled = tk.BooleanVar(value=bool(config.get("voice_enabled", True)))
        self.voice_engine = tk.StringVar(value=str(config.get("voice_engine", "silero")))
        self.telegram_path = tk.StringVar(value=config.get("apps", {}).get("telegram", {}).get("path", ""))
        self.discord_path = tk.StringVar(value=config.get("apps", {}).get("discord", {}).get("path", ""))
        self.steam_path = tk.StringVar(value=config.get("apps", {}).get("steam", {}).get("path", ""))
        startup = config.get("startup", {}) or {}
        self.launch_on_login = tk.BooleanVar(value=bool(startup.get("launch_on_login", False)))
        self.start_minimized_to_tray = tk.BooleanVar(value=bool(startup.get("start_minimized_to_tray", True)))
        self.minimize_to_tray_on_close = tk.BooleanVar(value=bool(startup.get("minimize_to_tray_on_close", True)))
        self.start_assistant_on_launch = tk.BooleanVar(value=bool(startup.get("start_assistant_on_launch", False)))

        self._combo(frame, "Язык ассистента", self.language, list(LANGUAGE_CODES.keys()))
        self._combo(frame, "Режим работы", self.mode, list(MODE_CODES.keys()))
        self._entry(frame, "Слово активации", self.wake_word)
        self._entry(frame, "Город для погоды", self.city)
        ttk.Checkbutton(frame, text="Озвучивать ответы ассистента", variable=self.voice_enabled).pack(anchor="w", pady=(8, 3))
        self._combo(frame, "Движок озвучки", self.voice_engine, ["silero", "pyttsx3"])

        startup_panel = ttk.LabelFrame(frame, text="Запуск Windows и трей")
        startup_panel.pack(fill="x", pady=(18, 0))
        ttk.Checkbutton(
            startup_panel,
            text="Запускать Cry вместе с Windows",
            variable=self.launch_on_login,
        ).pack(anchor="w", padx=10, pady=(8, 3))
        ttk.Checkbutton(
            startup_panel,
            text="При автозапуске открывать приложение в трее",
            variable=self.start_minimized_to_tray,
        ).pack(anchor="w", padx=10, pady=3)
        ttk.Checkbutton(
            startup_panel,
            text="Сворачивать окно в трей вместо закрытия",
            variable=self.minimize_to_tray_on_close,
        ).pack(anchor="w", padx=10, pady=3)
        ttk.Checkbutton(
            startup_panel,
            text="Запускать голосового ассистента при открытии приложения",
            variable=self.start_assistant_on_launch,
        ).pack(anchor="w", padx=10, pady=(3, 8))

        apps = ttk.LabelFrame(frame, text="Пути к приложениям")
        apps.pack(fill="x", pady=(18, 0))
        self._path_entry(apps, "Telegram", self.telegram_path)
        self._path_entry(apps, "Discord", self.discord_path)
        self._path_entry(apps, "Steam", self.steam_path)

        self._build_preflight_panel(frame)

        footer = ttk.Frame(frame)
        footer.pack(fill="x", side="bottom", pady=(18, 0))
        self.finish_button = ttk.Button(footer, text="Сохранить и завершить", command=self.finish)
        self.finish_button.pack(side="right")
        ttk.Button(footer, text="Закрыть", command=self.destroy).pack(side="right", padx=(0, 8))
        self.after(100, self.refresh_preflight)

    def _combo(self, parent, label, variable, values):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, width=22).pack(side="left")
        ttk.Combobox(row, textvariable=variable, values=values, state="readonly").pack(side="left", fill="x", expand=True)

    def _entry(self, parent, label, variable):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, width=22).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)

    def _path_entry(self, parent, label, variable):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=5)
        ttk.Label(row, text=label, width=16).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)

        def browse():
            selected = filedialog.askopenfilename(
                title=f"Выберите файл для {label}",
                filetypes=[
                    ("Приложения и ярлыки", "*.exe *.lnk"),
                    ("Все файлы", "*.*"),
                ],
            )
            if selected:
                variable.set(selected)

        ttk.Button(row, text="Выбрать", command=browse).pack(side="left", padx=(8, 0))

    def _build_preflight_panel(self, parent):
        panel = ttk.LabelFrame(parent, text="Готовность к запуску")
        panel.pack(fill="both", expand=True, pady=(18, 0))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        self.preflight_summary = ttk.Label(
            panel,
            text="Нажмите «Обновить чеклист», чтобы проверить готовность.",
            style="Hint.TLabel",
            wraplength=780,
        )
        self.preflight_summary.grid(column=0, row=0, sticky="w", padx=10, pady=(10, 6))

        table = ttk.Frame(panel)
        table.grid(column=0, row=1, sticky="nsew", padx=10)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)

        self.preflight_tree = ttk.Treeview(
            table,
            columns=("status", "details"),
            show="tree headings",
            height=9,
        )
        self.preflight_tree.heading("#0", text="Проверка")
        self.preflight_tree.heading("status", text="Статус")
        self.preflight_tree.heading("details", text="Детали")
        self.preflight_tree.column("#0", width=220, stretch=False)
        self.preflight_tree.column("status", width=120, stretch=False)
        self.preflight_tree.column("details", width=520, stretch=True)
        self.preflight_tree.tag_configure("ok", foreground="#176b35")
        self.preflight_tree.tag_configure("warn", foreground="#8a5a00")
        self.preflight_tree.tag_configure("fail", foreground="#9b1c1c")
        self.preflight_tree.grid(column=0, row=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.preflight_tree.yview)
        scrollbar.grid(column=1, row=0, sticky="ns")
        self.preflight_tree.configure(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(panel)
        buttons.grid(column=0, row=2, sticky="ew", padx=10, pady=10)
        ttk.Button(buttons, text="Обновить чеклист", command=self.refresh_preflight).pack(side="left")
        ttk.Button(buttons, text="Проверить микрофон", command=self.check_microphone).pack(side="left", padx=(8, 0))
        self.tts_preview_button = ttk.Button(buttons, text="Проверить голос", command=self.preview_tts)
        self.tts_preview_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Полная диагностика", command=self.run_diagnostics).pack(side="left", padx=(8, 0))

    def _config_from_form(self, mark_completed: bool = False) -> dict:
        config = deepcopy(self.app.settings.config)
        lang = _language_code(self.language.get())
        mode = _mode_code(self.mode.get())
        wake_word = self.wake_word.get().strip().lower()

        self.app._set_nested(config, ("assistant", "default_language"), lang)
        self.app._set_nested(config, ("language",), "ru-RU" if lang == "ru" else "en-US")
        self.app._set_nested(config, ("wake_word",), wake_word)
        self.app._set_nested(config, ("wake_words", lang), [wake_word] if wake_word else [])
        self.app._set_nested(config, ("weather", "default_city"), self.city.get().strip())
        self.app._set_nested(config, ("offline_mode",), mode == "offline")
        self.app._set_nested(config, ("auto_switch_mode",), mode == "hybrid")
        self.app._set_nested(config, ("voice_enabled",), self.voice_enabled.get())
        self.app._set_nested(config, ("voice_engine",), self.voice_engine.get())
        self.app._set_nested(config, ("startup", "launch_on_login"), self.launch_on_login.get())
        self.app._set_nested(config, ("startup", "start_minimized_to_tray"), self.start_minimized_to_tray.get())
        self.app._set_nested(config, ("startup", "minimize_to_tray_on_close"), self.minimize_to_tray_on_close.get())
        self.app._set_nested(config, ("startup", "start_assistant_on_launch"), self.start_assistant_on_launch.get())
        self.app._set_nested(config, ("apps", "telegram", "path"), self.telegram_path.get().strip())
        self.app._set_nested(config, ("apps", "discord", "path"), self.discord_path.get().strip())
        self.app._set_nested(config, ("apps", "steam", "path"), self.steam_path.get().strip())
        if mark_completed:
            self.app._set_nested(config, ("first_run_completed",), True)
        return config

    def _collect_preflight_rows(self) -> list[tuple[str, str, str]]:
        config = self._config_from_form(mark_completed=False)
        rows: list[tuple[str, str, str]] = []

        def add(name: str, status: str, details: str):
            rows.append((name, status, details))

        if sys.version_info[:2] == (3, 11):
            add("Окружение: Python", "ok", sys.version.split()[0])
        elif sys.version_info >= (3, 11):
            add("Окружение: Python", "warn", f"{sys.version.split()[0]}; целевая версия проекта: 3.11")
        else:
            add("Окружение: Python", "fail", f"{sys.version.split()[0]}; установите Python 3.11")

        required_modules = {
            "yaml": "PyYAML",
            "rapidfuzz": "rapidfuzz",
            "sounddevice": "sounddevice",
            "vosk": "vosk",
        }
        missing = [
            package
            for module_name, package in required_modules.items()
            if importlib.util.find_spec(module_name) is None
        ]
        add(
            "Окружение: зависимости",
            "fail" if missing else "ok",
            "Не установлены: " + ", ".join(missing) if missing else "Основные пакеты доступны",
        )

        wake_word = str(config.get("wake_word") or "").strip()
        add(
            "Команды: слово активации",
            "ok" if wake_word else "fail",
            wake_word if wake_word else "Укажите слово, например «край»",
        )

        paths = config.get("paths", {}) or {}
        commands_path = self.app._resolve_project_path(paths.get("datasets", "data/commands.yaml"))
        add(
            "Команды: файл",
            "ok" if commands_path.exists() else "fail",
            str(commands_path),
        )

        mode = "hybrid" if config.get("auto_switch_mode") else ("offline" if config.get("offline_mode") else "online")
        add("Режим", "ok", _mode_label(mode))

        startup = config.get("startup", {}) or {}
        if startup.get("launch_on_login"):
            add(
                "Windows: автозапуск",
                "ok" if sys.platform == "win32" else "warn",
                "Будет создан ярлык в автозагрузке Windows" if sys.platform == "win32" else "Автозапуск доступен только в Windows",
            )
        else:
            add("Windows: автозапуск", "warn", "Выключен; можно включить позже в настройках")
        add(
            "Трей",
            "ok" if startup.get("minimize_to_tray_on_close", True) else "warn",
            "Окно будет сворачиваться в трей" if startup.get("minimize_to_tray_on_close", True) else "Крестик будет закрывать приложение",
        )

        try:
            import sounddevice as sd

            default_input = sd.default.device[0]
            if default_input is None or default_input < 0:
                add("Голос: микрофон", "fail", "В Windows не выбран микрофон по умолчанию")
            else:
                device = sd.query_devices(default_input, "input")
                name = device.get("name", "неизвестно") if isinstance(device, dict) else str(device)
                add("Голос: микрофон", "ok", str(name))
        except Exception as exc:
            add("Голос: микрофон", "warn", str(exc))

        models_root = self.app._resolve_bundle_path(paths.get("stt_models", "data/models/stt"))
        lang = config.get("assistant", {}).get("default_language", "ru")
        model_dirs = {
            "ru": models_root / "vosk-model-small-ru-0.22",
            "en": models_root / "vosk-model-small-en-us-0.15",
        }
        selected_model = model_dirs.get(lang, model_dirs["ru"])
        if mode == "online":
            add("Распознавание: Vosk", "warn", "Офлайн-модель не обязательна в онлайн-режиме")
        elif selected_model.exists():
            add("Распознавание: Vosk", "ok", str(selected_model))
        else:
            status = "fail" if mode == "offline" else "warn"
            add("Распознавание: Vosk", status, f"Нет модели для языка {lang}: {selected_model}")

        self._add_tts_preflight_row(add, config)

        try:
            storage = AssistantStorage(paths.get("database"))
            add("Данные: SQLite", "ok", str(storage.db_path))
        except Exception as exc:
            add("Данные: SQLite", "fail", str(exc))

        log_file = get_log_file(config)
        add("Сервис: журнал", "ok" if log_file.parent.exists() else "warn", str(log_file))

        assistant = config.get("assistant", {}) or {}
        if assistant.get("ai_enabled"):
            has_keys = bool(assistant.get("yandexgpt_api_key") and assistant.get("yandex_folder_id"))
            add("Интеграции: ЯндексGPT", "ok" if has_keys else "fail", "Ключи заполнены" if has_keys else "Не заполнены ключи")
        else:
            add("Интеграции: ЯндексGPT", "warn", "ИИ-ответы выключены")

        weather = config.get("weather", {}) or {}
        add(
            "Интеграции: погода",
            "ok" if weather.get("api_key") else "warn",
            f"город: {weather.get('default_city') or 'не задан'}; API-ключ: {'есть' if weather.get('api_key') else 'нет'}",
        )

        apps = config.get("apps", {}) or {}
        configured_apps = []
        missing_apps = []
        for app_name, app_config in apps.items():
            path = str((app_config or {}).get("path") or "").strip()
            if not path:
                continue
            configured_apps.append(app_name)
            if not Path(path).exists():
                missing_apps.append(app_name)
        if missing_apps:
            add("Приложения", "warn", "Не найдены: " + ", ".join(missing_apps))
        elif configured_apps:
            add("Приложения", "ok", f"Заполнено путей: {len(configured_apps)}")
        else:
            add("Приложения", "warn", "Пути можно заполнить позже")

        return rows

    def _add_tts_preflight_row(self, add: Callable[[str, str, str], None], config: dict):
        if not config.get("voice_enabled", True):
            add("Голос: ответ", "warn", "Озвучка выключена, ответы будут только текстом")
            return

        engine = str(config.get("voice_engine", "silero"))
        if engine == "pyttsx3":
            status = "ok" if tts_module.pyttsx3 is not None else "warn"
            details = "pyttsx3 доступен" if tts_module.pyttsx3 is not None else "pyttsx3 недоступен, останется текстовый вывод"
            add("Голос: ответ", status, details)
            return

        paths = config.get("paths", {}) or {}
        model_root = self.app._resolve_project_path(paths.get("tts_models", "data/models/tts"))
        lang = config.get("assistant", {}).get("default_language", "ru")
        model_name = "v3_1_ru.pt" if lang == "ru" else "v3_en.pt"
        model_path = model_root / model_name
        model_ready = model_path.exists() and model_path.stat().st_size > 0
        if tts_module.torch is None:
            status = "warn" if tts_module.pyttsx3 is not None else "fail"
            details = "Torch недоступен; fallback pyttsx3" if tts_module.pyttsx3 is not None else "Torch и pyttsx3 недоступны"
            add("Голос: ответ", status, details)
        elif model_ready:
            add("Голос: ответ", "ok", str(model_path))
        elif tts_module.pyttsx3 is not None:
            add("Голос: ответ", "warn", f"Silero не готов: {model_path}; будет fallback pyttsx3")
        else:
            add("Голос: ответ", "warn", f"Silero не готов: {model_path}; останется текстовый вывод")

    def refresh_preflight(self):
        if not hasattr(self, "preflight_tree"):
            return
        for item in self.preflight_tree.get_children():
            self.preflight_tree.delete(item)

        labels = {"ok": "Готово", "warn": "Внимание", "fail": "Исправить"}
        rows = self._collect_preflight_rows()
        counts = {"ok": 0, "warn": 0, "fail": 0}
        for name, status, details in rows:
            counts[status] = counts.get(status, 0) + 1
            self.preflight_tree.insert("", "end", text=name, values=(labels.get(status, status), details), tags=(status,))

        if counts["fail"]:
            summary = f"Нужно исправить: {counts['fail']}. Предупреждений: {counts['warn']}."
        elif counts["warn"]:
            summary = f"Можно запускать, но есть предупреждения: {counts['warn']}."
        else:
            summary = "Все ключевые проверки готовы."
        self.preflight_summary.configure(text=summary)

    def preview_tts(self):
        if self.tts_preview_running:
            return
        config = self._config_from_form(mark_completed=False)
        config["voice_enabled"] = True
        config["offline_mode"] = True
        config["auto_switch_mode"] = False
        lang = config.get("assistant", {}).get("default_language", "ru")
        text = "Привет, я Cry. Голосовой ответ работает." if lang == "ru" else "Hello, I am Cry. Voice output works."
        self.tts_preview_running = True
        self.tts_preview_button.configure(state="disabled")
        self.preflight_summary.configure(text="Проверяю голосовой ответ...")
        threading.Thread(target=self._run_tts_preview, args=(config, text, lang), daemon=True).start()

    def _run_tts_preview(self, config: dict, text: str, lang: str):
        try:
            tts = tts_module.HybridTTS(config)
            tts.speak(text, lang=lang)
            if tts.model is None and tts.engine is None:
                message = "Озвучка недоступна, ассистент сможет отвечать текстом."
            else:
                message = f"Проверка голоса завершена. Использован движок: {tts.current_engine}."
            self.after(0, self._finish_tts_preview, message, False)
        except Exception as exc:
            self.after(0, self._finish_tts_preview, str(exc), True)

    def _finish_tts_preview(self, message: str, failed: bool):
        self.tts_preview_running = False
        if self.winfo_exists():
            self.tts_preview_button.configure(state="normal")
            self.preflight_summary.configure(text=message)
            self.refresh_preflight()
            if failed:
                messagebox.showerror("Проверка голоса", message)

    def check_microphone(self):
        try:
            import sounddevice as sd

            default_input = sd.default.device[0]
            if default_input is None or default_input < 0:
                messagebox.showwarning("Проверка микрофона", "В Windows не выбран микрофон по умолчанию.")
                return
            device = sd.query_devices(default_input, "input")
            name = device.get("name", "неизвестно") if isinstance(device, dict) else str(device)
            messagebox.showinfo("Проверка микрофона", f"Микрофон доступен:\n{name}")
        except Exception as exc:
            messagebox.showerror("Проверка микрофона", str(exc))
        self.refresh_preflight()

    def run_diagnostics(self):
        try:
            command = [sys.executable, "--diagnose"] if IS_FROZEN else [sys.executable, "diagnose.py"]
            cwd = EXECUTABLE_DIR if IS_FROZEN else PROJECT_ROOT
            result = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            if result.returncode == 0:
                messagebox.showinfo("Проверка проекта", output or "Проверка пройдена.")
            else:
                messagebox.showwarning("Проверка проекта", output or "Проверка завершилась с ошибкой.")
        except Exception as exc:
            messagebox.showerror("Проверка проекта", str(exc))
        self.refresh_preflight()

    def finish(self):
        wake_word = self.wake_word.get().strip().lower()
        if not wake_word:
            messagebox.showwarning("Мастер первого запуска", "Укажите слово активации.")
            return

        config = self._config_from_form(mark_completed=True)
        self.app.settings.save(config)
        self.app.load_config()
        self.app._sync_autostart(self.app.settings.config, silent=False)
        messagebox.showinfo("Мастер первого запуска", "Настройки сохранены.")
        self.destroy()


def main():
    enable_high_dpi_awareness()
    root = tk.Tk()
    ConfigApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
