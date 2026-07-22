# -*- coding: utf-8 -*-
"""
EasyConvert v1.1 — drag & drop any audio into MP3.

Two-panel UI:
  * top    = input queue (drag & drop files / folders, or pick via button)
  * bottom = output list (produced MP3s, open folder)

Features:
  - Direct ffmpeg-subprocess conversion (no pydub dependency at runtime for
    encoding) with real per-file progress, cancellation, metadata preservation.
  - Bitrate / sample-rate / channels / normalization / parallel workers.
  - Output folder modes: by-date, next-to-source, custom.
  - Collision policy: suffix _1, overwrite, skip.
  - i18n RU/EN with instant switching.
  - settings.json persistence, convert.log, update check via GitHub API.
"""

import os
import sys
import re
import json
import time
import locale
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
APP_VERSION = "1.1"
REPO_SLUG = "MarkHaker/EasyConvert"
DATE_FOLDER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Default sample of supported input extensions (informational only — ffmpeg
# decides what it can actually decode). Used for the file dialog filter.
INPUT_EXAMPLES = ".ogg .oga .opus .wav .mp3 .flac .aac .m4a .m4b .wma .ac3 .aiff .aif .amr .awb .voc .vox .gsm .tta .ape .wv .spx .webm .mka .mp4 .mkv .mov .avi"

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
    ".dca", ".dts", ".dtshd", ".thd", ".mlp", ".eac3",
}
# Formats ffmpeg cannot decode without extra assets (soundfont). We still try,
# but warn the user with a clear message.
LIMITED_EXTS = {".mid", ".midi", ".rmi", ".kar", ".mod", ".s3m", ".xm", ".it",
                ".mtm", ".669", ".far", ".stm", ".med", ".okt", ".psm", ".ptm",
                ".umx", ".amf", ".dsm", ".mdl", ".mt2", ".j2b", ".mptm", ".gdm"}


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
def is_frozen():
    return getattr(sys, "frozen", False)


def get_base_dir():
    """Directory where the program lives (exe folder or script folder)."""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_meipass():
    return getattr(sys, "_MEIPASS", None)


def find_ffmpeg():
    """Locate ffmpeg.exe: in _MEIPASS, next to exe/script, or in PATH."""
    candidates = []
    mp = get_meipass()
    if mp:
        candidates.append(mp)
    candidates.append(get_base_dir())
    for c in candidates:
        p = os.path.join(c, "ffmpeg.exe")
        if os.path.isfile(p):
            return p
    # last resort: rely on PATH
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
    """Resolve output directory based on settings."""
    mode = settings.get("out_mode", "date")
    if mode == "source":
        return os.path.dirname(os.path.abspath(input_path))
    elif mode == "custom":
        custom = settings.get("custom_out", "")
        if custom:
            os.makedirs(custom, exist_ok=True)
            return custom
    # date
    return get_or_create_today_folder()


def resolve_output_path(input_path, settings):
    """Compute the final .mp3 path, applying collision policy."""
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
    # suffix
    i = 1
    while True:
        cand = os.path.join(out_dir, f"{name_no_ext}_{i}.mp3")
        if not os.path.exists(cand):
            return cand, "new"
        i += 1


def collect_audio_files_from_paths(paths, recursive):
    """From a list of dropped paths, return the list of audio files."""
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
    # de-dup preserve order
    seen = set()
    out = []
    for f in result:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


# --------------------------------------------------------------------------- #
# Settings + logging
# --------------------------------------------------------------------------- #
DEFAULT_SETTINGS = {
    "bitrate": "320k",
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
    path = get_settings_path()
    s = dict(DEFAULT_SETTINGS)
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
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
        fmt = logging.Formatter("%(asctime)s  %(levelname)s  %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(fmt)
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
        loc = getlocale()[0] or "ru"
    except Exception:
        loc = "ru"
    return "ru" if loc.lower().startswith("ru") else "en"


def getlocale():
    try:
        import locale as _l
        try:
            return _l.getlocale()
        except Exception:
            return (_l.getdefaultlocale()[0], _l.getdefaultlocale()[1])
    except Exception:
        return (None, None)


I18N = {
    "ru": {
        "title": "EasyConvert — Аудио в MP3",
        "input_panel": "Вход: очередь файлов",
        "output_panel": "Выход: готовые MP3",
        "drop_hint": "БРОСЬ СЮДА ЛЮБОЕ АУДИО\nВ ЛЮБОМ ФОРМАТЕ\n\nа я его превращу в MP3",
        "drop_sub": "(или нажми кнопку «Добавить» ниже — файлы или папку)",
        "add_files": "Добавить файлы",
        "add_folder": "Добавить папку",
        "clear_input": "Очистить",
        "open_folder": "Открыть папку",
        "clear_output": "Очистить",
        "start": "Старт",
        "stop": "Стоп",
        "settings": "Настройки",
        "bitrate": "Битрейт:",
        "keep_native": "Сохранять исх. частоту/каналы",
        "normalize": "Нормализация громкости (loudnorm)",
        "out_mode": "Папка вывода:",
        "out_date": "по дате (ГГГГ-ММ-ДД)",
        "out_source": "рядом с исходником",
        "out_custom": "выбрать…",
        "collision": "При совпадении имён:",
        "col_suffix": "добавить _1",
        "col_overwrite": "перезаписать",
        "col_skip": "пропустить",
        "keep_tags": "Сохранять теги/метаданные",
        "recursive": "Рекурсивно по подпапкам",
        "workers": "Потоков:",
        "check_update": "Проверить обновления",
        "status_ready": "Готов к работе. Папка вывода: {}",
        "status_added": "Добавлено файлов: {}",
        "status_empty_queue": "Очередь пуста — добавь файлы",
        "status_processing": "Конвертирую [{}{}] : {}",
        "status_done": "Готово: {} из {}, ошибок: {}, пропущено: {}",
        "status_cancelled": "Остановлено пользователем",
        "status_no_update": "У вас последняя версия (v{})",
        "status_update_available": "Доступна новая версия: {} (текущая v{}). Открываю страницу…",
        "status_update_fail": "Не удалось проверить обновления: {}",
        "col_file": "Файл",
        "col_status": "Статус",
        "col_progress": "Прогресс",
        "col_out_name": "Имя",
        "col_out_path": "Папка",
        "col_out_size": "Размер",
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
        "log_cancelled": "Конвертация остановлена",
        "err_not_found": "Файл не найден",
        "err_decode": "ffmpeg не смог декодировать файл",
        "err_limited": "Формат требует звукового шрифта — не поддерживается",
        "err_unknown": "Ошибка",
        "msg_pick_files": "Выбери аудио файлы",
        "msg_pick_folder": "Выбери папку с аудио",
        "msg_pick_output": "Выбери папку для вывода MP3",
        "all_files": "Все файлы",
        "audio_files": "Аудио файлы",
        "confirm_clear_input": "Очистить очередь?",
        "about": "О программе",
        "about_text": "EasyConvert v{}\nDrag & drop аудио в MP3.\n\nGitHub: https://github.com/{}".format(APP_VERSION, REPO_SLUG),
    },
    "en": {
        "title": "EasyConvert — Audio to MP3",
        "input_panel": "Input: file queue",
        "output_panel": "Output: produced MP3s",
        "drop_hint": "DROP ANY AUDIO HERE\nIN ANY FORMAT\n\nand it becomes an MP3",
        "drop_sub": "(or click \"Add\" below — files or a folder)",
        "add_files": "Add files",
        "add_folder": "Add folder",
        "clear_input": "Clear",
        "open_folder": "Open folder",
        "clear_output": "Clear",
        "start": "Start",
        "stop": "Stop",
        "settings": "Settings",
        "bitrate": "Bitrate:",
        "keep_native": "Keep source sample-rate/channels",
        "normalize": "Normalize loudness (loudnorm)",
        "out_mode": "Output folder:",
        "out_date": "by date (YYYY-MM-DD)",
        "out_source": "next to source",
        "out_custom": "choose…",
        "collision": "On name clash:",
        "col_suffix": "add _1",
        "col_overwrite": "overwrite",
        "col_skip": "skip",
        "keep_tags": "Keep tags/metadata",
        "recursive": "Recurse into subfolders",
        "workers": "Workers:",
        "check_update": "Check for updates",
        "status_ready": "Ready. Output folder: {}",
        "status_added": "Added {} file(s)",
        "status_empty_queue": "Queue is empty — add some files",
        "status_processing": "Converting [{}/{}]: {}",
        "status_done": "Done: {}/{} — errors: {}, skipped: {}",
        "status_cancelled": "Cancelled by user",
        "status_no_update": "You're on the latest version (v{})",
        "status_update_available": "New version available: {} (current v{}). Opening page…",
        "status_update_fail": "Update check failed: {}",
        "col_file": "File",
        "col_status": "Status",
        "col_progress": "Progress",
        "col_out_name": "Name",
        "col_out_path": "Folder",
        "col_out_size": "Size",
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
        "log_cancelled": "Conversion cancelled",
        "err_not_found": "File not found",
        "err_decode": "ffmpeg could not decode the file",
        "err_limited": "Format needs a soundfont — unsupported",
        "err_unknown": "Error",
        "msg_pick_files": "Pick audio files",
        "msg_pick_folder": "Pick a folder with audio",
        "msg_pick_output": "Pick output folder for MP3s",
        "all_files": "All files",
        "audio_files": "Audio files",
        "confirm_clear_input": "Clear the queue?",
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
# ffprobe: get duration for progress
# --------------------------------------------------------------------------- #
def ffprobe_duration(probe_path, file_path):
    """Return duration in seconds (float) or None."""
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


_CREATEFLAGS = 0
if sys.platform == "win32":
    _CREATEFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0


# --------------------------------------------------------------------------- #
# Conversion core (ffmpeg subprocess)
# --------------------------------------------------------------------------- #
class Converter:
    """Runs ffmpeg in a worker thread; parses progress; supports cancel."""

    def __init__(self, settings, lang, on_progress=None, on_item=None,
                 on_done=None):
        self.settings = settings
        self.lang = lang
        self.on_progress = on_progress
        self.on_item = on_item
        self.on_done = on_done
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
                "-nostdin", "-y", "-i", in_path]
        # video containers: drop video stream
        args += ["-vn"]
        if s.get("keep_tags", True):
            # Pull format-level metadata, and also stream-level (Vorbis comments)
            # into the output MP3 ID3 tags. 0 = first input file.
            args += ["-map_metadata", "0", "-map_metadata", "0:s:0"]
        af = []
        if s.get("normalize", False):
            af.append("loudnorm")
        if af:
            args += ["-af", ",".join(af)]
        args += ["-c:a", "libmp3lame", "-b:a", s.get("bitrate", "320k")]
        if not s.get("keep_native", False):
            args += ["-ar", "44100", "-ac", "2"]
        args += [out_path]
        return args

    def convert_file(self, in_path, index, total):
        """Convert a single file. Returns (status, message, out_path)."""
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

        # Parse stderr line by line for time= progress.
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
            # remove partial output
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
# GUI
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
        self.configure(bg="#1e1e2e")
        self.minsize(760, 600)

        # Window icon
        try:
            self.iconbitmap(default=resource_path("ico.ico"))
        except Exception:
            pass

        # Restore geometry
        geo = self.settings.get("geometry")
        if geo:
            try:
                self.geometry(geo)
            except Exception:
                self.geometry("900x680")
        else:
            self.geometry("900x680")

        self.queue = []          # list of input paths pending
        self.queue_lock = threading.Lock()
        self.processing = False
        self.converter = None
        self._worker_thread = None
        self._cancel_requested = False

        self._build_ui()
        self._apply_lang()
        self._set_status(tr(self.lang, "status_ready", get_today_folder_name()))

        if _HAS_DND:
            # Register drop on whole window (root) + drop frame
            self.drop_target_register(tkinterdnd2.DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop_root)
            self.drop_frame.drop_target_register(tkinterdnd2.DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_frame.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            self.drop_frame.dnd_bind("<<DropLeave>>", self._on_drop_leave)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- UI construction ----
    def _build_ui(self):
        # Top bar: language switch + title + update
        topbar = tk.Frame(self, bg="#181825")
        topbar.pack(fill="x", padx=10, pady=(10, 4))

        self.title_lbl = tk.Label(topbar, text=APP_NAME, fg="#cba6f7",
                                 bg="#181825", font=("Segoe UI", 14, "bold"))
        self.title_lbl.pack(side="left", padx=(4, 16))

        self.lang_var = tk.StringVar(value=self.lang.upper())
        self.lang_ru = tk.Radiobutton(topbar, text="RU", value="RU",
                                      variable=self.lang_var,
                                      command=lambda: self._switch_lang("ru"),
                                      bg="#181825", fg="#cdd6f4",
                                      selectcolor="#2a2a3c",
                                      activebackground="#181825",
                                      activeforeground="#cdd6f4",
                                      font=("Segoe UI", 10, "bold"))
        self.lang_en = tk.Radiobutton(topbar, text="EN", value="EN",
                                      variable=self.lang_var,
                                      command=lambda: self._switch_lang("en"),
                                      bg="#181825", fg="#cdd6f4",
                                      selectcolor="#2a2a3c",
                                      activebackground="#181825",
                                      activeforeground="#cdd6f4",
                                      font=("Segoe UI", 10, "bold"))
        self.lang_ru.pack(side="right", padx=2)
        self.lang_en.pack(side="right", padx=2)

        self.update_btn = tk.Button(topbar, text=tr(self.lang, "check_update"),
                                   command=self.check_update, bg="#313244",
                                   fg="#cdd6f4", activebackground="#45475a",
                                   relief="flat", padx=10, pady=3,
                                   font=("Segoe UI", 9), cursor="hand2")
        self.update_btn.pack(side="right", padx=10)

        # Drop frame
        self.drop_frame = tk.Frame(self, bg="#2a2a3c",
                                  highlightbackground="#5b5b8a",
                                  highlightthickness=2, bd=0, height=130)
        self.drop_frame.pack(fill="x", padx=10, pady=(4, 6))
        self.drop_frame.pack_propagate(False)
        self.drop_label = tk.Label(self.drop_frame, text=tr(self.lang, "drop_hint"),
                                   fg="#cdd6f4", bg="#2a2a3c",
                                   font=("Segoe UI", 14, "bold"),
                                   justify="center")
        self.drop_label.place(relx=0.5, rely=0.46, anchor="center")
        self.sub_label = tk.Label(self.drop_frame, text=tr(self.lang, "drop_sub"),
                                  fg="#7f7fa0", bg="#2a2a3c",
                                  font=("Segoe UI", 9))
        self.sub_label.place(relx=0.5, rely=0.84, anchor="center")

        # Action buttons row
        act = tk.Frame(self, bg="#1e1e2e")
        act.pack(fill="x", padx=10, pady=(0, 6))
        self.add_files_btn = self._btn(act, tr(self.lang, "add_files"), self.choose_files)
        self.add_files_btn.pack(side="left", padx=(0, 6))
        self.add_folder_btn = self._btn(act, tr(self.lang, "add_folder"), self.choose_folder)
        self.add_folder_btn.pack(side="left", padx=(0, 6))
        self.clear_input_btn = self._btn(act, tr(self.lang, "clear_input"), self.clear_input, bg="#45475a")
        self.clear_input_btn.pack(side="left", padx=(0, 6))
        self.start_btn = self._btn(act, tr(self.lang, "start"), self.start_processing, bg="#a6e3a1", fg="#1e1e2e")
        self.start_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = self._btn(act, tr(self.lang, "stop"), self.stop_processing, bg="#f38ba8", fg="#1e1e2e")
        self.stop_btn.pack(side="left", padx=(0, 6))
        self.open_folder_btn = self._btn(act, tr(self.lang, "open_folder"), self.open_output_folder, bg="#89b4fa", fg="#1e1e2e")
        self.open_folder_btn.pack(side="right")

        # Settings panel (collapsible)
        self.settings_frame = tk.LabelFrame(self, text=tr(self.lang, "settings"),
                                            bg="#1e1e2e", fg="#a6adc8",
                                            font=("Segoe UI", 9, "bold"),
                                            bd=1, relief="ridge")
        self.settings_frame.pack(fill="x", padx=10, pady=(0, 6))
        sf = self.settings_frame
        sf.columnconfigure(0, weight=1)
        row = tk.Frame(sf, bg="#1e1e2e"); row.pack(fill="x", padx=8, pady=4)

        tk.Label(row, text=tr(self.lang, "bitrate"), bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.bitrate_var = tk.StringVar(value=self.settings.get("bitrate", "320k"))
        self.bitrate_cb = ttk.Combobox(row, textvariable=self.bitrate_var,
                                       values=["320k", "256k", "192k", "128k", "96k"],
                                       width=6, state="readonly")
        self.bitrate_cb.pack(side="left", padx=(0, 16))

        tk.Label(row, text=tr(self.lang, "workers"), bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        import multiprocessing as _mp
        maxw = max(1, _mp.cpu_count() or 4)
        self.workers_var = tk.IntVar(value=self.settings.get("workers", 0) or min(4, maxw))
        self.workers_sp = ttk.Spinbox(row, from_=1, to=maxw, width=4,
                                     textvariable=self.workers_var)
        self.workers_sp.pack(side="left", padx=(0, 16))

        tk.Label(row, text=tr(self.lang, "out_mode"), bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.out_mode_var = tk.StringVar(value=self.settings.get("out_mode", "date"))
        self.out_mode_cb = ttk.Combobox(row, textvariable=self.out_mode_var,
                                        values=["date", "source", "custom"],
                                        width=12, state="readonly")
        self.out_mode_cb.pack(side="left", padx=(0, 6))
        self.out_custom_btn = tk.Button(row, text="…", command=self.choose_custom_out,
                                        bg="#313244", fg="#cdd6f4", relief="flat",
                                        padx=6, cursor="hand2")
        self.out_custom_btn.pack(side="left", padx=(0, 16))

        tk.Label(row, text=tr(self.lang, "collision"), bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.col_var = tk.StringVar(value=self.settings.get("collision", "suffix"))
        self.col_cb = ttk.Combobox(row, textvariable=self.col_var,
                                   values=["suffix", "overwrite", "skip"],
                                   width=10, state="readonly")
        self.col_cb.pack(side="left", padx=(0, 16))

        row2 = tk.Frame(sf, bg="#1e1e2e"); row2.pack(fill="x", padx=8, pady=(0, 4))
        self.keep_native_var = tk.BooleanVar(value=self.settings.get("keep_native", False))
        self.keep_tags_var = tk.BooleanVar(value=self.settings.get("keep_tags", True))
        self.normalize_var = tk.BooleanVar(value=self.settings.get("normalize", False))
        self.recursive_var = tk.BooleanVar(value=self.settings.get("recursive", True))
        for var, key in [
            (self.keep_native_var, "keep_native"),
            (self.keep_tags_var, "keep_tags"),
            (self.normalize_var, "normalize"),
            (self.recursive_var, "recursive"),
        ]:
            cb = tk.Checkbutton(row2, text=tr(self.lang, key), variable=var,
                                bg="#1e1e2e", fg="#cdd6f4", selectcolor="#2a2a3c",
                                activebackground="#1e1e2e", activeforeground="#cdd6f4",
                                font=("Segoe UI", 9))
            cb.pack(side="left", padx=(0, 16))

        # Main two-panel area
        panels = tk.Frame(self, bg="#1e1e2e")
        panels.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=1)
        panels.rowconfigure(1, weight=1)

        # Input panel
        tk.Label(panels, text=tr(self.lang, "input_panel"), bg="#1e1e2e",
                 fg="#a6adc8", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.input_tree = ttk.Treeview(panels,
                                      columns=("file", "status", "progress"),
                                      show="headings", selectmode="extended")
        self.input_tree.heading("file", text=tr(self.lang, "col_file"))
        self.input_tree.heading("status", text=tr(self.lang, "col_status"))
        self.input_tree.heading("progress", text=tr(self.lang, "col_progress"))
        self.input_tree.column("file", width=260, anchor="w")
        self.input_tree.column("status", width=80, anchor="center")
        self.input_tree.column("progress", width=60, anchor="center")
        self.input_tree.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        isb = ttk.Scrollbar(panels, orient="vertical", command=self.input_tree.yview)
        self.input_tree.configure(yscrollcommand=isb.set)
        isb.grid(row=1, column=0, sticky="nsew", padx=(0, 0))

        # Output panel
        tk.Label(panels, text=tr(self.lang, "output_panel"), bg="#1e1e2e",
                 fg="#a6adc8", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w")
        self.output_tree = ttk.Treeview(panels,
                                       columns=("name", "path", "size"),
                                       show="headings", selectmode="extended")
        self.output_tree.heading("name", text=tr(self.lang, "col_out_name"))
        self.output_tree.heading("path", text=tr(self.lang, "col_out_path"))
        self.output_tree.heading("size", text=tr(self.lang, "col_out_size"))
        self.output_tree.column("name", width=180, anchor="w")
        self.output_tree.column("path", width=220, anchor="w")
        self.output_tree.column("size", width=60, anchor="e")
        self.output_tree.grid(row=1, column=1, sticky="nsew")
        osb = ttk.Scrollbar(panels, orient="vertical", command=self.output_tree.yview)
        self.output_tree.configure(yscrollcommand=osb.set)
        osb.grid(row=1, column=1, sticky="nsew")
        self.output_tree.bind("<Double-1>", self._open_selected_output)

        # Status + progress
        sb = tk.Frame(self, bg="#1e1e2e")
        sb.pack(fill="x", padx=10, pady=(0, 4))
        self.progress = ttk.Progressbar(sb, mode="determinate", maximum=100)
        self.progress.pack(fill="x", side="top")
        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(sb, textvariable=self.status_var,
                                     fg="#a6adc8", bg="#1e1e2e",
                                     font=("Segoe UI", 9), anchor="w", justify="left")
        self.status_label.pack(fill="x", side="top", pady=(2, 0))

        # Style
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", background="#181825", foreground="#cdd6f4",
                        fieldbackground="#181825", borderwidth=0)
        style.configure("Treeview.Heading", background="#313244",
                        foreground="#cdd6f4", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#45475a")])
        style.configure("Horizontal.TProgressbar", troughcolor="#181825",
                        background="#a6e3a1")

        # tagging for statuses
        self.input_tree.tag_configure("pending", foreground="#7f7fa0")
        self.input_tree.tag_configure("processing", foreground="#f9e2af")
        self.input_tree.tag_configure("done", foreground="#a6e3a1")
        self.input_tree.tag_configure("failed", foreground="#f38ba8")
        self.input_tree.tag_configure("skipped", foreground="#89b4fa")
        self.input_tree.tag_configure("overwritten", foreground="#a6e3a1")

    def _btn(self, parent, text, cmd, bg="#313244", fg="#cdd6f4"):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         activebackground="#45475a", relief="flat", padx=12,
                         pady=6, cursor="hand2", font=("Segoe UI", 10, "bold"))

    # ---- language ----
    def _switch_lang(self, new_lang):
        if new_lang == self.lang:
            return
        self.lang = new_lang
        self.settings["lang"] = new_lang
        save_settings(self.settings)
        self._apply_lang()
        self._set_status(tr(self.lang, "status_ready", get_today_folder_name()))

    def _apply_lang(self):
        L = self.lang
        self.title(tr(L, "title"))
        self.title_lbl.config(text=APP_NAME)
        self.update_btn.config(text=tr(L, "check_update"))
        self.drop_label.config(text=tr(L, "drop_hint"))
        self.sub_label.config(text=tr(L, "drop_sub"))
        self.add_files_btn.config(text=tr(L, "add_files"))
        self.add_folder_btn.config(text=tr(L, "add_folder"))
        self.clear_input_btn.config(text=tr(L, "clear_input"))
        self.start_btn.config(text=tr(L, "start"))
        self.stop_btn.config(text=tr(L, "stop"))
        self.open_folder_btn.config(text=tr(L, "open_folder"))
        self.settings_frame.config(text=tr(L, "settings"))
        self.input_tree.heading("file", text=tr(L, "col_file"))
        self.input_tree.heading("status", text=tr(L, "col_status"))
        self.input_tree.heading("progress", text=tr(L, "col_progress"))
        self.output_tree.heading("name", text=tr(L, "col_out_name"))
        self.output_tree.heading("path", text=tr(L, "col_out_path"))
        self.output_tree.heading("size", text=tr(L, "col_out_size"))
        # re-label settings row
        for w in self.settings_frame.winfo_children():
            for child in w.winfo_children():
                # labels keep their text; we re-apply via stored keys
                pass

    # ---- DnD ----
    def _on_drop_enter(self, event):
        self.drop_frame.config(highlightbackground="#cba6f7")

    def _on_drop_leave(self, event):
        self.drop_frame.config(highlightbackground="#5b5b8a")

    def _on_drop(self, event):
        self.drop_frame.config(highlightbackground="#5b5b8a")
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
        with self.queue_lock:
            existing = set(self.queue)
            for f in files:
                if f not in existing:
                    self.queue.append(f)
                    existing.add(f)
        self._refresh_input_tree()
        if files:
            self._set_status(tr(self.lang, "status_added", len(files)))
        else:
            self._set_status(tr(self.lang, "status_empty_queue"))

    def _refresh_input_tree(self):
        for iid in self.input_tree.get_children():
            self.input_tree.delete(iid)
        with self.queue_lock:
            items = list(self.queue)
        for i, f in enumerate(items):
            self.input_tree.insert("", "end", iid=str(i),
                                   values=(os.path.basename(f),
                                           tr(self.lang, "st_pending"), "—"),
                                   tags=("pending",))

    def clear_input(self):
        if not self.queue and not self.input_tree.get_children():
            return
        if not messagebox.askyesno(APP_NAME, tr(self.lang, "confirm_clear_input")):
            return
        with self.queue_lock:
            self.queue.clear()
        self._refresh_input_tree()
        self._set_status(tr(self.lang, "status_ready", get_today_folder_name()))

    def open_output_folder(self):
        # open the most relevant output folder
        sel = self.output_tree.selection()
        if sel:
            item = self.output_tree.item(sel[0])
            path = item["values"][1]
            try:
                os.startfile(path)
                return
            except Exception:
                pass
        # fallback: today folder
        try:
            os.startfile(get_or_create_today_folder())
        except Exception as e:
            self._set_status(f"open folder failed: {e}")

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
        self.settings["workers"] = int(self.workers_var.get() or 1)
        self.settings["out_mode"] = self.out_mode_var.get()
        self.settings["collision"] = self.col_var.get()
        self.settings["keep_native"] = bool(self.keep_native_var.get())
        self.settings["keep_tags"] = bool(self.keep_tags_var.get())
        self.settings["normalize"] = bool(self.normalize_var.get())
        self.settings["recursive"] = bool(self.recursive_var.get())
        save_settings(self.settings)

    def start_processing(self):
        self._collect_settings_from_ui()
        with self.queue_lock:
            files = list(self.queue)
        if not files:
            self._set_status(tr(self.lang, "status_empty_queue"))
            return
        self.processing = True
        self._cancel_requested = False
        self._set_ui_busy(True)
        self._worker_thread = threading.Thread(target=self._worker, args=(files,), daemon=True)
        self._worker_thread.start()

    def _worker(self, files):
        total = len(files)
        log.info(tr(self.lang, "log_conv_start", total))
        converter = Converter(self.settings, self.lang,
                              on_progress=self._on_progress,
                              on_item=self._on_item,
                              on_done=None)
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
            elif status == "overwritten":
                ok += 1
                if out_path:
                    self.after(0, lambda p=out_path: self._add_output_row(p, replace=True))
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
        self._set_status(tr(self.lang, "status_cancelled"))

    def _on_progress(self, index, total, pct, name):
        # overall progress across queue + per-file update
        overall = int(((index - 1) / max(total, 1)) * 100) + int(pct / max(total, 1))
        overall = max(0, min(100, overall))
        self.after(0, lambda: self.progress.config(value=overall))
        self.after(0, lambda: self._set_status(
            tr(self.lang, "status_processing", index, total, name)))
        self.after(0, lambda i=index, p=pct: self._update_input_row(i - 1, p))

    def _on_item(self, index, f, status, msg):
        iid = str(index - 1)
        tag = status if status in ("pending", "processing", "done", "failed", "skipped", "overwritten") else "failed"
        label_map = {"pending": "st_pending", "processing": "st_processing",
                     "done": "st_done", "failed": "st_failed",
                     "skipped": "st_skipped", "overwritten": "st_overwritten"}
        label = tr(self.lang, label_map.get(status, "st_failed"))
        self.after(0, lambda: self.input_tree.item(iid, values=(os.path.basename(f), label, "—"), tags=(tag,)))

    def _update_input_row(self, idx, pct):
        iid = str(idx)
        try:
            cur = self.input_tree.item(iid)["values"]
            name = cur[0]
            status = tr(self.lang, "st_processing")
            self.input_tree.item(iid, values=(name, status, f"{pct}%"), tags=("processing",))
        except Exception:
            pass

    def _add_output(self, path):
        self._add_output_row(path, replace=False)

    def _add_output_row(self, path, replace=False):
        name = os.path.basename(path)
        folder = os.path.dirname(path)
        try:
            size = os.path.getsize(path)
            size_s = f"{size // 1024} KB" if size < 1024 * 1024 else f"{size // (1024*1024)} MB"
        except Exception:
            size_s = "—"
        # remove existing row with same name if replace
        if replace:
            for iid in self.output_tree.get_children():
                if self.output_tree.item(iid)["values"][0] == name:
                    self.output_tree.delete(iid)
        self.output_tree.insert("", "end",
                                values=(name, folder, size_s))

    def _on_done(self, ok, fail, skip, total):
        self.processing = False
        self._set_ui_busy(False)
        self.progress.config(value=0)
        self._set_status(tr(self.lang, "status_done", ok, total, fail, skip))

    # ---- helpers ----
    def _set_status(self, msg):
        self.status_var.set(msg)

    def _set_ui_busy(self, busy):
        def _do():
            st = "disabled" if busy else "normal"
            self.add_files_btn.config(state=st)
            self.add_folder_btn.config(state=st)
            self.clear_input_btn.config(state=st)
            self.start_btn.config(state=st)
            if busy:
                self.stop_btn.config(state="normal")
            else:
                self.stop_btn.config(state="normal")
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
                    self._set_status(tr(self.lang, "status_update_available", "v" + latest, APP_VERSION))
                    import webbrowser
                    webbrowser.open(data.get("html_url", f"https://github.com/{REPO_SLUG}/releases/latest"))
                else:
                    self._set_status(tr(self.lang, "status_no_update", APP_VERSION))
            except Exception as e:
                self._set_status(tr(self.lang, "status_update_fail", e))
        threading.Thread(target=_do, daemon=True).start()

    # ---- close ----
    def _on_close(self):
        # persist geometry + settings
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
    """Parse DND_FILES data string into a list of file paths."""
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
    # CLI mode: EasyConvert --cli file1 file2 ... [--bitrate X --outdir Y --lang L]
    if len(sys.argv) >= 2 and sys.argv[1] == "--cli":
        s = load_settings()
        # parse optional flags
        i = 2
        files = []
        while i < len(sys.argv):
            a = sys.argv[i]
            if a == "--bitrate" and i + 1 < len(sys.argv):
                s["bitrate"] = sys.argv[i + 1]; i += 2; continue
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
