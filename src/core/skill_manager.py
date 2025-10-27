import importlib, os
from pathlib import Path


class SkillManager:
    def __init__(self, skills_path: str = "src/skills", debug: bool = True, context: dict = None):
        self.skills_path = Path(skills_path)
        self.debug = debug
        self.skills = {}
        self.context = context or {}
        self.load_all_skills()

    def log(self, msg: str):
        if self.debug:
            print(f"[SkillManager] {msg}")
            
    def reload(self):
        """Перезагружает все навыки (например, после обновления файлов)."""
        self.log("🔄 Все навыки перезагружены")
        self.load_all_skills()

    def load_all_skills(self):
        self.skills.clear()
        importlib.invalidate_caches()
        if not self.skills_path.exists():
            return
        for file in os.listdir(self.skills_path):
            if file.endswith(".py") and file != "__init__.py":
                name = file[:-3]
                module_name = f"src.skills.{name}"
                try:
                    module = importlib.import_module(module_name)
                    importlib.reload(module)
                    self.skills[name] = module
                    self.log(f"OK {name}")
                except Exception as e:
                    self.log(f"ERROR {name}: {e}")

    def execute(self, action: str, text: str = None):
        if not action:
            return "⚠️ Действие не указано."
        
        if "." in action:
            mod, fn = action.split(".", 1)
            module = self.skills.get(mod)
            if not module or not hasattr(module, fn):
                return f"❌ Не найдено: {action}"
            return self._safe_call(getattr(module, fn), action, text)
        
        for module in self.skills.values():
            fn = getattr(module, action, None)
            if callable(fn):
                return self._safe_call(fn, action, text)
        return f"⚠️ Навык '{action}' не найден."

    def _safe_call(self, fn, action, text):
        try:
            return fn(action=action, text=text, **self.context)
        except Exception as e:
            return f"⚠️ Ошибка в {action}: {e}"



# import importlib
# import os
# from pathlib import Path
# from functools import lru_cache


# class SkillManager:
#     """
#     Гибкий менеджер навыков.
#     Автоматически загружает, обновляет и вызывает функции из src/skills.
#     Поддерживает передачу аргументов, языка и контекста ассистента.
#     """

#     def __init__(self, skills_path: str = "src/skills", debug: bool = True, context: dict = None):
#         self.skills_path = Path(skills_path)
#         self.debug = debug
#         self.skills = {}
#         self.context = context or {}
#         self.load_all_skills()

#     def log(self, message: str):
#         if self.debug:
#             print(f"[DEBUG SkillManager] {message}")

#     # ========================= ЗАГРУЗКА НАВЫКОВ =========================

#     def load_all_skills(self):
#         """Загружает все навыки из директории src/skills."""
#         self.skills.clear()

#         if not self.skills_path.exists():
#             self.log(f"❌ Директория навыков не найдена: {self.skills_path}")
#             return

#         for file in os.listdir(self.skills_path):
#             if file.endswith(".py") and file != "__init__.py":
#                 name = file[:-3]
#                 module_name = f"src.skills.{name}"

#                 try:
#                     module = importlib.import_module(module_name)
#                     importlib.reload(module)
#                     self.skills[name] = module
#                     self.log(f"✅ Загружен навык: {name}")
#                 except Exception as e:
#                     print(f"[ERROR] Не удалось загрузить навык '{name}': {e}")

#     def reload(self):
#         """Перезагружает все навыки (например, после обновления файлов)."""
#         self.load_all_skills()
#         self.log("🔄 Все навыки перезагружены")

#     # ========================= ВЫПОЛНЕНИЕ ДЕЙСТВИЙ =========================

#     def execute(self, action: str, text: str = None):
#         """
#         Выполняет действие (например 'system.shutdown' или просто 'shutdown').
#         Передаёт функции все возможные данные: text, language, context, args, kwargs.
#         """
#         if not action:
#             return "⚠️ Действие не указано."
        
#         if not text:
#             return "⚠️ Text not found in SkillManager!"

#         # Собираем базовый контекст


#         def _call_function(fn):
#             context = {
#                 "action": action, 
#                 "text": text,
#                 **self.context,  # общий контекст (конфиг, имя пользователя, микрофон и т.п.)
#             }
#             try:
#                 return fn(**context)

#             except Exception as e:
#                 return f"⚠️ Ошибка при выполнении '{action}': {e}"

#         # Если указано module.function
#         if "." in action:
#             mod, func = action.split(".", 1)
#             module = self.skills.get(mod)

#             if not module:
#                 return f"❌ Навык '{mod}' не найден."

#             fn = getattr(module, func, None)
#             if not callable(fn):
#                 return f"⚠️ В '{mod}' нет функции '{func}'."

#             return _call_function(fn)

#         # Поиск по всем модулям
#         for name, module in self.skills.items():
#             fn = getattr(module, action, None)
#             if callable(fn):
#                 return _call_function(fn)

#         return f"❌ Действие '{action}' не найдено."

#     # ========================= СПРАВКА =========================

#     @lru_cache(maxsize=32)
#     def list_skills(self):
#         """Возвращает список всех загруженных навыков."""
#         return list(self.skills.keys())
