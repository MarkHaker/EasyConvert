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
Drag an audio file into the window (or drop it onto the `.exe`) — and it becomes an MP3. That's it.

### ✨ Features (v1.1.2)

#### Modern minimalist UI
- **Two-panel workspace** with raised cards: left = **FILE QUEUE**
  (name, size, status, per-file progress, color-coded states), right =
  **CONVERTED MP3s** (name, folder, size). Double-click a row to open the file.
- **Header** with logo + title, a compact **RU/EN pill switch**, and an
  icon-only "check for updates" button.
- Compact **icon action buttons** per card: `+ files`, `+ folder`, `clear`, `open folder`.
- Large prominent **START (teal ▶) / STOP (red ■)** action bar.
- **Compact settings panel** grouped into AUDIO / CONTROL / PATHS, clean checkboxes row.
- **Thin overall progress bar** + **status bar** with a colored state icon
  (idle / processing / done / error) and a version label.
- Dark Material/macOS-inspired theme; thin modern scrollbars; empty-state prompt.

#### Conversion
- 🎯 **Any format** — OGG, WAV, FLAC, AAC, M4A, WMA, MP3, AC3, OPUS, AIFF, and dozens more (everything `ffmpeg` understands). Video containers (MP4/MKV/WebM/...) are handled too — only the audio stream is extracted.
- 🏷️ **Tags &amp; metadata preserved** — artist, title, album, album art are carried over to the MP3 (`-map_metadata 0:s:0`).
- 🎚️ **Bitrate selector** — 320 / 256 / 192 / 128 / 96 kbps.
- 🎚️ **Channels** — mono / stereo selector (new in v1.1.2).
- 🔊 **Optional loudness normalization** (`loudnorm`).
- ⚡ **Keep source sample-rate** option (or force 44.1 kHz).
- ⏱️ **Real per-file progress** — the bar tracks actual encoding time via ffmpeg's `time=` output, not just file count.
- 🛑 **Stop button** — cancels the running queue instantly (terminates the ffmpeg process).

#### Output
- 🗂️ **Output folder modes:** by date (`YYYY-MM-DD`) · next to source · custom folder.
- 🏷️ **Same filename** — `song.ogg` → `song.mp3`.
- 🔁 **Collision policy:** add `_1` / overwrite / skip.
- 📅 **Auto-dated folders** — a new folder is created automatically when the date changes.

#### Convenience
- 🌐 **Two languages** — RU / EN switch in the top-right corner (instant, no restart). Default = system language.
- 🧰 **Folder drop** — drop a folder, all audio inside is queued (recursive toggle).
- 💾 **Settings &amp; window geometry saved** to `settings.json` next to the program.
- 📝 **`convert.log`** — a persistent log next to the program for troubleshooting.
- 🔄 **Update check** — "Check for updates" queries the GitHub Releases API and opens the new version page.
- 📦 **Single standalone EXE** — no dependencies, no installation, works on any Windows PC. `ffmpeg`/`ffprobe` are bundled inside.

### 📥 Download &amp; use
1. Go to [Releases](https://github.com/MarkHaker/EasyConvert/releases/latest) and download **`ogg_to_mp3.exe`**.
2. Put it anywhere (Desktop, USB stick — doesn't matter).
3. Either open it and drag audio into the window, **or** drag audio files straight onto `ogg_to_mp3.exe`.
4. MP3s appear in a `YYYY-MM-DD` folder next to the program (or wherever you chose in settings).

> ⚠️ MIDI/tracker formats (`.mid`, `.mod`, `.s3m`, `.xm`, `.it`) require a soundfont and can't be converted directly — you'll get a clear message, and the rest of the queue continues.

### 🖥️ CLI mode
```bat
ogg_to_mp3.exe --cli file1.ogg file2.wav --bitrate 192k --outdir "D:\out" --lang en
```

### 🔨 Build from source
```powershell
git clone https://github.com/MarkHaker/EasyConvert.git
cd EasyConvert
pip install -r requirements.txt
# Place ffmpeg.exe and ffprobe.exe next to the script (see build.ps1 for download links)
.\build.ps1            # or the PyInstaller command below
pyinstaller --noconfirm --windowed --onefile --icon ico.ico --name ogg_to_mp3 `
  --collect-all tkinterdnd2 --collect-all imageio_ffmpeg --collect-all pydub `
  --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." ogg_to_mp3.py
```
The EXE appears in `dist\ogg_to_mp3.exe`.

### 🧱 How it works
Built with **Python + Tkinter + tkinterdnd2**, driving a bundled **ffmpeg/ffprobe** directly via `subprocess` (no pydub at encode time). PyInstaller packs everything (including `ffmpeg.exe`/`ffprobe.exe`) into a single self-extracting EXE via `--onefile`.

### 🧩 Tech stack
`Python 3.14` · `Tkinter` · `tkinterdnd2` · `ffmpeg/ffprobe` · `PyInstaller`

---

## 🇷🇺 Русский

### Что это?
**EasyConvert** — крошечная самостоятельная программа для Windows, которая конвертирует **любое аудио в MP3**.
Перетащи аудио-файл в окно (или на сам `.exe`) — и он станет MP3. И всё.

### ✨ Возможности (v1.1.2)

#### Современный минималистичный UI
- **Двухпанельное рабочее пространство** с карточками: слева **ОЧЕРЕДЬ ФАЙЛОВ**
  (имя, размер, статус, прогресс по файлу, цветовые состояния), справа
  **ГОТОВЫЕ MP3** (имя, папка, размер). Двойной клик открывает файл.
- **Шапка** с логотипом и названием, компактный **RU/EN-переключатель** и
  кнопка-иконка «проверить обновления».
- Компактные **кнопки-иконки** в каждой карточке: `+ файлы`, `+ папка`, `очистить`, `открыть папку`.
- Крупная заметная панель **СТАРТ (бирюзовый ▶) / СТОП (красный ■)**.
- **Компактная панель настроек**, сгруппированная в АУДИО / УПРАВЛЕНИЕ / ПУТИ, чистая строка чекбоксов.
- **Тонкая полоса общего прогресса** + **статус-бар** с цветной иконкой состояния
  (ожидание / конвертация / готово / ошибка) и версией справа.
- Тёмная тема в стиле Material/macOS; тонкие современные скроллбары; подсказка при пустой очереди.

#### Конвертация
- 🎯 **Любой формат** — OGG, WAV, FLAC, AAC, M4A, WMA, MP3, AC3, OPUS, AIFF и ещё десятки (всё, что понимает `ffmpeg`). Видеоконтейнеры (MP4/MKV/WebM/...) тоже поддерживаются — извлекается только аудиодорожка.
- 🏷️ **Сохранение тегов и метаданных** — исполнитель, название, альбом, обложка переносятся в MP3 (`-map_metadata 0:s:0`).
- 🎚️ **Выбор битрейта** — 320 / 256 / 192 / 128 / 96 kbps.
- 🎚️ **Каналы** — выбор моно / стерео (новое в v1.1.2).
- 🔊 **Нормализация громкости** (`loudnorm`) — опционально.
- ⚡ **Сохранять частоту исходника** — опция (иначе 44.1 кГц).
- ⏱️ **Честный прогресс по файлу** — полоса отслеживает реальное время кодирования через `time=` от ffmpeg.
- 🛑 **Кнопка «Стоп»** — мгновенно отменяет очередь (терминирует процесс ffmpeg).

#### Вывод
- 🗂️ **Папки вывода:** по дате (`ГГГГ-ММ-ДД`) · рядом с исходником · своя папка.
- 🏷️ **То же имя** — `song.ogg` → `song.mp3`.
- 🔁 **При совпадении имён:** добавить `_1` / перезаписать / пропустить.
- 📅 **Папки по дате** — новая создаётся автоматически при смене даты.

#### Удобство
- 🌐 **Два языка** — переключатель RU/EN в правом верхнем углу (мгновенно, без перезапуска). По умолчанию — язык системы.
- 🧰 **Бросание папки** — брось папку, всё аудио внутри попадёт в очередь (опция рекурсивно по подпапкам).
- 💾 **Настройки и размер окна сохраняются** в `settings.json` рядом с программой.
- 📝 **`convert.log`** — постоянный лог рядом с программой для разбора проблем.
- 🔄 **Проверка обновлений** — «Проверить обновления» обращается к GitHub Releases API и открывает страницу новой версии.
- 📦 **Один самостоятельный EXE** — без зависимостей, без установки, работает на любом ПК с Windows. `ffmpeg`/`ffprobe` вшиты внутрь.

### 📥 Скачать и пользоваться
1. Зайди в [Releases](https://github.com/MarkHaker/EasyConvert/releases/latest) и скачай **`ogg_to_mp3.exe`**.
2. Положи куда угодно (Рабочий стол, флешка — неважно).
3. Либо открой программу и перетащи аудио в окно, **либо** перетащи файлы прямо на `ogg_to_mp3.exe`.
4. MP3 появятся в папке `ГГГГ-ММ-ДД` рядом с программой (или там, где выбрано в настройках).

> ⚠️ MIDI/трекерные форматы (`.mid`, `.mod`, `.s3m`, `.xm`, `.it`) требуют звукового шрифта и не конвертируются напрямую — получишь понятное сообщение, а остальные файлы в очереди продолжат обработку.

### 🖥️ Режим CLI
```bat
ogg_to_mp3.exe --cli file1.ogg file2.wav --bitrate 192k --outdir "D:\out" --lang ru
```

### 🔨 Сборка из исходников
```powershell
git clone https://github.com/MarkHaker/EasyConvert.git
cd EasyConvert
pip install -r requirements.txt
# Положи ffmpeg.exe и ffprobe.exe рядом со скриптом (ссылки в build.ps1)
.\build.ps1            # или команда PyInstaller ниже
pyinstaller --noconfirm --windowed --onefile --icon ico.ico --name ogg_to_mp3 `
  --collect-all tkinterdnd2 --collect-all imageio_ffmpeg --collect-all pydub `
  --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." ogg_to_mp3.py
```
EXE появится в `dist\ogg_to_mp3.exe`.

### 🧱 Как это работает
Сделано на **Python + Tkinter + tkinterdnd2**, поверх вшитого **ffmpeg/ffprobe**, вызываемого напрямую через `subprocess` (без pydub при кодировании). PyInstaller упаковывает всё (включая `ffmpeg.exe`/`ffprobe.exe`) в один самораспаковывающийся EXE через `--onefile`.

### 🧩 Технологии
`Python 3.14` · `Tkinter` · `tkinterdnd2` · `ffmpeg/ffprobe` · `PyInstaller`

---

## 📄 Changelog / История изменений
See / см. [CHANGELOG.md](CHANGELOG.md).

## 📄 License / Лицензия
MIT License — see [LICENSE](LICENSE). Свободно используй, модифицируй и распространяй.

<p align="center"><sub>Made with ❤️ by <a href="https://github.com/MarkHaker">MarkHaker</a></sub></p>
