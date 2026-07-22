# -*- coding: utf-8 -*-
"""
EasyConvert v1.1.3 — drag & drop any audio into MP3.

Premium card-based neumorphism UI built with PyQt6 + QSS.
- Card surfaces with drop shadows, rounded corners (cards 20px, controls 12px).
- Dotted dropzone, custom dark thin scrollbars, toggle switches (no checkboxes).
- Strict vector icons drawn with QPainter (no emojis).
- Direct ffmpeg-subprocess core: real per-file progress, cancel, metadata
  preservation (-map_metadata 0:s:0), video container support (-vn).
- i18n RU/EN with a pill switch. settings.json, convert.log, update check.
"""

import os
import sys
import re
import json
import time
import threading
import subprocess
import datetime
import urllib.request
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QRectF, QPoint, QPointF, QLineF
from PyQt6.QtGui import (QGuiApplication, QAction, QColor, QPainter, QPen,
                         QBrush, QPainterPath, QIcon, QPixmap, QFontDatabase)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel,
                             QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QFrame, QScrollArea, QComboBox, QSpinBox, QTreeWidget,
                             QTreeWidgetItem, QProgressBar, QSizePolicy, QStyle,
                             QStyleOptionViewItem, QStyledItemDelegate)
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QAbstractItemView

APP_NAME = "EasyConvert"
APP_VERSION = "1.1.3"
REPO_SLUG = "MarkHaker/EasyConvert"

# --------------------------------------------------------------------------- #
# Palette (strict, per spec)
# --------------------------------------------------------------------------- #
C_MAIN_BG = "#13131A"
C_CARD = "#1C1C26"
C_INPUT = "#252533"
C_ACCENT = "#00F0FF"      # START neon teal
C_DANGER = "#FF3366"      # STOP neon red
C_TEXT = "#FFFFFF"
C_TEXT_DIM = "#8A8A9D"
C_BORDER = "#2E2E3A"

# --------------------------------------------------------------------------- #
# Audio extensions
# --------------------------------------------------------------------------- #
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
        "queue": "Очередь файлов",
        "done_mp3": "Готовые MP3",
        "drop_hint": "Перетащите файлы сюда",
        "drop_sub": "или нажмите + выше",
        "add_file_tip": "Добавить файлы",
        "add_folder_tip": "Добавить папку",
        "clear_tip": "Очистить",
        "open_folder_tip": "Открыть папку",
        "start": "СТАРТ",
        "stop": "СТОП",
        "audio": "АУДИО",
        "control": "УПРАВЛЕНИЕ",
        "paths": "ПУТИ",
        "bitrate": "Битрейт",
        "channels": "Каналы",
        "workers": "Потоков",
        "out_mode": "Папка вывода",
        "collision": "При совпадении",
        "keep_native": "Сохранять частоту исх.",
        "keep_tags": "Сохранять теги",
        "normalize": "Нормализация громкости",
        "recursive": "Рекурсивно по подпапкам",
        "check_update": "Проверить обновления",
        "status_ready": "Готов к работе. Папка: {}",
        "status_added": "Добавлено файлов: {}",
        "status_empty_queue": "Очередь пуста — добавьте файлы",
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
        "log_conv_start": "Начало конвертации: {} файл(ов)",
        "log_conv_ok": "[OK] {}/{}  {}  ->  {}",
        "log_conv_fail": "[FAIL] {}/{}  {}: {}",
        "log_conv_skip": "[SKIP] {}/{}  {} (уже существует)",
        "err_not_found": "Файл не найден",
        "err_decode": "ffmpeg не смог декодировать файл",
        "err_limited": "Формат требует звукового шрифта — не поддерживается",
        "err_unknown": "Ошибка",
        "msg_pick_files": "Выберите аудио файлы",
        "msg_pick_folder": "Выберите папку с аудио",
        "msg_pick_output": "Выберите папку для вывода MP3",
        "all_files": "Все файлы",
        "audio_files": "Аудио файлы",
        "confirm_clear": "Очистить список?",
    },
    "en": {
        "title": "EasyConvert — Audio to MP3",
        "queue": "File queue",
        "done_mp3": "Converted MP3s",
        "drop_hint": "Drop files here",
        "drop_sub": "or click + above",
        "add_file_tip": "Add files",
        "add_folder_tip": "Add folder",
        "clear_tip": "Clear",
        "open_folder_tip": "Open folder",
        "start": "START",
        "stop": "STOP",
        "audio": "AUDIO",
        "control": "CONTROL",
        "paths": "PATHS",
        "bitrate": "Bitrate",
        "channels": "Channels",
        "workers": "Workers",
        "out_mode": "Output folder",
        "collision": "On clash",
        "keep_native": "Keep source rate",
        "keep_tags": "Keep tags",
        "normalize": "Loudness normalization",
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
    },
}


def tr(lang, key, *args):
    t = I18N.get(lang, I18N["en"]).get(key, key)
    try:
        return t.format(*args) if args else t
    except Exception:
        return t


# --------------------------------------------------------------------------- #
# Conversion core (ffmpeg subprocess)
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
# Worker thread (Qt)
# --------------------------------------------------------------------------- #
class ConvertWorker(QThread):
    progress = pyqtSignal(int, int, int, str)   # index, total, pct, name
    item_status = pyqtSignal(int, str, str)     # index, status, name
    output_ready = pyqtSignal(str)              # output path
    finished_run = pyqtSignal(int, int, int, int)  # ok, fail, skip, total
    log_line = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, files, settings, lang):
        super().__init__()
        self.files = files
        self.settings = settings
        self.lang = lang
        self.converter = Converter(settings, lang, on_progress=self._on_progress)
        self._stop = False

    def _on_progress(self, index, total, pct, name):
        self.progress.emit(index, total, pct, name)

    def cancel(self):
        self._stop = True
        self.converter.cancel()

    def run(self):
        total = len(self.files)
        log.info(tr(self.lang, "log_conv_start", total))
        self.log_line.emit(tr(self.lang, "log_conv_start", total))
        ok = fail = skip = 0
        for i, f in enumerate(self.files, start=1):
            if self._stop:
                break
            self.item_status.emit(i, "processing", f)
            status, msg, out_path = self.converter.convert_file(f, i, total)
            if status == "done":
                ok += 1
                if out_path:
                    self.output_ready.emit(out_path)
            elif status == "skipped":
                skip += 1
                if out_path:
                    self.output_ready.emit(out_path)
            elif status == "cancelled":
                self.cancelled.emit()
                break
            else:
                fail += 1
            self.item_status.emit(i, status, f)
            self.log_line.emit(msg)
            log.info(msg)
        self.finished_run.emit(ok, fail, skip, total)


# --------------------------------------------------------------------------- #
# Icon renderer — strict vector icons, no emojis
# --------------------------------------------------------------------------- #
def make_icon_pixmap(draw_func, size=20, color=C_TEXT_DIM, device_pixel_ratio=1.0):
    """Render an icon via a QPainter draw_func onto a transparent pixmap."""
    px = QPixmap(int(size * device_pixel_ratio), int(size * device_pixel_ratio))
    px.setDevicePixelRatio(device_pixel_ratio)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    col = QColor(color)
    p.setPen(QPen(col, 1.6))
    p.setBrush(QBrush(col))
    draw_func(p, size)
    p.end()
    return px


def icon_plus(p, s):
    m = s * 0.22
    p.setPen(QPen(p.pen().color(), 2.0))
    p.drawLine(QLineF(QPointF(m, s / 2), QPointF(s - m, s / 2)))
    p.drawLine(QLineF(QPointF(s / 2, m), QPointF(s / 2, s - m)))


def icon_folder(p, s):
    col = p.pen().color()
    p.setPen(QPen(col, 1.8))
    p.setBrush(QBrush(col))
    path = QPainterPath()
    m = 0.18
    path.moveTo(s * m, s * (0.30))
    path.lineTo(s * 0.42, s * 0.30)
    path.lineTo(s * 0.52, s * 0.40)
    path.lineTo(s * (1 - m), s * 0.40)
    path.lineTo(s * (1 - m), s * (1 - m))
    path.lineTo(s * m, s * (1 - m))
    path.closeSubpath()
    p.drawPath(path)


def icon_trash(p, s):
    col = p.pen().color()
    p.setPen(QPen(col, 1.8))
    p.setBrush(QBrush(Qt.GlobalColor.transparent))
    m = 0.22
    # lid
    p.drawLine(QLineF(QPointF(s * m, s * 0.32), QPointF(s * (1 - m), s * 0.32)))
    # handle
    p.drawLine(QLineF(QPointF(s * 0.40, s * 0.32), QPointF(s * 0.40, s * 0.24)))
    p.drawLine(QLineF(QPointF(s * 0.60, s * 0.24), QPointF(s * 0.60, s * 0.32)))
    # body
    p.setBrush(QBrush(Qt.GlobalColor.transparent))
    p.drawRoundedRect(QRectF(s * m, s * 0.32, s * (1 - 2 * m), s * (0.68 - 0.32)),
                      2, 2)
    # lines
    p.drawLine(QLineF(QPointF(s * 0.45, s * 0.42), QPointF(s * 0.45, s * 0.60)))
    p.drawLine(QLineF(QPointF(s * 0.55, s * 0.42), QPointF(s * 0.55, s * 0.60)))


def icon_refresh(p, s):
    col = p.pen().color()
    p.setPen(QPen(col, 1.8))
    p.setBrush(QBrush(col))
    p.translate(s / 2, s / 2)
    r = s * 0.34
    # Draw ~300deg arc using addArc (start 20deg, span 300deg)
    path = QPainterPath()
    path.arcMoveTo(QRectF(-r, -r, 2 * r, 2 * r), 20)
    path.arcTo(QRectF(-r, -r, 2 * r, 2 * r), 20, 300)
    p.drawPath(path)
    # arrowhead at the end of the arc
    p.setBrush(QBrush(col))
    tri = QPainterPath()
    tri.moveTo(r * 0.6, -r * 0.2)
    tri.lineTo(r * 1.15, r * 0.1)
    tri.lineTo(r * 0.6, r * 0.5)
    tri.closeSubpath()
    p.drawPath(tri)


def icon_play(p, s):
    col = p.pen().color()
    p.setBrush(QBrush(col))
    p.setPen(Qt.PenStyle.NoPen)
    tri = QPainterPath()
    m = 0.28
    tri.moveTo(s * (m + 0.04), s * m)
    tri.lineTo(s * (1 - m), s / 2)
    tri.lineTo(s * (m + 0.04), s * (1 - m))
    tri.closeSubpath()
    p.drawPath(tri)


def icon_stop(p, s):
    col = p.pen().color()
    p.setBrush(QBrush(col))
    p.setPen(Qt.PenStyle.NoPen)
    m = 0.26
    p.drawRoundedRect(QRectF(s * m, s * m, s * (1 - 2 * m), s * (1 - 2 * m)),
                      2, 2)


def icon_check(p, s):
    col = p.pen().color()
    p.setPen(QPen(col, 2.2))
    p.setBrush(QBrush(Qt.GlobalColor.transparent))
    path = QPainterPath()
    m = 0.24
    path.moveTo(s * m, s * 0.54)
    path.lineTo(s * 0.42, s * (1 - m))
    path.lineTo(s * (1 - m), s * m)
    p.drawPath(path)


def icon_cross(p, s):
    col = p.pen().color()
    p.setPen(QPen(col, 2.0))
    m = 0.26
    p.drawLine(s * m, s * m, s * (1 - m), s * (1 - m))
    p.drawLine(s * (1 - m), s * m, s * m, s * (1 - m))


def icon_note(p, s):
    col = p.pen().color()
    p.setPen(QPen(col, 1.6))
    p.setBrush(QBrush(col))
    path = QPainterPath()
    m = 0.26
    path.moveTo(s * (1 - m), s * m)
    path.lineTo(s * (1 - m), s * (0.70))
    path.cubicTo(s * (1 - m), s * 0.85, s * m, s * 0.92, s * m, s * 0.78)
    path.lineTo(s * m, s * 0.30)
    p.drawPath(path)
    p.setBrush(QBrush(col))
    p.drawEllipse(QRectF(s * m * 0.6, s * 0.70, s * 0.20, s * 0.20))


def icon_open_folder(p, s):
    icon_folder(p, s)
    col = p.pen().color()
    p.setPen(QPen(col, 1.6))
    # lines
    p.drawLine(QLineF(QPointF(s * 0.30, s * 0.62), QPointF(s * 0.70, s * 0.50)))


def get_icon(name, size=20, color=C_TEXT_DIM, dpr=1.0):
    funcs = {
        "plus": icon_plus, "folder": icon_folder, "trash": icon_trash,
        "refresh": icon_refresh, "play": icon_play, "stop": icon_stop,
        "check": icon_check, "cross": icon_cross, "note": icon_note,
        "open_folder": icon_open_folder,
    }
    f = funcs.get(name)
    if not f:
        return QPixmap()
    return make_icon_pixmap(f, size=size, color=color, device_pixel_ratio=dpr)


class IconButton(QPushButton):
    """Square flat icon button with rounded corners."""

    def __init__(self, icon_name, tip, size=34, icon_color=C_TEXT_DIM, on_click=None):
        super().__init__()
        self._icon_name = icon_name
        self._icon_color = icon_color
        self._size = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tip)
        self.setObjectName("iconBtn")
        self._on_click = on_click
        self._render_icon()
        self.clicked.connect(lambda: self._on_click and self._on_click())

    def _render_icon(self):
        dpr = self.devicePixelRatioF() or 1.0
        px = get_icon(self._icon_name, size=self._size * 0.5,
                      color=self._icon_color, dpr=dpr)
        self.setIcon(QIcon(px))
        self.setIconSize(QSize(int(self._size * 0.5), int(self._size * 0.5)))

    def set_icon_color(self, color):
        self._icon_color = color
        self._render_icon()


# --------------------------------------------------------------------------- #
# Toggle switch (no checkboxes)
# --------------------------------------------------------------------------- #
class ToggleSwitch(QWidget):
    def __init__(self, label_text, initial=False, on_toggle=None):
        super().__init__()
        self.setObjectName("toggleRow")
        self._state = initial
        self._on_toggle = on_toggle
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(12)
        self.label = QLabel(label_text)
        self.label.setObjectName("toggleLabel")
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._knob = _SwitchKnob(initial=self._state, toggled=self._toggle)
        lay.addWidget(self.label)
        lay.addStretch(1)
        lay.addWidget(self._knob)
        self.label.mousePressEvent = lambda e: self._toggle(not self._state)

    def _toggle(self, val):
        new = not self._state
        self._state = new
        self._knob.set_state(new)
        if self._on_toggle:
            self._on_toggle(new)

    def set_state(self, val):
        self._state = bool(val)
        self._knob.set_state(self._state)

    def state(self):
        return self._state

    def set_text(self, text):
        self.label.setText(text)


class _SwitchKnob(QWidget):
    SIZE_W = 44
    SIZE_H = 24

    def __init__(self, initial=False, toggled=None):
        super().__init__()
        self._state = initial
        self._toggled = toggled
        self.setFixedSize(self.SIZE_W, self.SIZE_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_state(self, val):
        self._state = bool(val)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._state = not self._state
            self.update()
            if self._toggled:
                self._toggled(self._state)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.SIZE_H / 2
        track = QColor(C_ACCENT) if self._state else QColor("#3A3A4A")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(track))
        p.drawRoundedRect(QRectF(0, 0, self.SIZE_W, self.SIZE_H), r, r)
        # knob
        kx = (self.SIZE_W - self.SIZE_H + 2) if self._state else 2
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawEllipse(QRectF(kx, 2, self.SIZE_H - 4, self.SIZE_H - 4))
        p.end()


# --------------------------------------------------------------------------- #
# Language pill switch
# --------------------------------------------------------------------------- #
class LangSwitch(QWidget):
    def __init__(self, lang, on_change):
        super().__init__()
        self._lang = lang
        self._on_change = on_change
        self.setFixedSize(76, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_lang(self, lang):
        self._lang = lang
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            new = "en" if self._lang == "ru" else "ru"
            self._lang = new
            self.update()
            if self._on_change:
                self._on_change(new)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        # capsule background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(C_INPUT)))
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        half = w / 2
        # active side
        active_is_ru = self._lang == "ru"
        p.setBrush(QBrush(QColor(C_ACCENT)))
        p.drawRoundedRect(
            QRectF(2 if active_is_ru else half, 2, half - 2, h - 4),
            (h - 4) / 2, (h - 4) / 2)
        # text
        p.setPen(QPen(QColor(C_TEXT)))
        f = p.font()
        f.setBold(True)
        f.setPointSize(9)
        p.setFont(f)
        ru_color = QColor(C_INPUT) if active_is_ru else QColor(C_TEXT_DIM)
        en_color = QColor(C_TEXT_DIM) if active_is_ru else QColor(C_INPUT)
        p.setPen(QPen(ru_color))
        p.drawText(QRectF(0, 0, half, h), Qt.AlignmentFlag.AlignCenter, "RU")
        p.setPen(QPen(en_color))
        p.drawText(QRectF(half, 0, half, h), Qt.AlignmentFlag.AlignCenter, "EN")
        p.end()


# --------------------------------------------------------------------------- #
# Card with drop shadow
# --------------------------------------------------------------------------- #
class Card(QFrame):
    def __init__(self, radius=20):
        super().__init__()
        self.setObjectName("card")
        self._radius = radius
        # Drop shadow via QSS box-shadow is unsupported in Qt; we emulate depth
        # using a subtle border + slightly lighter background. A real
        # QGraphicsDropShadowEffect causes access-violation crashes on some
        # Windows Qt6 builds when combined with QSS backgrounds, so we keep
        # the look purely via QSS (see #card rule).


# --------------------------------------------------------------------------- #
# Dotted dropzone (inside queue card)
# --------------------------------------------------------------------------- #
class Dropzone(QFrame):
    def __init__(self, hint_text, sub_text):
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self._hint = hint_text
        self._sub = sub_text
        self._hover = False

    def set_texts(self, hint, sub):
        self._hint = hint
        self._sub = sub
        self.update()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self._hover = True
            self.update()
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, _):
        self._hover = False
        self.update()

    def dropEvent(self, e):
        self._hover = False
        self.update()
        urls = e.mimeData().urls()
        paths = []
        for u in urls:
            if u.isLocalFile():
                paths.append(u.toLocalFile())
        if paths and self.window().__class__.__name__ == "MainWindow":
            self.window().add_paths(paths)
        e.acceptProposedAction()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(C_INPUT)))
        p.drawRoundedRect(r, 12, 12)
        # dotted border
        col = QColor(C_ACCENT) if self._hover else QColor(C_TEXT_DIM)
        pen = QPen(col, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([1, 4])
        p.setPen(pen)
        p.setBrush(Qt.GlobalBrush.NoBrush)
        p.setBrush(QBrush(Qt.GlobalColor.transparent))
        p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 12, 12)
        # text
        p.setPen(QPen(col))
        f = p.font()
        f.setPointSize(12)
        f.setBold(True)
        p.setFont(f)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._hint)
        p.end()


# --------------------------------------------------------------------------- #
# Queue list (custom delegate for progress bar in rows)
# --------------------------------------------------------------------------- #
class QueueTree(QTreeWidget):
    def __init__(self, lang):
        super().__init__()
        self.lang = lang
        self.setObjectName("queueTree")
        self.setHeaderHidden(False)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setAlternatingRowColors(False)
        self.setItemDelegate(QueueDelegate(self))
        self._configure_columns()

    def _configure_columns(self):
        self.setColumnCount(4)
        self.setHeaderLabels([tr(self.lang, "col_name"),
                              tr(self.lang, "col_size"),
                              tr(self.lang, "col_status"),
                              tr(self.lang, "col_progress")])
        self.setColumnWidth(0, 240)
        self.setColumnWidth(1, 70)
        self.setColumnWidth(2, 90)
        self.setColumnWidth(3, 80)
        # hide the root branch lines
        self.setStyleSheet(self.styleSheet())

    def retranslate(self, lang):
        self.lang = lang
        self.setHeaderLabels([tr(lang, "col_name"),
                              tr(lang, "col_size"),
                              tr(lang, "col_status"),
                              tr(lang, "col_progress")])

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = []
        for u in e.mimeData().urls():
            if u.isLocalFile():
                paths.append(u.toLocalFile())
        if paths:
            self.window().add_paths(paths)
        e.acceptProposedAction()


class QueueDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        # Draw selection background
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QBrush(QColor("#2E2E3A")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(option.rect)
        # Draw text columns
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = index.column()
        if col == 3:
            # progress column: draw a mini bar
            data = index.data(Qt.ItemDataRole.UserRole)
            pct = 0
            if isinstance(data, (int, float)):
                pct = int(data)
            status_text = ""
            smi = index.siblingAtColumn(2)
            if smi is not None:
                status_text = smi.data(Qt.ItemDataRole.DisplayRole) or ""
            r = option.rect.adjusted(6, 0, -6, 0)
            # track
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#2A2A36")))
            bar_h = 6
            br = QRectF(r.left(), r.center().y() - bar_h / 2, r.width(), bar_h)
            painter.drawRoundedRect(br, 3, 3)
            # fill
            if "processing" in str(status_text).lower() or pct > 0:
                fill = QColor(C_ACCENT)
                painter.setBrush(QBrush(fill))
                fr = QRectF(br.left(), br.top(), br.width() * pct / 100.0, bar_h)
                painter.drawRoundedRect(fr, 3, 3)
            painter.setPen(QPen(QColor(C_TEXT_DIM)))
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, f"{pct}%")
        else:
            painter.setPen(QPen(QColor(C_TEXT)))
            if col == 2:
                # status text colored
                status_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
                color = QColor(C_TEXT_DIM)
                low = str(status_text).lower()
                if any(w in low for w in ["done", "готово"]):
                    color = QColor("#39D98A")
                elif any(w in low for w in ["processing", "конверт"]):
                    color = QColor("#FFC53D")
                elif any(w in low for w in ["fail", "ошибк"]):
                    color = QColor(C_DANGER)
                elif any(w in low for w in ["skip", "пропуск"]):
                    color = QColor("#5B8DEF")
                painter.setPen(QPen(color))
            painter.drawText(option.rect.adjusted(8, 0, -8, 0),
                              Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                              str(index.data(Qt.ItemDataRole.DisplayRole) or ""))
        painter.restore()


# --------------------------------------------------------------------------- #
# Status dot indicator (with pulsing)
# --------------------------------------------------------------------------- #
class StatusDot(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(12, 12)
        self._state = "idle"
        self._opacity = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._phase = 0.0

    def set_state(self, state):
        self._state = state
        if state == "processing":
            self._timer.start(80)
        else:
            self._timer.stop()
            self._opacity = 1.0
        self.update()

    def _pulse(self):
        import math
        self._phase += 0.15
        self._opacity = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(self._phase))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._state == "done":
            col = QColor("#39D98A")
        elif self._state == "error":
            col = QColor(C_DANGER)
        elif self._state == "processing":
            col = QColor("#FFC53D")
            col.setAlphaF(self._opacity)
        else:
            col = QColor("#39D98A")
            col.setAlphaF(0.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        p.drawEllipse(QRectF(1, 1, 10, 10))
        p.end()


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self, dropped_files=None):
        super().__init__()
        self.settings = load_settings()
        self.lang = self.settings.get("lang") or default_lang()
        self.queue_files = []
        self.worker = None
        self._processing = False

        self.setWindowTitle(tr(self.lang, "title"))
        self.setStyleSheet(APP_QSS)
        # Window background + rounded (frameless-ish? keep standard window but dark)
        self.setObjectName("mainWindow")

        # Window icon
        try:
            self.setWindowIcon(QIcon(resource_path("ico.ico")))
        except Exception:
            pass

        # Restore geometry
        geo = self.settings.get("geometry")
        if geo:
            try:
                self.restoreGeometry(bytes.fromhex(geo))
            except Exception:
                self.resize(1080, 760)
        else:
            self.resize(1080, 760)

        self._build_ui()
        self._apply_lang()
        self._set_status(tr(self.lang, "status_ready", get_today_folder_name()), "idle")

        # enable drop on whole window
        self.setAcceptDrops(True)

        if dropped_files:
            QTimer.singleShot(150, lambda: self.add_paths(dropped_files))

    # ---- UI build ----
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        central.setContentsMargins(24, 24, 24, 18)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        # ---- Header ----
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(6, 0, 6, 0)
        hl.setSpacing(12)
        title = QLabel("EasyConvert")
        title.setObjectName("appTitle")
        hl.addWidget(title)
        hl.addStretch(1)
        self.update_btn = IconButton("refresh", tr(self.lang, "check_update"),
                                     size=36, icon_color=C_TEXT_DIM,
                                     on_click=self.check_update)
        hl.addWidget(self.update_btn)
        self.lang_switch = LangSwitch(self.lang, on_change=self._switch_lang)
        hl.addWidget(self.lang_switch)
        root.addWidget(header)

        # ---- Two cards: queue + output ----
        cards = QWidget()
        cl = QHBoxLayout(cards)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(20)

        # Left card: queue
        qcard = Card(radius=20)
        qcard_l = QVBoxLayout(qcard)
        qcard_l.setContentsMargins(20, 20, 20, 20)
        qcard_l.setSpacing(12)
        # header row
        qhdr = QHBoxLayout()
        qhdr.setContentsMargins(0, 0, 0, 0)
        qhdr.setSpacing(10)
        qh_icon = QLabel()
        qh_icon.setPixmap(get_icon("note", 18, C_ACCENT, self.devicePixelRatioF()))
        qh_icon.setFixedSize(20, 20)
        qhdr.addWidget(qh_icon)
        self.queue_title = QLabel(tr(self.lang, "queue"))
        self.queue_title.setObjectName("cardTitle")
        qhdr.addWidget(self.queue_title)
        qhdr.addStretch(1)
        self.add_file_btn = IconButton("plus", tr(self.lang, "add_file_tip"),
                                       size=34, icon_color=C_TEXT, on_click=self.choose_files)
        qhdr.addWidget(self.add_file_btn)
        self.add_folder_btn = IconButton("folder", tr(self.lang, "add_folder_tip"),
                                         size=34, icon_color=C_TEXT, on_click=self.choose_folder)
        qhdr.addWidget(self.add_folder_btn)
        self.clear_btn = IconButton("trash", tr(self.lang, "clear_tip"),
                                    size=34, icon_color=C_DANGER, on_click=self.clear_input)
        qhdr.addWidget(self.clear_btn)
        qcard_l.addLayout(qhdr)
        # dropzone
        self.dropzone = Dropzone(tr(self.lang, "drop_hint"),
                                 tr(self.lang, "drop_sub"))
        self.dropzone.setMinimumHeight(120)
        qcard_l.addWidget(self.dropzone, 0)
        # queue tree
        self.queue_tree = QueueTree(self.lang)
        self.queue_tree.setMinimumHeight(200)
        qcard_l.addWidget(self.queue_tree, 1)
        cl.addWidget(qcard, 1)

        # Right card: output
        ocard = Card(radius=20)
        ocard_l = QVBoxLayout(ocard)
        ocard_l.setContentsMargins(20, 20, 20, 20)
        ocard_l.setSpacing(12)
        ohdr = QHBoxLayout()
        ohdr.setContentsMargins(0, 0, 0, 0)
        ohdr.setSpacing(10)
        oh_icon = QLabel()
        oh_icon.setPixmap(get_icon("check", 18, "#39D98A", self.devicePixelRatioF()))
        oh_icon.setFixedSize(20, 20)
        ohdr.addWidget(oh_icon)
        self.out_title = QLabel(tr(self.lang, "done_mp3"))
        self.out_title.setObjectName("cardTitle")
        ohdr.addWidget(self.out_title)
        ohdr.addStretch(1)
        self.open_folder_btn = IconButton("open_folder", tr(self.lang, "open_folder_tip"),
                                          size=34, icon_color=C_TEXT, on_click=self.open_output_folder)
        ohdr.addWidget(self.open_folder_btn)
        self.clear_out_btn = IconButton("trash", tr(self.lang, "clear_tip"),
                                        size=34, icon_color=C_DANGER, on_click=self.clear_output)
        ohdr.addWidget(self.clear_out_btn)
        ocard_l.addLayout(ohdr)
        # output tree (simple)
        self.output_tree = QTreeWidget()
        self.output_tree.setObjectName("queueTree")
        self.output_tree.setHeaderHidden(False)
        self.output_tree.setRootIsDecorated(False)
        self.output_tree.setUniformRowHeights(True)
        self.output_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.output_tree.setColumnCount(3)
        self.output_tree.setHeaderLabels([tr(self.lang, "col_name"),
                                          tr(self.lang, "col_path"),
                                          tr(self.lang, "col_size")])
        self.output_tree.setColumnWidth(0, 200)
        self.output_tree.setColumnWidth(1, 220)
        self.output_tree.setColumnWidth(2, 70)
        self.output_tree.itemDoubleClicked.connect(self._open_selected_output)
        ocard_l.addWidget(self.output_tree, 1)
        cl.addWidget(ocard, 1)

        root.addWidget(cards, 1)

        # ---- Bottom card: settings + actions ----
        bcard = Card(radius=20)
        bcard_l = QHBoxLayout(bcard)
        bcard_l.setContentsMargins(24, 20, 24, 20)
        bcard_l.setSpacing(32)

        # Left: settings (3 columns)
        settings_w = QWidget()
        sl = QHBoxLayout(settings_w)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(36)

        # Audio group
        audio_col = self._setting_column(tr(self.lang, "audio"))
        self.bitrate_cb = self._dark_combobox(["320k", "256k", "192k", "128k", "96k"])
        self.bitrate_cb.setCurrentText(self.settings.get("bitrate", "320k"))
        audio_col_layout = audio_col.layout()
        audio_col_layout.addWidget(self._labeled(tr(self.lang, "bitrate"), self.bitrate_cb))
        self.channels_cb = self._dark_combobox(["1", "2"])
        self.channels_cb.setCurrentText(str(self.settings.get("channels", "2")))
        audio_col_layout.addWidget(self._labeled(tr(self.lang, "channels"), self.channels_cb))
        sl.addWidget(audio_col)

        # Control group
        ctrl_col = self._setting_column(tr(self.lang, "control"))
        import multiprocessing as _mp
        maxw = max(1, _mp.cpu_count() or 4)
        self.workers_sp = QSpinBox()
        self.workers_sp.setObjectName("darkControl")
        self.workers_sp.setRange(1, maxw)
        self.workers_sp.setValue(self.settings.get("workers", 0) or min(4, maxw))
        ctrl_col.layout().addWidget(self._labeled(tr(self.lang, "workers"), self.workers_sp))
        # toggles under control? Put toggles in a separate group below paths
        sl.addWidget(ctrl_col)

        # Paths group
        paths_col = self._setting_column(tr(self.lang, "paths"))
        self.out_mode_cb = self._dark_combobox(["date", "source", "custom"])
        self.out_mode_cb.setCurrentText(self.settings.get("out_mode", "date"))
        self.out_mode_cb.currentTextChanged.connect(self._on_out_mode_changed)
        paths_col.layout().addWidget(self._labeled(tr(self.lang, "out_mode"), self.out_mode_cb))
        self.collision_cb = self._dark_combobox(["suffix", "overwrite", "skip"])
        self.collision_cb.setCurrentText(self.settings.get("collision", "suffix"))
        paths_col.layout().addWidget(self._labeled(tr(self.lang, "collision"), self.collision_cb))
        sl.addWidget(paths_col)

        bcard_l.addWidget(settings_w, 1)

        # Toggles row (small, above actions)
        toggles_w = QWidget()
        tl = QVBoxLayout(toggles_w)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)
        self.keep_native_t = ToggleSwitch(tr(self.lang, "keep_native"),
                                          self.settings.get("keep_native_rate", False))
        self.keep_tags_t = ToggleSwitch(tr(self.lang, "keep_tags"),
                                        self.settings.get("keep_tags", True))
        self.normalize_t = ToggleSwitch(tr(self.lang, "normalize"),
                                        self.settings.get("normalize", False))
        self.recursive_t = ToggleSwitch(tr(self.lang, "recursive"),
                                        self.settings.get("recursive", True))
        # store labels for retranslation
        self._toggle_widgets = [
            (self.keep_native_t, "keep_native"),
            (self.keep_tags_t, "keep_tags"),
            (self.normalize_t, "normalize"),
            (self.recursive_t, "recursive"),
        ]
        for t, _ in self._toggle_widgets:
            tl.addWidget(t)
        bcard_l.addWidget(toggles_w, 1)

        # Right: actions
        actions_w = QWidget()
        al = QVBoxLayout(actions_w)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(12)
        # Start button
        self.start_btn = QPushButton(tr(self.lang, "start"))
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_btn.setMinimumHeight(52)
        self.start_btn.clicked.connect(self.start_processing)
        # Stop button
        self.stop_btn = QPushButton(tr(self.lang, "stop"))
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.stop_btn.setMinimumHeight(44)
        self.stop_btn.clicked.connect(self.stop_processing)
        al.addWidget(self.start_btn)
        al.addWidget(self.stop_btn)
        bcard_l.addWidget(actions_w, 1)

        root.addWidget(bcard, 0)

        # ---- Status bar ----
        sb = QWidget()
        sb_l = QHBoxLayout(sb)
        sb_l.setContentsMargins(10, 0, 10, 0)
        sb_l.setSpacing(10)
        self.status_dot = StatusDot()
        sb_l.addWidget(self.status_dot)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusText")
        sb_l.addWidget(self.status_label)
        sb_l.addStretch(1)
        self.ver_label = QLabel(f"v{APP_VERSION}")
        self.ver_label.setObjectName("verText")
        sb_l.addWidget(self.ver_label)
        root.addWidget(sb)

        # progress bar (thin)
        self.progress = QProgressBar()
        self.progress.setObjectName("thinProgress")
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

    def _setting_column(self, title):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("groupTitle")
        lay.addWidget(title_lbl)
        # store for retranslation
        if not hasattr(self, "_group_titles"):
            self._group_titles = []
        self._group_titles.append((title_lbl, title))
        return w

    def _dark_combobox(self, values):
        cb = QComboBox()
        cb.setObjectName("darkCombo")
        cb.addItems(values)
        return cb

    def _labeled(self, label_text, control):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setObjectName("fieldLabel")
        lay.addWidget(lbl)
        lay.addWidget(control)
        return w

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
        self.setWindowTitle(tr(L, "title"))
        self.queue_title.setText(tr(L, "queue"))
        self.out_title.setText(tr(L, "done_mp3"))
        self.dropzone.set_texts(tr(L, "drop_hint"), tr(L, "drop_sub"))
        self.update_btn.setToolTip(tr(L, "check_update"))
        self.add_file_btn.setToolTip(tr(L, "add_file_tip"))
        self.add_folder_btn.setToolTip(tr(L, "add_folder_tip"))
        self.clear_btn.setToolTip(tr(L, "clear_tip"))
        self.open_folder_btn.setToolTip(tr(L, "open_folder_tip"))
        self.clear_out_btn.setToolTip(tr(L, "clear_tip"))
        self.start_btn.setText(tr(L, "start"))
        self.stop_btn.setText(tr(L, "stop"))
        self.queue_tree.retranslate(L)
        self.output_tree.setHeaderLabels([tr(L, "col_name"), tr(L, "col_path"), tr(L, "col_size")])
        for title_lbl, title_key in getattr(self, "_group_titles", []):
            title_lbl.setText(tr(L, title_key))
        for t, key in getattr(self, "_toggle_widgets", []):
            t.set_text(tr(L, key))

    # ---- file picking ----
    def choose_files(self):
        from PyQt6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(
            self, tr(self.lang, "msg_pick_files"), "",
            f"{tr(self.lang, 'audio_files')} (*{' *'.join(sorted(AUDIO_EXTS))});;"
            f"{tr(self.lang, 'all_files')} (*.*)")
        if files:
            self.add_paths(list(files))

    def choose_folder(self):
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, tr(self.lang, "msg_pick_folder"))
        if folder:
            self.add_paths([folder])

    def choose_custom_out(self):
        from PyQt6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, tr(self.lang, "msg_pick_output"))
        if d:
            self.settings["custom_out"] = d
            self.out_mode_cb.setCurrentText("custom")
            save_settings(self.settings)

    def _on_out_mode_changed(self, val):
        if val == "custom" and not self.settings.get("custom_out"):
            self.choose_custom_out()

    def add_paths(self, paths):
        files = collect_audio_files_from_paths(paths, self.recursive_t.state())
        added = 0
        existing = set(self.queue_files)
        for f in files:
            if f not in existing:
                self.queue_files.append(f)
                existing.add(f)
                added += 1
        self._refresh_queue_tree()
        if added:
            self._set_status(tr(self.lang, "status_added", added), "idle")
        else:
            self._set_status(tr(self.lang, "status_empty_queue"), "idle")

    def _refresh_queue_tree(self):
        self.queue_tree.clear()
        for i, f in enumerate(self.queue_files):
            try:
                size = human_size(os.path.getsize(f))
            except Exception:
                size = "—"
            it = QTreeWidgetItem([os.path.basename(f), size,
                                  tr(self.lang, "st_pending"), "0%"])
            it.setData(3, Qt.ItemDataRole.UserRole, 0)
            it.setForeground(2, QColor(C_TEXT_DIM))
            self.queue_tree.addTopLevelItem(it)
        self._toggle_empty_state()

    def _toggle_empty_state(self):
        has = self.queue_tree.topLevelItemCount() > 0
        self.dropzone.setVisible(not has)
        self.queue_tree.setVisible(has)
        # re-layout
        self.centralWidget().updateGeometry()

    def clear_input(self):
        if not self.queue_files:
            return
        if not self._confirm(tr(self.lang, "confirm_clear")):
            return
        self.queue_files.clear()
        self._refresh_queue_tree()
        self._set_status(tr(self.lang, "status_ready", get_today_folder_name()), "idle")

    def clear_output(self):
        if not self.output_tree.topLevelItemCount():
            return
        if not self._confirm(tr(self.lang, "confirm_clear")):
            return
        self.output_tree.clear()

    def _confirm(self, text):
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setStyleSheet(APP_QSS)
        return box.exec() == QMessageBox.StandardButton.Yes

    def open_output_folder(self):
        sel = self.output_tree.selectedItems()
        if sel:
            path = sel[0].text(1)
            try:
                self._startfile(path)
                return
            except Exception:
                pass
        try:
            self._startfile(get_or_create_today_folder())
        except Exception as e:
            self._set_status(f"open folder failed: {e}", "error")

    def _startfile(self, path):
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])

    def _open_selected_output(self, item):
        name = item.text(0)
        folder = item.text(1)
        full = os.path.join(folder, name + ("" if name.lower().endswith(".mp3") else ".mp3"))
        try:
            self._startfile(full)
        except Exception:
            try:
                self._startfile(folder)
            except Exception:
                pass

    # ---- processing ----
    def _collect_settings(self):
        self.settings["bitrate"] = self.bitrate_cb.currentText()
        self.settings["channels"] = self.channels_cb.currentText()
        try:
            self.settings["workers"] = int(self.workers_sp.value())
        except Exception:
            self.settings["workers"] = 1
        self.settings["out_mode"] = self.out_mode_cb.currentText()
        self.settings["collision"] = self.collision_cb.currentText()
        self.settings["keep_native_rate"] = bool(self.keep_native_t.state())
        self.settings["keep_tags"] = bool(self.keep_tags_t.state())
        self.settings["normalize"] = bool(self.normalize_t.state())
        self.settings["recursive"] = bool(self.recursive_t.state())
        save_settings(self.settings)

    def start_processing(self):
        self._collect_settings()
        if not self.queue_files:
            self._set_status(tr(self.lang, "status_empty_queue"), "idle")
            return
        if self._processing:
            return
        self._processing = True
        self._set_ui_busy(True)
        self.progress.setValue(0)
        self.worker = ConvertWorker(list(self.queue_files), self.settings, self.lang)
        self.worker.progress.connect(self._on_progress)
        self.worker.item_status.connect(self._on_item_status)
        self.worker.output_ready.connect(self._add_output)
        self.worker.finished_run.connect(self._on_done)
        self.worker.cancelled.connect(lambda: self._set_status(
            tr(self.lang, "status_cancelled"), "error"))
        self.worker.log_line.connect(lambda s: log.info(s))
        self.worker.start()

    def stop_processing(self):
        if self.worker:
            self.worker.cancel()
        self._set_status(tr(self.lang, "status_cancelled"), "error")

    def _on_progress(self, index, total, pct, name):
        overall = int(((index - 1) / max(total, 1)) * 100) + int(pct / max(total, 1))
        overall = max(0, min(100, overall))
        self.progress.setValue(overall)
        self._set_status(tr(self.lang, "status_processing", index, total, name), "processing")
        # update row progress
        if 0 < index <= self.queue_tree.topLevelItemCount():
            it = self.queue_tree.topLevelItem(index - 1)
            it.setData(3, Qt.ItemDataRole.UserRole, pct)
            it.setText(3, f"{pct}%")
            it.setText(2, tr(self.lang, "st_processing"))
            self.queue_tree.viewport().update()

    def _on_item_status(self, index, status, path):
        if not (0 < index <= self.queue_tree.topLevelItemCount()):
            return
        it = self.queue_tree.topLevelItem(index - 1)
        label_map = {"pending": "st_pending", "processing": "st_processing",
                     "done": "st_done", "failed": "st_failed",
                     "skipped": "st_skipped"}
        label = tr(self.lang, label_map.get(status, "st_failed"))
        it.setText(2, label)
        if status == "done":
            it.setData(3, Qt.ItemDataRole.UserRole, 100)
            it.setText(3, "100%")
        elif status == "failed":
            it.setText(3, "!")
        self.queue_tree.viewport().update()

    def _add_output(self, path):
        name = os.path.basename(path)
        folder = os.path.dirname(path)
        try:
            size_s = human_size(os.path.getsize(path))
        except Exception:
            size_s = "—"
        it = QTreeWidgetItem([name, folder, size_s])
        self.output_tree.addTopLevelItem(it)
        self.output_tree.scrollToBottom()

    def _on_done(self, ok, fail, skip, total):
        self._processing = False
        self._set_ui_busy(False)
        self.progress.setValue(0)
        state = "error" if fail > 0 else "done"
        self._set_status(tr(self.lang, "status_done", ok, total, fail, skip), state)

    # ---- helpers ----
    def _set_status(self, msg, state="idle"):
        self.status_label.setText(msg)
        self.status_dot.set_state(state)

    def _set_ui_busy(self, busy):
        self.start_btn.setEnabled(not busy)
        self.add_file_btn.setEnabled(not busy)
        self.add_folder_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)

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

    # ---- DnD on whole window ----
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = []
        for u in e.mimeData().urls():
            if u.isLocalFile():
                paths.append(u.toLocalFile())
        if paths:
            self.add_paths(paths)
        e.acceptProposedAction()

    # ---- close ----
    def closeEvent(self, e):
        try:
            self.settings["geometry"] = self.saveGeometry().toHex().data().decode()
        except Exception:
            pass
        self._collect_settings()
        if self._processing and self.worker:
            self.worker.cancel()
            self.worker.wait(2000)
        super().closeEvent(e)


def _ver_gt(a, b):
    def parts(x):
        return [int(p) for p in re.findall(r"\d+", x) or "0"]
    return parts(a) > parts(b)


# --------------------------------------------------------------------------- #
# QSS stylesheet
# --------------------------------------------------------------------------- #
APP_QSS = f"""
* {{
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    color: {C_TEXT};
    outline: none;
}}
#mainWindow, QMainWindow {{
    background: {C_MAIN_BG};
}}
#central {{
    background: {C_MAIN_BG};
}}
#appTitle {{
    color: {C_TEXT};
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 0.5px;
}}
#cardTitle {{
    color: {C_TEXT};
    font-size: 14px;
    font-weight: 700;
}}
#groupTitle {{
    color: {C_TEXT_DIM};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
#fieldLabel {{
    color: {C_TEXT_DIM};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
#card {{
    background: {C_CARD};
    border: 1px solid #2A2A36;
    border-radius: 20px;
}}
#iconBtn {{
    background: {C_INPUT};
    border: none;
    border-radius: 12px;
}}
#iconBtn:hover {{
    background: #2F2F3E;
}}
#iconBtn:disabled {{
    background: #1F1F29;
    color: #4A4A5A;
}}
#darkCombo, QComboBox {{
    background: {C_INPUT};
    border: 1px solid #2A2A36;
    border-radius: 12px;
    padding: 8px 12px;
    color: {C_TEXT};
    min-height: 18px;
    font-size: 12px;
}}
#darkCombo:hover {{
    border: 1px solid #3A3A4A;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {C_TEXT_DIM};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {C_INPUT};
    border: 1px solid #2A2A36;
    border-radius: 8px;
    selection-background-color: #2F2F3E;
    color: {C_TEXT};
    padding: 4px;
    outline: none;
}}
#darkControl, QSpinBox {{
    background: {C_INPUT};
    border: 1px solid #2A2A36;
    border-radius: 12px;
    padding: 8px 12px;
    color: {C_TEXT};
    min-height: 18px;
    font-size: 12px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: transparent;
    border: none;
    width: 18px;
}}
QSpinBox::up-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {C_TEXT_DIM};
}}
QSpinBox::down-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C_TEXT_DIM};
}}
#startBtn {{
    background: {C_ACCENT};
    color: #000000;
    border: none;
    border-radius: 14px;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 1px;
}}
#startBtn:hover {{
    background: #5CF5FF;
}}
#startBtn:disabled {{
    background: #1F8E96;
    color: #0A3A3D;
}}
#stopBtn {{
    background: {C_INPUT};
    color: {C_DANGER};
    border: 1px solid {C_DANGER};
    border-radius: 14px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
}}
#stopBtn:hover {{
    background: #2A1A22;
}}
#toggleLabel {{
    color: {C_TEXT};
    font-size: 11px;
    font-weight: 500;
}}
#statusText {{
    color: {C_TEXT_DIM};
    font-size: 11px;
}}
#verText {{
    color: {C_TEXT_DIM};
    font-size: 10px;
}}
#thinProgress, QProgressBar {{
    background: {C_INPUT};
    border: none;
    border-radius: 2px;
}}
QProgressBar::chunk {{
    background: {C_ACCENT};
    border-radius: 2px;
}}
/* Tree / queue */
#queueTree, QTreeWidget {{
    background: {C_INPUT};
    border: 1px solid #2A2A36;
    border-radius: 12px;
    color: {C_TEXT};
    outline: none;
    font-size: 12px;
    padding: 2px;
}}
QTreeWidget::item {{
    padding: 6px 4px;
    border: none;
}}
QTreeWidget::item:selected {{
    background: #2E2E3A;
}}
QTreeWidget::branch {{
    background: transparent;
}}
QHeaderView::section {{
    background: {C_INPUT};
    color: {C_TEXT_DIM};
    border: none;
    border-bottom: 1px solid #2A2A36;
    padding: 6px 8px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
QHeaderView {{
    background: transparent;
}}
/* Custom scrollbars — thin & dark */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px;
}}
QScrollBar::handle:vertical {{
    background: #3A3A4A;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C_ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 4px;
}}
QScrollBar::handle:horizontal {{
    background: #3A3A4A;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {C_ACCENT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QToolTip {{
    background: {C_INPUT};
    color: {C_TEXT};
    border: 1px solid #2A2A36;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}}
QMessageBox {{
    background: {C_CARD};
}}
QMessageBox QLabel {{
    color: {C_TEXT};
    font-size: 12px;
}}
QMessageBox QPushButton {{
    background: {C_INPUT};
    color: {C_TEXT};
    border: 1px solid #2A2A36;
    border-radius: 8px;
    padding: 6px 16px;
    min-width: 60px;
}}
QMessageBox QPushButton:hover {{
    background: #2F2F3E;
}}
"""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def run_cli(files, settings):
    L = settings.get("lang") or default_lang()
    total = len(files)
    ok = fail = skip = 0
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
    # CLI mode
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

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # High-DPI: rely on default style; Fusion can conflict with our QSS on
    # some Windows builds.
    sys.exit(app.exec())
    win = MainWindow(dropped_files=dropped if dropped else None)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
