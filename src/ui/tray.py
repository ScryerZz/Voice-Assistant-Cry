from __future__ import annotations

import threading
import tkinter as tk
from typing import Any, Callable

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None


class TrayController:
    def __init__(self, root: tk.Tk, app: Any):
        self.root = root
        self.app = app
        self.icon = None
        self.thread: threading.Thread | None = None

    @property
    def available(self) -> bool:
        return pystray is not None and Image is not None and ImageDraw is not None

    def start(self) -> bool:
        if self.icon is not None:
            return True
        if not self.available:
            return False

        self.icon = pystray.Icon(
            "CryAssistant",
            self._create_icon_image(),
            "Голосовой ассистент Cry",
            self._menu(),
        )
        self.thread = threading.Thread(target=self.icon.run, daemon=True, name="tray_icon")
        self.thread.start()
        return True

    def stop(self) -> None:
        icon = self.icon
        self.icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass

    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem("Показать окно", self._call(self.app.show_window)),
            pystray.MenuItem("Скрыть в трей", self._call(self.app.hide_to_tray)),
            pystray.MenuItem("Запустить/остановить ассистента", self._call(self.app.toggle_assistant_runtime)),
            pystray.MenuItem("Выход", self._call(lambda: self.app.exit_application(confirm=False))),
        )

    def _call(self, callback: Callable[[], None]):
        def handler(_icon=None, _item=None):
            try:
                self.root.after(0, callback)
            except Exception:
                pass

        return handler

    def _create_icon_image(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((6, 6, 58, 58), fill=(0, 122, 255, 255))
        draw.ellipse((18, 16, 46, 44), outline=(255, 255, 255, 255), width=5)
        draw.rectangle((42, 34, 52, 40), fill=(0, 122, 255, 255))
        draw.arc((16, 12, 52, 50), start=42, end=320, fill=(255, 255, 255, 255), width=5)
        return image
