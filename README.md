# 🎵 EasyConvert

<p align="center">
  <b>Drag &amp; drop any audio file — get an MP3. Just that.</b><br/>
  <b>Перетащи любое аудио — получишь MP3. Вот так просто.</b>
</p>

<p align="center">
  <a href="https://github.com/MarkHaker/EasyConvert/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/MarkHaker/EasyConvert?style=flat-square"></a>
  <a href="https://github.com/MarkHaker/EasyConvert/releases/latest"><img alt="Downloads" src="https://img.shields.io/github/downloads/MarkHaker/EasyConvert/total?style=flat-square"></a>
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-blue?style=flat-square">
  <img alt="License" src="https://img.shields.io/github/license/MarkHaker/EasyConvert?style=flat-square">
  <img alt="Python" src="https://img.shields.io/badge/python-3.14-yellow?style=flat-square">
</p>

---

🌐 **Choose language / Выберите язык:**
&nbsp;[**English**](#-english) &nbsp;|&nbsp; [**Русский**](#-русский)

---

## 🇬🇧 English

### What is this?
**EasyConvert** is a tiny, standalone Windows application that converts **any audio file into MP3**.
Drag an audio file into the window (or drop it onto the `.exe`) — and it becomes an MP3, saved into a folder named by today's date, next to the program. That's it.

### Features
- 🎯 **Any audio format** — OGG, WAV, FLAC, AAC, M4A, WMA, MP3, AC3, OPUS, AIFF, and dozens more (everything `ffmpeg` understands).
- 🖱️ **Drag &amp; drop** — drop files into the window *or* directly onto the EXE.
- 🗂️ **Auto-dated folders** — output goes to a folder named `YYYY-MM-DD` (a new folder is created automatically when the date changes).
- 🏷️ **Same filename** — `song.ogg` → `song.mp3` (auto-renames on collisions).
- 🎚️ **MP3 320 kbps**, 44.1 kHz, stereo.
- 📦 **Single standalone EXE** — no dependencies, no installation, works on any Windows PC. `ffmpeg`/`ffprobe` are bundled inside.
- 🌑 Clean dark UI in Russian: *"Брось сюда любое аудио в любом формате — а я его превращу в MP3"*.

### Download &amp; use
1. Go to [Releases](https://github.com/MarkHaker/EasyConvert/releases/latest) and download **`ogg_to_mp3.exe`**.
2. Put it anywhere (Desktop, USB stick — doesn't matter).
3. Either open it and drag audio into the window, **or** drag audio files straight onto `ogg_to_mp3.exe`.
4. MP3s appear in a `YYYY-MM-DD` folder next to the program.

> ⚠️ MIDI/tracker formats (`.mid`, `.mod`, `.s3m`, `.xm`, `.it`) require a soundfont and can't be converted directly — you'll get a clear message, and the rest of the queue continues.

### Build from source
```powershell
git clone https://github.com/MarkHaker/EasyConvert.git
cd EasyConvert
pip install pydub audioop-lts imageio-ffmpeg tkinterdnd2 pyinstaller
# Place ffmpeg.exe and ffprobe.exe next to the script
pyinstaller --noconfirm --windowed --onefile --icon ico.ico --name ogg_to_mp3 `
  --collect-all tkinterdnd2 --collect-all imageio_ffmpeg --collect-all pydub `
  --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." ogg_to_mp3.py
```
The EXE appears in `dist\ogg_to_mp3.exe`.

### How it works
Built with **Python + Tkinter + pydub**, wrapped around a bundled **ffmpeg/ffprobe**. PyInstaller packs everything (including `ffmpeg.exe`/`ffprobe.exe`) into a single self-extracting EXE via `--onefile`.

### Tech stack
`Python 3.14` · `Tkinter` · `tkinterdnd2` · `pydub` · `imageio-ffmpeg` · `PyInstaller` · `ffmpeg`

---

## 🇷🇺 Русский

### Что это?
**EasyConvert** — крошечная самостоятельная программа для Windows, которая конвертирует **любое аудио в MP3**.
Перетащи аудио-файл в окно (или на сам `.exe`) — и он станет MP3, сохранённым в папку с сегодняшней датой рядом с программой. И всё.

### Возможности
- 🎯 **Любой формат аудио** — OGG, WAV, FLAC, AAC, M4A, WMA, MP3, AC3, OPUS, AIFF и ещё десятки (всё, что понимает `ffmpeg`).
- 🖱️ **Drag &amp; drop** — бросай файлы в окно *или* прямо на EXE.
- 🗂️ **Папки по дате** — результат сохраняется в папку `ГГГГ-ММ-ДД` (новая создаётся автоматически при смене даты).
- 🏷️ **То же имя** — `song.ogg` → `song.mp3` (при совпадении имён добавляется `_1`, `_2`...).
- 🎚️ **MP3 320 kbps**, 44.1 кГц, стерео.
- 📦 **Один самостоятельный EXE** — без зависимостей, без установки, работает на любом ПК с Windows. `ffmpeg`/`ffprobe` вшиты внутрь.
- 🌑 Аккуратный тёмный интерфейс с надписью: *«Брось сюда любое аудио в любом формате — а я его превращу в MP3»*.

### Скачать и пользоваться
1. Зайди в [Releases](https://github.com/MarkHaker/EasyConvert/releases/latest) и скачай **`ogg_to_mp3.exe`**.
2. Положи куда угодно (Рабочий стол, флешка — неважно).
3. Либо открой программу и перетащи аудио в окно, **либо** перетащи файлы прямо на `ogg_to_mp3.exe`.
4. MP3 появятся в папке `ГГГГ-ММ-ДД` рядом с программой.

> ⚠️ MIDI/трекерные форматы (`.mid`, `.mod`, `.s3m`, `.xm`, `.it`) требуют звукового шрифта и не конвертируются напрямую — получишь понятное сообщение, а остальные файлы в очереди продолжат обработку.

### Сборка из исходников
```powershell
git clone https://github.com/MarkHaker/EasyConvert.git
cd EasyConvert
pip install pydub audioop-lts imageio-ffmpeg tkinterdnd2 pyinstaller
# Положи ffmpeg.exe и ffprobe.exe рядом со скриптом
pyinstaller --noconfirm --windowed --onefile --icon ico.ico --name ogg_to_mp3 `
  --collect-all tkinterdnd2 --collect-all imageio_ffmpeg --collect-all pydub `
  --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." ogg_to_mp3.py
```
EXE появится в `dist\ogg_to_mp3.exe`.

### Как это работает
Сделано на **Python + Tkinter + pydub**, поверх вшитого **ffmpeg/ffprobe**. PyInstaller упаковывает всё (включая `ffmpeg.exe`/`ffprobe.exe`) в один самораспаковывающийся EXE через `--onefile`.

### Технологии
`Python 3.14` · `Tkinter` · `tkinterdnd2` · `pydub` · `imageio-ffmpeg` · `PyInstaller` · `ffmpeg`

---

## 📄 License / Лицензия

MIT License — see [LICENSE](LICENSE). Свободно используй, модифицируй и распространяй.

<p align="center"><sub>Made with ❤️ by <a href="https://github.com/MarkHaker">MarkHaker</a></sub></p>
