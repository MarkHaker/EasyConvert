# -*- coding: utf-8 -*-
"""
Audio -> MP3 converter.

Drag & drop any audio file(s) into the window (or use the button).
Files are converted to MP3 (320 kbps) keeping the original name,
saved into a folder named by today's date (YYYY-MM-DD).
A new date-folder is created automatically whenever the date changes.
Folders are created next to the program (same directory as the .exe / .py).
"""

import os
import sys
import re
import shutil
import threading
import datetime
import tkinter as tk
from tkinter import ttk, filedialog

import imageio_ffmpeg  # noqa: F401  (provides ffmpeg binary fallback in dev mode)
from pydub import AudioSegment

try:
    import tkinterdnd2  # noqa: F401
    _HAS_DND = True
except Exception:
    _HAS_DND = False


def is_frozen():
    return getattr(sys, "frozen", False)


def get_base_dir():
    """Directory where the program lives (exe folder or script folder)."""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _setup_ffmpeg_in_path():
    """Make ffmpeg/ffprobe discoverable by pydub (which uses PATH lookup).

    Bundled ffmpeg.exe and ffprobe.exe live in the PyInstaller _MEIPASS dir
    (added via --add-binary) and, in dev mode, next to this script.
    """
    base = get_base_dir()
    candidates = [base]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and meipass != base:
        candidates.append(meipass)

    path_sep = os.pathsep
    existing = os.environ.get("PATH", "").split(path_sep)
    for c in candidates:
        if c and os.path.isdir(c) and c not in existing:
            existing.insert(0, c)
    os.environ["PATH"] = path_sep.join(existing)

    # Tell pydub explicitly where ffmpeg is, if we can find one.
    for c in candidates:
        cand = os.path.join(c, "ffmpeg.exe")
        if os.path.exists(cand):
            try:
                AudioSegment.converter = cand
            except Exception:
                pass
            break


# Make ffmpeg/ffprobe findable before any pydub call runs.
_setup_ffmpeg_in_path()


def get_today_folder_name():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def get_or_create_today_folder():
    folder_path = os.path.join(get_base_dir(), get_today_folder_name())
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def is_audio_ext(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return bool(ext)


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


def convert_one_file(input_path, index, total):
    """Convert a single audio file to mp3. Returns (ok, message)."""
    try:
        if not os.path.isfile(input_path):
            return False, f"Файл не найден: {input_path}"

        name_no_ext = os.path.splitext(os.path.basename(input_path))[0]
        ext = os.path.splitext(input_path)[1].lower().lstrip(".")

        out_dir = get_or_create_today_folder()
        out_path = os.path.join(out_dir, name_no_ext + ".mp3")
        counter = 1
        while os.path.exists(out_path):
            out_path = os.path.join(out_dir, f"{name_no_ext}_{counter}.mp3")
            counter += 1

        audio = None
        last_err = None
        # First try letting ffmpeg auto-detect the container/codec.
        try:
            audio = AudioSegment.from_file(input_path)
        except Exception as e:
            last_err = e
            # Force the format hint.
            if ext:
                try:
                    audio = AudioSegment.from_file(input_path, format=ext)
                except Exception as e2:
                    last_err = e2

        if audio is None:
            raise RuntimeError(
                f"Не удалось декодировать файл (.{ext}). "
                f"ffmpeg не смог разобрать этот формат. {last_err}"
            )

        audio.export(
            out_path,
            format="mp3",
            bitrate="320k",
            parameters=["-ar", "44100", "-ac", "2"],
        )

        return True, f"[OK] [{index}/{total}] {os.path.basename(out_path)}  ->  {os.path.basename(out_dir)}/"
    except Exception as e:
        return False, f"[FAIL] [{index}/{total}] {os.path.basename(input_path)}: {e}"


# Choose base class depending on dnd availability
if _HAS_DND:
    import tkinterdnd2
    _BaseRoot = tkinterdnd2.Tk
else:
    _BaseRoot = tk.Tk


class DropWindow(_BaseRoot):
    def __init__(self):
        super().__init__()
        self.title("Audio -> MP3")
        self.geometry("600x480")
        self.configure(bg="#1e1e2e")
        self.minsize(420, 360)

        self.queue = []
        self.queue_lock = threading.Lock()
        self.processing = False

        self._build_ui()

        if _HAS_DND:
            self.drop_frame.drop_target_register(tkinterdnd2.DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_frame.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            self.drop_frame.dnd_bind("<<DropLeave>>", self._on_drop_leave)

        self.update_status_ready()

    def _build_ui(self):
        # Drop zone
        self.drop_frame = tk.Frame(
            self,
            bg="#2a2a3c",
            highlightbackground="#5b5b8a",
            highlightthickness=2,
            bd=0,
        )
        self.drop_frame.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        self.drop_label = tk.Label(
            self.drop_frame,
            text="БРОСЬ СЮДА ЛЮБОЕ АУДИО\nВ ЛЮБОМ ФОРМАТЕ\n\nа я его превращу в MP3",
            fg="#cdd6f4",
            bg="#2a2a3c",
            font=("Segoe UI", 16, "bold"),
            justify="center",
        )
        self.drop_label.place(relx=0.5, rely=0.45, anchor="center")

        self.sub_label = tk.Label(
            self.drop_frame,
            text="(или нажми кнопку ниже и выбери файлы)",
            fg="#7f7fa0",
            bg="#2a2a3c",
            font=("Segoe UI", 10),
        )
        self.sub_label.place(relx=0.5, rely=0.8, anchor="center")

        # Buttons
        btn_frame = tk.Frame(self, bg="#1e1e2e")
        btn_frame.pack(fill="x", padx=16, pady=(0, 4))

        self.choose_btn = tk.Button(
            btn_frame,
            text="Выбрать файлы",
            command=self.choose_files,
            bg="#cba6f7",
            fg="#1e1e2e",
            activebackground="#b4befe",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
        )
        self.choose_btn.pack(side="left", padx=(0, 8))

        self.open_folder_btn = tk.Button(
            btn_frame,
            text="Открыть папку с MP3",
            command=self.open_today_folder,
            bg="#89b4fa",
            fg="#1e1e2e",
            activebackground="#b4befe",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
        )
        self.open_folder_btn.pack(side="left")

        # Progress
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=16, pady=(8, 4))

        # Status line
        self.status_var = tk.StringVar(value="Готов к работе.")
        self.status_label = tk.Label(
            self,
            textvariable=self.status_var,
            fg="#a6adc8",
            bg="#1e1e2e",
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=560,
        )
        self.status_label.pack(fill="x", padx=16, pady=(0, 2))

        # Log box
        self.log_text = tk.Text(
            self,
            height=7,
            bg="#181825",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            font=("Consolas", 9),
            bd=0,
            wrap="word",
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=False, padx=16, pady=(0, 16))

        # Style
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Horizontal.TProgressbar", troughcolor="#181825", background="#a6e3a1")

    # ---- DnD callbacks ----
    def _on_drop_enter(self, event):
        self.drop_frame.config(highlightbackground="#cba6f7")

    def _on_drop_leave(self, event):
        self.drop_frame.config(highlightbackground="#5b5b8a")

    def _on_drop(self, event):
        self.drop_frame.config(highlightbackground="#5b5b8a")
        files = parse_dropped_files(event.data)
        self.add_files(files)

    # ---- File picking ----
    def choose_files(self):
        files = filedialog.askopenfilenames(
            title="Выбери аудио файлы",
            filetypes=[("Все файлы", "*.*")],
        )
        if files:
            self.add_files(list(files))

    def add_files(self, files):
        added = 0
        with self.queue_lock:
            for f in files:
                if os.path.isfile(f):
                    self.queue.append(f)
                    added += 1
        if added:
            self.log(f"Добавлено файлов: {added}")
            if not self.processing:
                threading.Thread(target=self.process_queue, daemon=True).start()

    # ---- Conversion worker ----
    def process_queue(self):
        self.processing = True
        self.set_ui_busy(True)
        try:
            while True:
                with self.queue_lock:
                    if not self.queue:
                        break
                    files = list(self.queue)
                    self.queue.clear()
                total = len(files)
                self._set_status(f"В очереди {total} файл(ов)...")
                for i, f in enumerate(files, start=1):
                    self._set_status(f"Конвертирую [{i}/{total}]: {os.path.basename(f)}")
                    self._set_progress(int((i - 1) / total * 100))
                    ok, message = convert_one_file(f, i, total)
                    self.log(message)
                    self._set_progress(int(i / total * 100))
            self.update_status_ready()
        finally:
            self.processing = False
            self.set_ui_busy(False)
            self._set_progress(0)

    # ---- UI helpers ----
    def _set_status(self, msg):
        self.after(0, lambda m=msg: self.status_var.set(m))

    def _set_progress(self, val):
        self.after(0, lambda v=val: self.progress.config(value=v))

    def set_ui_busy(self, busy):
        def _do():
            state = "disabled" if busy else "normal"
            self.choose_btn.config(state=state)
            self.open_folder_btn.config(state=state)
            if busy:
                self.drop_label.config(text="Конвертирую...\nпожалуйста, подожди")
            else:
                self.drop_label.config(text="БРОСЬ СЮДА ЛЮБОЕ АУДИО\nВ ЛЮБОМ ФОРМАТЕ\n\nа я его превращу в MP3")
        self.after(0, _do)

    def update_status_ready(self):
        self.status_var.set("Готов к работе. Папка вывода: " + get_today_folder_name())

    def log(self, msg):
        def _do():
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(0, _do)

    def open_today_folder(self):
        folder = get_or_create_today_folder()
        try:
            os.startfile(folder)
        except Exception as e:
            self.log(f"Не удалось открыть папку: {e}")


def run_cli(files):
    """Headless conversion: convert given files and print results."""
    total = len(files)
    ok_count = 0
    for i, f in enumerate(files, start=1):
        ok, msg = convert_one_file(f, i, total)
        print(msg, flush=True)
        if ok:
            ok_count += 1
    print(f"\nГотово: {ok_count}/{total} успешно.", flush=True)
    out_dir = get_or_create_today_folder()
    print("Папка вывода:", out_dir, flush=True)


def main():
    # CLI mode: ogg_to_mp3 --cli file1 file2 ...
    if len(sys.argv) >= 2 and sys.argv[1] == "--cli":
        files = sys.argv[2:]
        if not files:
            print("Нет файлов для конвертации.")
            return 1
        return run_cli(files)

    # GUI mode: also accept files dropped onto the exe (argv paths).
    dropped_files = []
    if len(sys.argv) >= 2:
        for arg in sys.argv[1:]:
            if os.path.exists(arg):
                dropped_files.append(arg)

    app = DropWindow()
    if dropped_files:
        app.add_files(dropped_files)
    app.mainloop()


if __name__ == "__main__":
    main()
