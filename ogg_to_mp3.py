# -*- coding: utf-8 -*-
"""
EasyConvert v1.1.2 — drag & drop any audio into MP3.

Modern minimalist two-panel UI:
  * left  = input queue (file + size + status + per-file progress)
  * right = output list (produced MP3s, open folder)

Conversion core: direct ffmpeg-subprocess with real per-file progress,
cancellation, metadata preservation. i18n RU/EN. settings.json, convert.log,
update check via GitHub API.
"""

import os
import sys
import re
import json
import threading
import subprocess
import datetime
import urllib.request
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import tkinterdnd2  # noqa: F401
    _HAS_DND = True
except Exception:
    _HAS_DND = False

APP_NAME = "EasyConvert"
APP_VERSION = "1.1.2"
REPO_SLUG = "MarkHaker/EasyConvert"

# Palette — clean dark (Material / macOS-ish)
C_BG = "#1e1e2e"          # window background (deep blue-grey)
C_BG_RAISED = "#252537"   # cards / raised surfaces
C_BG_INSET = "#181825"    # inputs / lists
C_BORDER = "#313244"
C_BORDER_SOFT = "#2a2a3c"
C_TEXT = "#cdd6f4"
C_TEXT_DIM = "#7f7fa0"
C_TEXT_FAINT = "#5b5b8a"
C_ACCENT = "#bb86fc"      # soft purple
C_ACCENT_2 = "#03dac6"    # teal — Start
C_DANGER = "#cf6679"      # red — Stop
C_OK = "#a6e3a1"
C_WARN = "#f9e2af"
C_INFO = "#89b4fa"

FONT = "Segoe UI"
FONT_MONO = "Cascadia Mono"

# Audio extensions used to filter files when a folder is dropped.
AUDIO_EXTS = {
    ".ogg", ".oga", ".opus", ".spx", ".wav", ".mp3", ".mp2", ".mp1", ".flac",
    ".aac", ".m4a", ".m4b", ".m4p", ".m4r", ".wma", ".ac3", ".ec3", ".dts",
    ".aiff", ".aif", ".aifc", ".amr", ".awb", ".voc", ".vox", ".gsm", ".tta",
    ".ape", ".wv", ".shn", ".ofr", ".pac", ".tak", ".la", ".qcp", ".sln",
    ".dss", ".msv", ".dvf", ".ivs", ".mmf", ".iklax", ".webm", ".mka",
    ".mp4", ".mkv", ".mov", ".avi", ".ts", ".m2ts", ".mts", ".3gp", ".3g2",
    ".caf", ".w64", ".sd2", ".iff", ".8svx", ".paf", ".fap", ".mat4", ".mat5",
    ".pvf", ".xi", ".htk", ".sds", ".avr", ".wavex", ".rf64", ".bwf", ".amb",
    ".svx", ".nist", ".sph", ".txw", ".smp", ".pcm", ".raw", ".vqf",
    ".dca", ".dtshd", ".thd", ".mlp", ".eac3",
}
LIMITED_EXTS = {".mid", ".midi", ".rmi", ".kar", ".mod", ".s3m", ".xm", ".it",
                ".mtm", ".669", ".far", ".stm", ".med", ".okt", ".psm", ".ptm",
                ".umx", ".amf", ".dsm", ".mdl", ".mt2", ".j2b", ".mptm", ".gdm"}


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
def is_frozen():
    return getattr(sys, "frozen", False)


def get_base_dir():
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_meipass():
    return getattr(sys, "_MEIPASS", None)


def find_ffmpeg():
    candidates = []
    mp = get_meipass()
    if mp:
        candidates.append(mp)
    candidates.append(get_base_dir())
    for c in candidates:
        p = os.path.join(c, "ffmpeg.exe")
        if os.path.isfile(p):
            return p
    return "ffmpeg"


def find_ffprobe():
    candidates = []
    mp = get_meipass()
    if mp:
        candidates.append(mp)
    candidates.append(get_base_dir())
    for c in candidates:
        p = os.path.join(c, "ffprobe.exe")
        if os.path.isfile(p):
            return p
    return "ffprobe"


def resource_path(rel):
    base = get_meipass() or get_base_dir()
    return os.path.join(base, rel)


def get_today_folder_name():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def get_or_create_today_folder():
    folder = os.path.join(get_base_dir(), get_today_folder_name())
    os.makedirs(folder, exist_ok=True)
    return folder


def get_settings_path():
    return os.path.join(get_base_dir(), "settings.json")


def get_log_path():
    return os.path.join(get_base_dir(), "convert.log")


def get_output_folder_for_file(input_path, settings):
    mode = settings.get("out_mode", "date")
    if mode == "source":
        return os.path.dirname(os.path.abspath(input_path))
    elif mode == "custom":
        custom = settings.get("custom_out", "")
        if custom:
            os.makedirs(custom, exist_ok=True)
            return custom
    return get_or_create_today_folder()


def resolve_output_path(input_path, settings):
    out_dir = get_output_folder_for_file(input_path, settings)
    name_no_ext = os.path.splitext(os.path.basename(input_path))[0]
    out_path = os.path.join(out_dir, name_no_ext + ".mp3")
    if not os.path.exists(out_path):
        return out_path, "new"
    policy = settings.get("collision", "suffix")
    if policy == "overwrite":
        return out_path, "overwrite"
    elif policy == "skip":
        return out_path, "skip"
    i = 1
    while True:
        cand = os.path.join(out_dir, f"{name_no_ext}_{i}.mp3")
        if not os.path.exists(cand):
            return cand, "new"
        i += 1


def collect_audio_files_from_paths(paths, recursive):
    result = []
    for p in paths:
        if os.path.isfile(p):
            if os.path.splitext(p)[1].lower() in AUDIO_EXTS or os.path.splitext(p)[1].lower() in LIMITED_EXTS:
                result.append(p)
        elif os.path.isdir(p):
            if recursive:
                for root, _dirs, files in os.walk(p):
                    for f in files:
                        if os.path.splitext(f)[1].lower() in AUDIO_EXTS or os.path.splitext(f)[1].lower() in LIMITED_EXTS:
                            result.append(os.path.join(root, f))
            else:
                for f in os.listdir(p):
                    fp = os.path.join(p, f)
                    if os.path.isfile(fp) and (os.path.splitext(f)[1].lower() in AUDIO_EXTS or os.path.splitext(f)[1].lower() in LIMITED_EXTS):
                        result.append(fp)
    seen = set()
    out = []
    for f in result:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def human_size(n):
    try:
        n = int(n)
    except Exception:
        return "—"
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n // 1024} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


# --------------------------------------------------------------------------- #
# Settings + logging
# --------------------------------------------------------------------------- #
DEFAULT_SETTINGS = {
    "bitrate": "320k",
    "channels": "2",
    "keep_native_rate": False,
    "normalize": False,
    "out_mode": "date",
    "custom_out": "",
    "collision": "suffix",
    "keep_tags": True,
    "workers": 0,
    "recursive": True,
    "lang": None,
    "geometry": None,
}


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        if os.path.isfile(get_settings_path()):
            with open(get_settings_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            s.update(data)
    except Exception:
        pass
    return s


def save_settings(settings):
    try:
        with open(get_settings_path(), "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def setup_logger():
    logger = logging.getLogger("easyconvert")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        fh = logging.FileHandler(get_log_path(), encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s",
                                          datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


log = setup_logger()


# --------------------------------------------------------------------------- #
# i18n
# --------------------------------------------------------------------------- #
def default_lang():
    try:
        import locale as _l
        try:
            loc = _l.getlocale()[0] or _l.getdefaultlocale()[0] or "ru"
        except Exception:
            loc = _l.getdefaultlocale()[0] or "ru"
    except Exception:
        loc = "ru"
    return "ru" if str(loc).lower().startswith("ru") else "en"


I18N = {
    "ru": {
        "title": "EasyConvert — Аудио в MP3",
        "input_panel": "ОЧЕРЕДЬ ФАЙЛОВ",
        "output_panel": "ГОТОВЫЕ MP3",
        "drop_hint": "Перетащи файлы или папку сюда",
        "drop_sub": "или нажми + ниже",
        "add_files": "Добавить файлы",
        "add_folder": "Добавить папку",
        "clear": "Очистить",
        "open_folder": "Открыть папку",
        "start": "СТАРТ",
        "stop": "СТОП",
        "audio": "Аудио",
        "manage": "Управление",
        "paths": "Пути",
        "bitrate": "Битрейт",
        "channels": "Каналы",
        "workers": "Потоков",
        "out_mode": "Папка вывода",
        "collision": "При совпадении",
        "keep_native": "Сохранять исх. частоту/каналы",
        "keep_tags": "Сохранять теги/метаданные",
        "normalize": "Нормализация громкости (loudnorm)",
        "recursive": "Рекурсивно по подпапкам",
        "check_update": "Проверить обновления",
        "status_ready": "Готов к работе. Папка: {}",
        "status_added": "Добавлено файлов: {}",
        "status_empty_queue": "Очередь пуста — добавь файлы",
        "status_processing": "Конвертация [{}/{}]: {}",
        "status_done": "Готово: {}/{} — ошибок: {}, пропущено: {}",
        "status_cancelled": "Остановлено пользователем",
        "status_no_update": "У вас последняя версия (v{})",
        "status_update_available": "Доступна новая версия: {} (текущая v{}). Открываю…",
        "status_update_fail": "Не удалось проверить обновления: {}",
        "col_name": "Имя",
        "col_size": "Размер",
        "col_status": "Статус",
        "col_progress": "Прогресс",
        "col_path": "Папка",
        "st_pending": "ожидание",
        "st_processing": "конвертация…",
        "st_done": "готово",
        "st_failed": "ошибка",
        "st_skipped": "пропуск",
        "st_overwritten": "перезапись",
        "log_conv_start": "Начало конвертации: {} файл(ов)",
        "log_conv_ok": "[OK] {}/{}  {}  ->  {}",
        "log_conv_fail": "[FAIL] {}/{}  {}: {}",
        "log_conv_skip": "[SKIP] {}/{}  {} (уже существует)",
        "err_not_found": "Файл не найден",
        "err_decode": "ffmpeg не смог декодировать файл",
        "err_limited": "Формат требует звукового шрифта — не поддерживается",
        "err_unknown": "Ошибка",
        "msg_pick_files": "Выбери аудио файлы",
        "msg_pick_folder": "Выбери папку с аудио",
        "msg_pick_output": "Выбери папку для вывода MP3",
        "all_files": "Все файлы",
        "audio_files": "Аудио файлы",
        "confirm_clear": "Очистить список?",
        "about": "О программе",
        "about_text": "EasyConvert v{}\nDrag & drop аудио в MP3.\n\nGitHub: https://github.com/{}".format(APP_VERSION, REPO_SLUG),
    },
    "en": {
        "title": "EasyConvert — Audio to MP3",
        "input_panel": "FILE QUEUE",
        "output_panel": "CONVERTED MP3s",
        "drop_hint": "Drop files or a folder here",
        "drop_sub": "or click + below",
        "add_files": "Add files",
        "add_folder": "Add folder",
        "clear": "Clear",
        "open_folder": "Open folder",
        "start": "START",
        "stop": "STOP",
        "audio": "Audio",
        "manage": "Control",
        "paths": "Paths",
        "bitrate": "Bitrate",
        "channels": "Channels",
        "workers": "Workers",
        "out_mode": "Output folder",
        "collision": "On clash",
        "keep_native": "Keep orig. freq/chan.",
        "keep_tags": "Keep tags/metadata",
        "normalize": "Loudness normalization (loudnorm)",
        "recursive": "Recursive subfolders",
        "check_update": "Check for updates",
        "status_ready": "Ready. Output: {}",
        "status_added": "Added {} file(s)",
        "status_empty_queue": "Queue is empty — add some files",
        "status_processing": "Converting [{}/{}]: {}",
        "status_done": "Done: {}/{} — errors: {}, skipped: {}",
        "status_cancelled": "Cancelled by user",
        "status_no_update": "You're on the latest version (v{})",
        "status_update_available": "New version available: {} (current v{}). Opening…",
        "status_update_fail": "Update check failed: {}",
        "col_name": "Name",
        "col_size": "Size",
        "col_status": "Status",
        "col_progress": "Progress",
        "col_path": "Folder",
        "st_pending": "pending",
        "st_processing": "processing…",
        "st_done": "done",
        "st_failed": "failed",
        "st_skipped": "skipped",
        "st_overwritten": "overwritten",
        "log_conv_start": "Conversion started: {} file(s)",
        "log_conv_ok": "[OK] {}/{}  {}  ->  {}",
        "log_conv_fail": "[FAIL] {}/{}  {}: {}",
        "log_conv_skip": "[SKIP] {}/{}  {} (already exists)",
        "err_not_found": "File not found",
        "err_decode": "ffmpeg could not decode the file",
        "err_limited": "Format needs a soundfont — unsupported",
        "err_unknown": "Error",
        "msg_pick_files": "Pick audio files",
        "msg_pick_folder": "Pick a folder with audio",
        "msg_pick_output": "Pick output folder for MP3s",
        "all_files": "All files",
        "audio_files": "Audio files",
        "confirm_clear": "Clear the list?",
        "about": "About",
        "about_text": "EasyConvert v{}\nDrag & drop audio to MP3.\n\nGitHub: https://github.com/{}".format(APP_VERSION, REPO_SLUG),
    },
}


def tr(lang, key, *args):
    t = I18N.get(lang, I18N["en"]).get(key, key)
    try:
        return t.format(*args) if args else t
    except Exception:
        return t


# --------------------------------------------------------------------------- #
# ffprobe + conversion core
# --------------------------------------------------------------------------- #
_CREATEFLAGS = 0
if sys.platform == "win32":
    _CREATEFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0


def ffprobe_duration(probe_path, file_path):
    try:
        cmd = [probe_path, "-v", "error", "-show_entries",
               "format=duration", "-of",
               "default=noprint_wrappers=1:nokey=1", file_path]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           creationflags=_CREATEFLAGS, timeout=30)
        out = (r.stdout or "").strip()
        if out:
            return float(out.splitlines()[0])
    except Exception:
        pass
    return None


class Converter:
    def __init__(self, settings, lang, on_progress=None):
        self.settings = settings
        self.lang = lang
        self.on_progress = on_progress
        self.cancel_event = threading.Event()
        self._proc = None
        self._lock = threading.Lock()

    def cancel(self):
        self.cancel_event.set()
        with self._lock:
            p = self._proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass

    def _build_args(self, in_path, out_path):
        s = self.settings
        args = [find_ffmpeg(), "-hide_banner", "-loglevel", "error",
                "-nostdin", "-y", "-i", in_path, "-vn"]
        if s.get("keep_tags", True):
            args += ["-map_metadata", "0", "-map_metadata", "0:s:0"]
        af = []
        if s.get("normalize", False):
            af.append("loudnorm")
        if af:
            args += ["-af", ",".join(af)]
        args += ["-c:a", "libmp3lame", "-b:a", s.get("bitrate", "320k")]
        if not s.get("keep_native_rate", False):
            args += ["-ar", "44100"]
            ch = str(s.get("channels", "2"))
            if ch in ("1", "2"):
                args += ["-ac", ch]
        args += [out_path]
        return args

    def convert_file(self, in_path, index, total):
        L = self.lang
        if not os.path.isfile(in_path):
            return "failed", tr(L, "err_not_found"), None
        ext = os.path.splitext(in_path)[1].lower()
        if ext in LIMITED_EXTS:
            return "failed", tr(L, "err_limited"), None

        out_path, action = resolve_output_path(in_path, self.settings)
        if action == "skip":
            return "skipped", tr(L, "log_conv_skip", index, total,
                                 os.path.basename(in_path)), out_path

        duration = ffprobe_duration(find_ffprobe(), in_path)
        args = self._build_args(in_path, out_path)
        log.info("ffmpeg %s", " ".join(args))

        try:
            self._proc = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                creationflags=_CREATEFLAGS,
            )
        except Exception as e:
            return "failed", tr(L, "err_unknown") + f": {e}", None

        stderr_lines = []
        try:
            assert self._proc.stderr is not None
            for line in self._proc.stderr:
                if self.cancel_event.is_set():
                    break
                stderr_lines.append(line)
                m = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
                if m and duration:
                    h, mi, se = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    cur = h * 3600 + mi * 60 + se
                    pct = max(0, min(99, int(cur / max(duration, 0.001) * 100)))
                    if self.on_progress:
                        self.on_progress(index, total, pct, os.path.basename(in_path))
        except Exception:
            pass
        finally:
            try:
                self._proc.wait(timeout=10)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass

        if self.cancel_event.is_set():
            try:
                if out_path and os.path.exists(out_path):
                    os.remove(out_path)
            except Exception:
                pass
            return "cancelled", tr(L, "status_cancelled"), None

        if self._proc.returncode != 0:
            tail = "".join(stderr_lines[-5:]).strip()
            return "failed", tr(L, "err_decode") + f" ({ext})" + (f": {tail}" if tail else ""), None

        if self.on_progress:
            self.on_progress(index, total, 100, os.path.basename(in_path))
        return "done", tr(L, "log_conv_ok", index, total,
                          os.path.basename(out_path),
                          os.path.basename(os.path.dirname(out_path))), out_path


# --------------------------------------------------------------------------- #
# Custom widgets
# --------------------------------------------------------------------------- #
class FlatButton(tk.Frame):
    """A flat, rounded-feeling button (frame + label)."""

    def __init__(self, parent, text, command, bg=C_BG_RAISED, fg=C_TEXT,
                 accent=None, font_size=10, bold=False, padx=14, pady=8,
                 icon=None, width=None):
        super().__init__(parent, bg=bg)
        self._bg = bg
        self._bg_hover = self._lighten(bg)
        self._fg = fg
        fnt = (FONT, font_size, "bold" if bold else "normal")
        label_text = (icon + "  " + text) if icon else text
        self.lbl = tk.Label(self, text=label_text, fg=fg, bg=bg, font=fnt,
                           cursor="hand2")
        self.lbl.pack(fill="both", expand=True, padx=padx, pady=pady)
        if width:
            self.config(width=width)
            self.lbl.config(width=width)
        self._cmd = command
        for w in (self, self.lbl):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_click(self, e):
        if self._cmd:
            self._cmd()

    def _on_enter(self, e):
        self.config(bg=self._bg_hover)
        self.lbl.config(bg=self._bg_hover)

    def _on_leave(self, e):
        self.config(bg=self._bg)
        self.lbl.config(bg=self._bg)

    def _lighten(self, hexcolor):
        try:
            r = int(hexcolor[1:3], 16); g = int(hexcolor[3:5], 16); b = int(hexcolor[5:7], 16)
            r = min(255, r + 18); g = min(255, g + 18); b = min(255, b + 18)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hexcolor

    def set_text(self, text, icon=None):
        label_text = (icon + "  " + text) if icon else text
        self.lbl.config(text=label_text)

    def set_state(self, enabled):
        st = "normal" if enabled else "disabled"
        self.lbl.config(state=st)


class IconLabelButton(tk.Frame):
    """Compact square icon button (e.g. + file, + folder, trash)."""

    def __init__(self, parent, icon, command, bg=C_BG_RAISED, fg=C_TEXT,
                 size=36, tooltip=None):
        super().__init__(parent, bg=bg, width=size, height=size)
        self._bg = bg
        self._bg_hover = self._lighten(bg)
        self._cmd = command
        self.lbl = tk.Label(self, text=icon, fg=fg, bg=bg,
                            font=(FONT, 13), cursor="hand2")
        self.lbl.place(relx=0.5, rely=0.5, anchor="center")
        for w in (self, self.lbl):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_click(self, e):
        if self._cmd:
            self._cmd()

    def _on_enter(self, e):
        self.config(bg=self._bg_hover); self.lbl.config(bg=self._bg_hover)

    def _on_leave(self, e):
        self.config(bg=self._bg); self.lbl.config(bg=self._bg)

    def _lighten(self, hexcolor):
        try:
            r = int(hexcolor[1:3], 16); g = int(hexcolor[3:5], 16); b = int(hexcolor[5:7], 16)
            r = min(255, r + 18); g = min(255, g + 18); b = min(255, b + 18)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hexcolor

    def set_state(self, enabled):
        st = "normal" if enabled else "disabled"
        self.lbl.config(state=st)


class LangSwitch(tk.Frame):
    """Compact EN/RU pill switch."""

    def __init__(self, parent, lang, on_change):
        super().__init__(parent, bg=C_BG_RAISED)
        self._on_change = on_change
        self._lang = lang
        self.btn_ru = tk.Label(self, text="RU", bg=(C_ACCENT if lang == "ru" else C_BG_RAISED),
                               fg=(C_BG if lang == "ru" else C_TEXT_DIM),
                               font=(FONT, 9, "bold"), cursor="hand2", width=3)
        self.btn_en = tk.Label(self, text="EN", bg=(C_ACCENT if lang == "en" else C_BG_RAISED),
                               fg=(C_BG if lang == "en" else C_TEXT_DIM),
                               font=(FONT, 9, "bold"), cursor="hand2", width=3)
        self.btn_ru.pack(side="left", padx=2, pady=2)
        self.btn_en.pack(side="left", padx=2, pady=2)
        self.btn_ru.bind("<Button-1>", lambda e: self._set("ru"))
        self.btn_en.bind("<Button-1>", lambda e: self._set("en"))

    def _set(self, lng):
        if lng == self._lang:
            return
        self._lang = lng
        self.btn_ru.config(bg=(C_ACCENT if lng == "ru" else C_BG_RAISED),
                           fg=(C_BG if lng == "ru" else C_TEXT_DIM))
        self.btn_en.config(bg=(C_ACCENT if lng == "en" else C_BG_RAISED),
                           fg=(C_BG if lng == "en" else C_TEXT_DIM))
        if self._on_change:
            self._on_change(lng)


class ThinProgressbar(tk.Canvas):
    """A thin, flat progress bar drawn on a canvas — modern look."""

    def __init__(self, parent, height=6, bg=C_BG_INSET, fill=C_ACCENT_2, **kw):
        super().__init__(parent, bg=bg, height=height, highlightthickness=0, **kw)
        self._value = 0.0
        self._fill = fill
        self._bg = bg
        self._height = height
        self.bind("<Configure>", lambda e: self._draw())

    def set_color(self, fill):
        self._fill = fill
        self._draw()

    def set_value(self, pct):
        self._value = max(0.0, min(100.0, float(pct)))
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return
        # track
        self.create_rectangle(0, 0, w, h, fill=self._bg, outline="")
        # fill
        fw = int(w * self._value / 100.0)
        if fw > 0:
            self.create_rectangle(0, 0, fw, h, fill=self._fill, outline="")


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #
if _HAS_DND:
    import tkinterdnd2
    _BaseRoot = tkinterdnd2.Tk
else:
    _BaseRoot = tk.Tk


class DropWindow(_BaseRoot):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.lang = self.settings.get("lang") or default_lang()

        self.title(tr(self.lang, "title"))
        self.configure(bg=C_BG)
        self.minsize(860, 620)

        try:
            self.iconbitmap(default=resource_path("ico.ico"))
        except Exception:
            pass

        geo = self.settings.get("geometry") or "980x720"
        try:
            self.geometry(geo)
        except Exception:
            self.geometry("980x720")

        self.queue = []
        self.queue_lock = threading.Lock()
        self.processing = False
        self.converter = None
        self._worker_thread = None
        self._cancel_requested = False

        self._build_ui()
        self._apply_lang()
        self._set_status(tr(self.lang, "status_ready", get_today_folder_name()), "idle")

        if _HAS_DND:
            # whole window is a drop target
            self.drop_target_register(tkinterdnd2.DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop_root)
            self.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            self.dnd_bind("<<DropLeave>>", self._on_drop_leave)
            # also the input list area
            self.input_card.drop_target_register(tkinterdnd2.DND_FILES)
            self.input_card.dnd_bind("<<Drop>>", self._on_drop)
            self.input_card.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            self.input_card.dnd_bind("<<DropLeave>>", self._on_drop_leave)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- UI construction ----
    def _build_ui(self):
        self._configure_style()

        # Root container with padding
        root = tk.Frame(self, bg=C_BG)
        root.pack(fill="both", expand=True, padx=14, pady=14)

        # ---- Header ----
        header = tk.Frame(root, bg=C_BG)
        header.pack(fill="x", pady=(0, 14))

        # Logo glyph + title
        logo = tk.Label(header, text="\u266B", fg=C_ACCENT, bg=C_BG,
                       font=(FONT, 22, "bold"))
        logo.pack(side="left", padx=(0, 10))
        self.title_lbl = tk.Label(header, text=APP_NAME, fg=C_TEXT, bg=C_BG,
                                  font=(FONT, 18, "bold"))
        self.title_lbl.pack(side="left")

        # Right side: update btn + lang switch
        right = tk.Frame(header, bg=C_BG)
        right.pack(side="right")
        self.update_btn = IconLabelButton(right, "\u21bb", self.check_update,
                                          bg=C_BG_RAISED, fg=C_TEXT, size=32)
        self.update_btn.pack(side="left", padx=(0, 8))
        self.lang_switch = LangSwitch(right, self.lang, on_change=self._switch_lang)
        self.lang_switch.pack(side="left")

        # ---- Two-column workspace ----
        work = tk.Frame(root, bg=C_BG)
        work.pack(fill="both", expand=True)
        work.columnconfigure(0, weight=1, uniform="col")
        work.columnconfigure(1, weight=1, uniform="col")
        work.rowconfigure(1, weight=1)

        # Input card (left)
        self.input_card = tk.Frame(work, bg=C_BG_RAISED, highlightbackground=C_BORDER,
                                   highlightthickness=1, bd=0)
        self.input_card.grid(row=1, column=0, sticky="nsew", padx=(0, 7))
        self.input_card.columnconfigure(0, weight=1)
        self.input_card.rowconfigure(1, weight=1)

        in_hdr = tk.Frame(self.input_card, bg=C_BG_RAISED)
        in_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        in_icon = tk.Label(in_hdr, text="\u266B", fg=C_ACCENT, bg=C_BG_RAISED,
                           font=(FONT, 12, "bold"))
        in_icon.pack(side="left", padx=(0, 8))
        self.in_title = tk.Label(in_hdr, text=tr(self.lang, "input_panel"),
                                 fg=C_TEXT, bg=C_BG_RAISED,
                                 font=(FONT, 10, "bold"))
        self.in_title.pack(side="left")
        # input action icons (right of header)
        in_act = tk.Frame(in_hdr, bg=C_BG_RAISED)
        in_act.pack(side="right")
        self.add_files_btn = IconLabelButton(in_act, "+", self.choose_files,
                                             bg=C_BG_INSET, fg=C_OK, size=28)
        self.add_files_btn.pack(side="left", padx=2)
        self.add_folder_btn = IconLabelButton(in_act, "\u25A3", self.choose_folder,
                                              bg=C_BG_INSET, fg=C_INFO, size=28)
        self.add_folder_btn.pack(side="left", padx=2)
        self.clear_input_btn = IconLabelButton(in_act, "\u2715", self.clear_input,
                                               bg=C_BG_INSET, fg=C_DANGER, size=28)
        self.clear_input_btn.pack(side="left", padx=2)

        # Empty-state label (shows when queue empty)
        self.empty_label = tk.Label(self.input_card, text=tr(self.lang, "drop_hint"),
                                    fg=C_TEXT_FAINT, bg=C_BG_RAISED,
                                    font=(FONT, 12, "bold"), justify="center")
        self.empty_sub = tk.Label(self.input_card, text=tr(self.lang, "drop_sub"),
                                  fg=C_TEXT_FAINT, bg=C_BG_RAISED,
                                  font=(FONT, 9))
        # Place them centered, will toggle visibility

        # Input tree
        self.input_tree = ttk.Treeview(self.input_card,
                                      columns=("name", "size", "status", "progress"),
                                      show="tree", selectmode="extended",
                                      style="Queue.Treeview")
        self.input_tree.heading("#0", text="")
        self.input_tree.heading("name", text=tr(self.lang, "col_name"))
        self.input_tree.heading("size", text=tr(self.lang, "col_size"))
        self.input_tree.heading("status", text=tr(self.lang, "col_status"))
        self.input_tree.heading("progress", text=tr(self.lang, "col_progress"))
        self.input_tree.column("#0", width=28, stretch=False, anchor="center")
        self.input_tree.column("name", width=200, anchor="w")
        self.input_tree.column("size", width=64, anchor="e")
        self.input_tree.column("status", width=80, anchor="center")
        self.input_tree.column("progress", width=70, anchor="center")
        self.input_tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        isb = ttk.Scrollbar(self.input_card, orient="vertical",
                           command=self.input_tree.yview, style="Thin.Vertical.TScrollbar")
        self.input_tree.configure(yscrollcommand=isb.set)
        isb.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne", width=8)
        self._bind_tree_dnd_scroll()

        # tag colors for statuses
        self.input_tree.tag_configure("pending", foreground=C_TEXT_DIM)
        self.input_tree.tag_configure("processing", foreground=C_WARN)
        self.input_tree.tag_configure("done", foreground=C_OK)
        self.input_tree.tag_configure("failed", foreground=C_DANGER)
        self.input_tree.tag_configure("skipped", foreground=C_INFO)
        self.input_tree.tag_configure("overwritten", foreground=C_OK)

        # Output card (right)
        self.output_card = tk.Frame(work, bg=C_BG_RAISED, highlightbackground=C_BORDER,
                                    highlightthickness=1, bd=0)
        self.output_card.grid(row=1, column=1, sticky="nsew", padx=(7, 0))
        self.output_card.columnconfigure(0, weight=1)
        self.output_card.rowconfigure(1, weight=1)

        out_hdr = tk.Frame(self.output_card, bg=C_BG_RAISED)
        out_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        out_icon = tk.Label(out_hdr, text="\u2713", fg=C_ACCENT_2, bg=C_BG_RAISED,
                            font=(FONT, 12, "bold"))
        out_icon.pack(side="left", padx=(0, 8))
        self.out_title = tk.Label(out_hdr, text=tr(self.lang, "output_panel"),
                                  fg=C_TEXT, bg=C_BG_RAISED,
                                  font=(FONT, 10, "bold"))
        self.out_title.pack(side="left")
        out_act = tk.Frame(out_hdr, bg=C_BG_RAISED)
        out_act.pack(side="right")
        self.open_folder_btn = IconLabelButton(out_act, "\u25A2", self.open_output_folder,
                                                bg=C_BG_INSET, fg=C_INFO, size=28)
        self.open_folder_btn.pack(side="left", padx=2)
        self.clear_output_btn = IconLabelButton(out_act, "\u2715", self.clear_output,
                                                bg=C_BG_INSET, fg=C_DANGER, size=28)
        self.clear_output_btn.pack(side="left", padx=2)

        # Output tree
        self.output_tree = ttk.Treeview(self.output_card,
                                       columns=("name", "path", "size"),
                                       show="tree", selectmode="extended",
                                       style="Queue.Treeview")
        self.output_tree.heading("#0", text="")
        self.output_tree.heading("name", text=tr(self.lang, "col_name"))
        self.output_tree.heading("path", text=tr(self.lang, "col_path"))
        self.output_tree.heading("size", text=tr(self.lang, "col_size"))
        self.output_tree.column("#0", width=28, stretch=False, anchor="center")
        self.output_tree.column("name", width=170, anchor="w")
        self.output_tree.column("path", width=210, anchor="w")
        self.output_tree.column("size", width=64, anchor="e")
        self.output_tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        osb = ttk.Scrollbar(self.output_card, orient="vertical",
                            command=self.output_tree.yview, style="Thin.Vertical.TScrollbar")
        self.output_tree.configure(yscrollcommand=osb.set)
        osb.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne", width=8)
        self.output_tree.bind("<Double-1>", self._open_selected_output)

        # ---- Center action bar (Start / Stop) ----
        actbar = tk.Frame(root, bg=C_BG)
        actbar.pack(fill="x", pady=(14, 10))
        self.start_btn = FlatButton(actbar, tr(self.lang, "start"),
                                    self.start_processing, bg=C_ACCENT_2, fg=C_BG,
                                    font_size=12, bold=True, padx=28, pady=10,
                                    icon="\u25B6")
        self.start_btn.pack(side="left", padx=(0, 10))
        self.stop_btn = FlatButton(actbar, tr(self.lang, "stop"),
                                   self.stop_processing, bg=C_DANGER, fg=C_BG,
                                   font_size=12, bold=True, padx=28, pady=10,
                                   icon="\u25A0")
        self.stop_btn.pack(side="left")

        # ---- Settings panel (compact, no frame) ----
        sf = tk.Frame(root, bg=C_BG_RAISED, highlightbackground=C_BORDER_SOFT,
                      highlightthickness=1, bd=0)
        sf.pack(fill="x", pady=(0, 10))
        sf.columnconfigure(0, weight=1)

        # Row 1: grouped sections
        srow1 = tk.Frame(sf, bg=C_BG_RAISED)
        srow1.pack(fill="x", padx=12, pady=(10, 4))

        # Audio group
        self.bitrate_var = tk.StringVar(value=self.settings.get("bitrate", "320k"))
        self.channels_var = tk.StringVar(value=str(self.settings.get("channels", "2")))
        self._setting_group(srow1, tr(self.lang, "audio"), [
            ("bitrate", self._combobox_var(self.bitrate_var,
                          ["320k", "256k", "192k", "128k", "96k"], 6)),
            ("channels", self._combobox_var(self.channels_var, ["1", "2"], 4)),
        ])
        # Manage group
        import multiprocessing as _mp
        maxw = max(1, _mp.cpu_count() or 4)
        self.workers_var = tk.IntVar(value=self.settings.get("workers", 0) or min(4, maxw))
        self._setting_group(srow1, tr(self.lang, "manage"), [
            ("workers", self._spinbox_var(self.workers_var, 1, maxw, 4)),
        ])
        # Paths group
        self.out_mode_var = tk.StringVar(value=self.settings.get("out_mode", "date"))
        self.col_var = tk.StringVar(value=self.settings.get("collision", "suffix"))
        self._setting_group(srow1, tr(self.lang, "paths"), [
            ("out_mode", self._combobox_var(self.out_mode_var,
                          ["date", "source", "custom"], 12)),
            ("collision", self._combobox_var(self.col_var,
                          ["suffix", "overwrite", "skip"], 10)),
        ])
        # choose output button
        self.out_custom_btn = IconLabelButton(srow1, "\u25A2", self.choose_custom_out,
                                             bg=C_BG_INSET, fg=C_INFO, size=30)
        self.out_custom_btn.pack(side="left", padx=(6, 0), pady=4)

        # Row 2: checkboxes
        srow2 = tk.Frame(sf, bg=C_BG_RAISED)
        srow2.pack(fill="x", padx=12, pady=(4, 10))
        self.keep_native_var = tk.BooleanVar(value=self.settings.get("keep_native_rate", False))
        self.keep_tags_var = tk.BooleanVar(value=self.settings.get("keep_tags", True))
        self.normalize_var = tk.BooleanVar(value=self.settings.get("normalize", False))
        self.recursive_var = tk.BooleanVar(value=self.settings.get("recursive", True))
        self._cb_widgets = []
        for var, key in [
            (self.keep_native_var, "keep_native"),
            (self.keep_tags_var, "keep_tags"),
            (self.normalize_var, "normalize"),
            (self.recursive_var, "recursive"),
        ]:
            cb = tk.Checkbutton(srow2, text=tr(self.lang, key), variable=var,
                                bg=C_BG_RAISED, fg=C_TEXT, selectcolor=C_BG_INSET,
                                activebackground=C_BG_RAISED, activeforeground=C_TEXT,
                                font=(FONT, 9), bd=0, highlightthickness=0,
                                cursor="hand2")
            cb.pack(side="left", padx=(0, 18))
            self._cb_widgets.append((cb, key))

        # ---- Bottom: overall progress + status bar ----
        bottom = tk.Frame(root, bg=C_BG)
        bottom.pack(fill="x")

        self.progress = ThinProgressbar(bottom, height=8, bg=C_BG_INSET, fill=C_ACCENT_2)
        self.progress.pack(fill="x", pady=(0, 6))

        statusbar = tk.Frame(bottom, bg=C_BG)
        statusbar.pack(fill="x")
        self.status_icon = tk.Label(statusbar, text="\u25CF", fg=C_TEXT_FAINT,
                                    bg=C_BG, font=(FONT, 10))
        self.status_icon.pack(side="left", padx=(0, 8))
        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(statusbar, textvariable=self.status_var,
                                     fg=C_TEXT_DIM, bg=C_BG, font=(FONT, 9),
                                     anchor="w", justify="left")
        self.status_label.pack(side="left", fill="x", expand=True)
        self.ver_label = tk.Label(statusbar, text=f"v{APP_VERSION}", fg=C_TEXT_FAINT,
                                  bg=C_BG, font=(FONT, 8))
        self.ver_label.pack(side="right")

        # Initial empty-state placement
        self._toggle_empty_state()

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # Treeview (queue style)
        style.configure("Queue.Treeview", background=C_BG_INSET, foreground=C_TEXT,
                        fieldbackground=C_BG_INSET, borderwidth=0, rowheight=26)
        style.configure("Queue.Treeview.Heading", background=C_BG_RAISED,
                        foreground=C_TEXT_DIM, borderwidth=0,
                        font=(FONT, 9, "bold"), relief="flat")
        style.map("Queue.Treeview.Heading", background=[("active", C_BORDER)])
        style.map("Queue.Treeview", background=[("selected", C_BORDER)])
        # Thin scrollbar
        style.configure("Thin.Vertical.TScrollbar", background=C_BORDER,
                        troughcolor=C_BG_INSET, borderwidth=0, arrowcolor=C_BG_INSET,
                        arrowsize=0, gripcount=0, width=8)
        style.map("Thin.Vertical.TScrollbar", background=[("active", C_ACCENT)])

    def _bind_tree_dnd_scroll(self):
        # Mouse wheel scrolling for input tree
        def _wheel(event):
            self.input_tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.input_tree.bind("<MouseWheel>", _wheel)

    # ---- setting group helpers ----
    def _setting_group(self, parent, title, items):
        g = tk.Frame(parent, bg=C_BG_RAISED)
        g.pack(side="left", padx=(0, 18))
        title_lbl = tk.Label(g, text=title.upper(), fg=C_TEXT_FAINT, bg=C_BG_RAISED,
                             font=(FONT, 7, "bold"))
        title_lbl.pack(anchor="w", padx=2, pady=(0, 2))
        if not hasattr(self, "_group_titles"):
            self._group_titles = []
        self._group_titles.append((title_lbl, title))
        for key, widget in items:
            row = tk.Frame(g, bg=C_BG_RAISED)
            row.pack(anchor="w", pady=1)
            widget.pack(in_=row, side="left")

    def _combobox_var(self, var, values, width):
        cb = ttk.Combobox(textvariable=var, values=values, width=width,
                          state="readonly", style="Queue.Treeview")
        return cb

    def _spinbox_var(self, var, frm, to, width):
        sp = ttk.Spinbox(textvariable=var, from_=frm, to=to, width=width,
                         style="Queue.Treeview")
        return sp

    def _out_mode_label(self, key):
        m = {"date": {"ru": "по дате", "en": "by date"},
             "source": {"ru": "рядом с исх.", "en": "next to source"},
             "custom": {"ru": "выбрать…", "en": "choose…"}}
        return m.get(key, {}).get(self.lang, key)

    def _col_label(self, key):
        m = {"suffix": {"ru": "добавить _1", "en": "add _1"},
             "overwrite": {"ru": "перезаписать", "en": "overwrite"},
             "skip": {"ru": "пропустить", "en": "skip"}}
        return m.get(key, {}).get(self.lang, key)

    def _spinbox(self, value, frm, to, width):
        var = tk.IntVar(value=value)
        sp = ttk.Spinbox(textvariable=var, from_=frm, to=to, width=width,
                         style="Queue.Treeview")
        sp.__ec_var = var
        return sp

    def _setting_group_titles_widgets(self):
        # Returns list of (group_title_label, group_frame) in order: audio, manage, paths
        result = []
        sf = self.winfo_children()  # not robust; use stored refs instead
        return result

    # ---- language ----
    def _switch_lang(self, new_lang):
        if new_lang == self.lang:
            return
        self.lang = new_lang
        self.settings["lang"] = new_lang
        save_settings(self.settings)
        self._apply_lang()
        self._set_status(tr(self.lang, "status_ready", get_today_folder_name()), "idle")

    def _apply_lang(self):
        L = self.lang
        self.title(tr(L, "title"))
        self.in_title.config(text=tr(L, "input_panel"))
        self.out_title.config(text=tr(L, "output_panel"))
        self.empty_label.config(text=tr(L, "drop_hint"))
        self.empty_sub.config(text=tr(L, "drop_sub"))
        self.start_btn.set_text(tr(L, "start"), icon="\u25B6")
        self.stop_btn.set_text(tr(L, "stop"), icon="\u25A0")
        self.input_tree.heading("name", text=tr(L, "col_name"))
        self.input_tree.heading("size", text=tr(L, "col_size"))
        self.input_tree.heading("status", text=tr(L, "col_status"))
        self.input_tree.heading("progress", text=tr(L, "col_progress"))
        self.output_tree.heading("name", text=tr(L, "col_name"))
        self.output_tree.heading("path", text=tr(L, "col_path"))
        self.output_tree.heading("size", text=tr(L, "col_size"))
        # checkbox labels
        for cb, key in self._cb_widgets:
            cb.config(text=tr(L, key))
        # setting group titles + combobox values (rebuild out_mode display)
        # rebuild group titles
        groups = [w for w in self.winfo_children()]
        self._refresh_setting_group_titles()

    def _refresh_setting_group_titles(self):
        L = self.lang
        for title_lbl, title_key in getattr(self, "_group_titles", []):
            title_lbl.config(text=title_key.upper())

    # ---- empty state ----
    def _toggle_empty_state(self):
        has_items = len(self.input_tree.get_children()) > 0
        if has_items:
            try:
                self.empty_label.place_forget()
                self.empty_sub.place_forget()
            except Exception:
                pass
        else:
            self.empty_label.place(relx=0.5, rely=0.42, anchor="center")
            self.empty_sub.place(relx=0.5, rely=0.60, anchor="center")
            self.empty_label.lift()
            self.empty_sub.lift()

    # ---- DnD ----
    def _on_drop_enter(self, event):
        try:
            self.input_card.config(highlightbackground=C_ACCENT)
        except Exception:
            pass

    def _on_drop_leave(self, event):
        try:
            self.input_card.config(highlightbackground=C_BORDER)
        except Exception:
            pass

    def _on_drop(self, event):
        self._on_drop_leave(event)
        files = parse_dropped_files(event.data)
        self.add_paths(files)

    def _on_drop_root(self, event):
        files = parse_dropped_files(event.data)
        self.add_paths(files)

    # ---- file picking ----
    def choose_files(self):
        files = filedialog.askopenfilenames(
            title=tr(self.lang, "msg_pick_files"),
            filetypes=[(tr(self.lang, "audio_files"), " ".join("*" + e for e in sorted(AUDIO_EXTS))),
                       (tr(self.lang, "all_files"), "*.*")],
        )
        if files:
            self.add_paths(list(files))

    def choose_folder(self):
        folder = filedialog.askdirectory(title=tr(self.lang, "msg_pick_folder"))
        if folder:
            self.add_paths([folder])

    def choose_custom_out(self):
        d = filedialog.askdirectory(title=tr(self.lang, "msg_pick_output"))
        if d:
            self.settings["custom_out"] = d
            self.out_mode_var.set("custom")
            save_settings(self.settings)

    def add_paths(self, paths):
        files = collect_audio_files_from_paths(paths, self.recursive_var.get())
        added = 0
        with self.queue_lock:
            existing = set(self.queue)
            for f in files:
                if f not in existing:
                    self.queue.append(f)
                    existing.add(f)
                    added += 1
        self._refresh_input_tree()
        if added:
            self._set_status(tr(self.lang, "status_added", added), "idle")
        else:
            self._set_status(tr(self.lang, "status_empty_queue"), "idle")

    def _refresh_input_tree(self):
        for iid in self.input_tree.get_children():
            self.input_tree.delete(iid)
        with self.queue_lock:
            items = list(self.queue)
        for i, f in enumerate(items):
            try:
                size = human_size(os.path.getsize(f))
            except Exception:
                size = "—"
            self.input_tree.insert("", "end", iid=str(i),
                                   text="",
                                   values=(os.path.basename(f), size,
                                           tr(self.lang, "st_pending"), "—"),
                                   tags=("pending",))
        self._toggle_empty_state()

    def clear_input(self):
        if not self.queue and not self.input_tree.get_children():
            return
        if not messagebox.askyesno(APP_NAME, tr(self.lang, "confirm_clear")):
            return
        with self.queue_lock:
            self.queue.clear()
        self._refresh_input_tree()
        self._set_status(tr(self.lang, "status_ready", get_today_folder_name()), "idle")

    def clear_output(self):
        if not self.output_tree.get_children():
            return
        if not messagebox.askyesno(APP_NAME, tr(self.lang, "confirm_clear")):
            return
        for iid in self.output_tree.get_children():
            self.output_tree.delete(iid)

    def open_output_folder(self):
        sel = self.output_tree.selection()
        if sel:
            item = self.output_tree.item(sel[0])
            path = item["values"][1]
            try:
                os.startfile(path)
                return
            except Exception:
                pass
        try:
            os.startfile(get_or_create_today_folder())
        except Exception as e:
            self._set_status(f"open folder failed: {e}", "error")

    def _open_selected_output(self, event):
        sel = self.output_tree.selection()
        if not sel:
            return
        item = self.output_tree.item(sel[0])
        name = item["values"][0]
        folder = item["values"][1]
        full = os.path.join(folder, name + ("" if name.lower().endswith(".mp3") else ".mp3"))
        try:
            os.startfile(full)
        except Exception:
            try:
                os.startfile(folder)
            except Exception:
                pass

    # ---- processing ----
    def _collect_settings_from_ui(self):
        self.settings["bitrate"] = self.bitrate_var.get()
        self.settings["channels"] = self.channels_var.get()
        try:
            self.settings["workers"] = int(self.workers_var.get() or 1)
        except Exception:
            self.settings["workers"] = 1
        self.settings["out_mode"] = self.out_mode_var.get()
        self.settings["collision"] = self.col_var.get()
        self.settings["keep_native_rate"] = bool(self.keep_native_var.get())
        self.settings["keep_tags"] = bool(self.keep_tags_var.get())
        self.settings["normalize"] = bool(self.normalize_var.get())
        self.settings["recursive"] = bool(self.recursive_var.get())
        save_settings(self.settings)

    def start_processing(self):
        self._collect_settings_from_ui()
        with self.queue_lock:
            files = list(self.queue)
        if not files:
            self._set_status(tr(self.lang, "status_empty_queue"), "idle")
            return
        self.processing = True
        self._cancel_requested = False
        self._set_ui_busy(True)
        self.progress.set_color(C_ACCENT_2)
        self._worker_thread = threading.Thread(target=self._worker, args=(files,), daemon=True)
        self._worker_thread.start()

    def _worker(self, files):
        total = len(files)
        log.info(tr(self.lang, "log_conv_start", total))
        converter = Converter(self.settings, self.lang, on_progress=self._on_progress)
        self.converter = converter
        ok = 0
        fail = 0
        skip = 0
        for i, f in enumerate(files, start=1):
            if self._cancel_requested:
                break
            self._on_item(i, f, "processing", None)
            status, msg, out_path = converter.convert_file(f, i, total)
            if status == "done":
                ok += 1
                if out_path:
                    self.after(0, lambda p=out_path: self._add_output(p))
            elif status == "skipped":
                skip += 1
                if out_path:
                    self.after(0, lambda p=out_path: self._add_output(p))
            elif status == "cancelled":
                break
            else:
                fail += 1
            self._on_item(i, f, status, msg)
            log.info(msg)
        self.after(0, lambda: self._on_done(ok, fail, skip, total))

    def stop_processing(self):
        self._cancel_requested = True
        if self.converter:
            self.converter.cancel()
        self._set_status(tr(self.lang, "status_cancelled"), "error")
        self.progress.set_color(C_DANGER)

    def _on_progress(self, index, total, pct, name):
        overall = int(((index - 1) / max(total, 1)) * 100) + int(pct / max(total, 1))
        overall = max(0, min(100, overall))
        self.after(0, lambda: self.progress.set_value(overall))
        self.after(0, lambda: self._set_status(
            tr(self.lang, "status_processing", index, total, name), "processing"))
        self.after(0, lambda i=index, p=pct: self._update_input_row(i - 1, p))

    def _on_item(self, index, f, status, msg):
        iid = str(index - 1)
        tag = status if status in ("pending", "processing", "done", "failed", "skipped", "overwritten") else "failed"
        label_map = {"pending": "st_pending", "processing": "st_processing",
                     "done": "st_done", "failed": "st_failed",
                     "skipped": "st_skipped", "overwritten": "st_overwritten"}
        label = tr(self.lang, label_map.get(status, "st_failed"))
        try:
            size = human_size(os.path.getsize(f))
        except Exception:
            size = "—"
        progress_txt = "—" if status in ("pending", "done", "skipped", "failed") else ("100%" if status == "done" else "—")
        if status == "done":
            progress_txt = "100%"
        elif status == "failed":
            progress_txt = "!"
        self.after(0, lambda: self.input_tree.item(
            iid, values=(os.path.basename(f), size, label, progress_txt), tags=(tag,)))

    def _update_input_row(self, idx, pct):
        iid = str(idx)
        try:
            cur = self.input_tree.item(iid)["values"]
            name = cur[0]
            size = cur[1]
            status = tr(self.lang, "st_processing")
            self.input_tree.item(iid, values=(name, size, status, f"{pct}%"), tags=("processing",))
        except Exception:
            pass

    def _add_output(self, path):
        name = os.path.basename(path)
        folder = os.path.dirname(path)
        try:
            size_s = human_size(os.path.getsize(path))
        except Exception:
            size_s = "—"
        self.output_tree.insert("", "end", values=(name, folder, size_s))

    def _on_done(self, ok, fail, skip, total):
        self.processing = False
        self._set_ui_busy(False)
        self.progress.set_value(0)
        state = "error" if fail > 0 else "done"
        self._set_status(tr(self.lang, "status_done", ok, total, fail, skip), state)

    # ---- helpers ----
    def _set_status(self, msg, state="idle"):
        self.status_var.set(msg)
        color_map = {"idle": C_TEXT_FAINT, "processing": C_WARN,
                     "done": C_OK, "error": C_DANGER}
        icon_map = {"idle": "\u25CF", "processing": "\u25CF",
                    "done": "\u2713", "error": "\u2715"}
        self.status_icon.config(text=icon_map.get(state, "\u25CF"),
                                fg=color_map.get(state, C_TEXT_FAINT))

    def _set_ui_busy(self, busy):
        def _do():
            st = "disabled" if busy else "normal"
            self.add_files_btn.set_state(not busy)
            self.add_folder_btn.set_state(not busy)
            self.clear_input_btn.set_state(not busy)
            self.start_btn.set_state(not busy)
            self.clear_output_btn.set_state(not busy)
        self.after(0, _do)

    # ---- update check ----
    def check_update(self):
        def _do():
            try:
                url = f"https://api.github.com/repos/{REPO_SLUG}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode("utf-8"))
                latest = (data.get("tag_name") or "").lstrip("v")
                if latest and _ver_gt(latest, APP_VERSION):
                    self._set_status(tr(self.lang, "status_update_available",
                                        "v" + latest, APP_VERSION), "processing")
                    import webbrowser
                    webbrowser.open(data.get("html_url", f"https://github.com/{REPO_SLUG}/releases/latest"))
                else:
                    self._set_status(tr(self.lang, "status_no_update", APP_VERSION), "done")
            except Exception as e:
                self._set_status(tr(self.lang, "status_update_fail", e), "error")
        threading.Thread(target=_do, daemon=True).start()

    # ---- close ----
    def _on_close(self):
        try:
            self.settings["geometry"] = self.geometry()
        except Exception:
            pass
        self._collect_settings_from_ui()
        if self.processing and self.converter:
            self.converter.cancel()
        self.destroy()


def _ver_gt(a, b):
    def parts(x):
        return [int(p) for p in re.findall(r"\d+", x) or "0"]
    return parts(a) > parts(b)


def parse_dropped_files(data):
    result = []
    if isinstance(data, (list, tuple)):
        items = list(data)
    else:
        items = re.findall(r"\{[^}]*\}|\"[^\"]*\"|\S+", str(data))
    for p in items:
        p = p.strip()
        if not p:
            continue
        if p.startswith("{") and p.endswith("}"):
            p = p[1:-1]
        elif p.startswith('"') and p.endswith('"'):
            p = p[1:-1]
        if p:
            result.append(p)
    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def run_cli(files, settings):
    L = settings.get("lang") or default_lang()
    total = len(files)
    ok = 0
    fail = 0
    skip = 0
    converter = Converter(settings, L)
    print(f"EasyConvert v{APP_VERSION} — CLI mode")
    print(f"Files: {total}  bitrate={settings.get('bitrate')}  out={settings.get('out_mode')}")
    for i, f in enumerate(files, start=1):
        status, msg, _ = converter.convert_file(f, i, total)
        print(msg, flush=True)
        if status == "done":
            ok += 1
        elif status == "skipped":
            skip += 1
        else:
            fail += 1
    print(f"\nDone: {ok}/{total} — errors: {fail}, skipped: {skip}", flush=True)


def main():
    # CLI mode: EasyConvert --cli file1 file2 ... [--bitrate X --outdir Y --lang L --channels N]
    if len(sys.argv) >= 2 and sys.argv[1] == "--cli":
        s = load_settings()
        i = 2
        files = []
        while i < len(sys.argv):
            a = sys.argv[i]
            if a == "--bitrate" and i + 1 < len(sys.argv):
                s["bitrate"] = sys.argv[i + 1]; i += 2; continue
            if a == "--channels" and i + 1 < len(sys.argv):
                s["channels"] = sys.argv[i + 1]; i += 2; continue
            if a == "--outdir" and i + 1 < len(sys.argv):
                s["out_mode"] = "custom"; s["custom_out"] = sys.argv[i + 1]; i += 2; continue
            if a == "--lang" and i + 1 < len(sys.argv):
                s["lang"] = sys.argv[i + 1]; i += 2; continue
            files.append(a); i += 1
        if not files:
            print("No files to convert.")
            return 1
        return run_cli(files, s)

    # GUI mode: accept files dropped onto the exe (argv paths).
    dropped = []
    if len(sys.argv) >= 2:
        for arg in sys.argv[1:]:
            if os.path.exists(arg):
                dropped.append(arg)

    app = DropWindow()
    if dropped:
        app.after(100, lambda: app.add_paths(dropped))
    app.mainloop()


if __name__ == "__main__":
    main()
