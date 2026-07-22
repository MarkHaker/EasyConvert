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

### ✨ Features (v1.1.3)

#### Premium PyQt6 UI (card-based neumorphism)
- Built with **PyQt6 + QSS** (no standard tkinter). Deep `#13131A` background,
  `#1C1C26` raised cards with 20px rounded corners and subtle borders.
- Strict palette: neon-teal `#00F0FF` START, neon-red `#FF3366` STOP, white
  text, `#8A8A9D` secondary.
- **Strict vector icons** drawn with QPainter (plus, folder, trash, refresh,
  play, stop, check, note). **No emojis.**
- **Header**: bold title + compact **RU/EN pill switch** (capsule, active side
  highlighted) + icon-only update button.
- **Two raised cards** with 20px gap: left = **FILE QUEUE** with a dotted
  dropzone + per-file mini progress bars in rows; right = **CONVERTED MP3s**
  with thin dark custom scrollbars. Double-click to open.
- **Bottom settings + action card**: AUDIO / CONTROL / PATHS columns with dark
  rounded comboboxes, plus four **Toggle Switches** (no checkboxes).
- Large **START** button (neon teal) and outlined **STOP** button.
- **Status bar** with a colored dot (green idle, pulsing yellow while working,
  red on error) + thin overall progress bar.
- Generous spacing everywhere (≥15–20px padding, ≥20px between blocks).

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
  --collect-all PyQt6 --collect-all imageio_ffmpeg --collect-all pydub `
  --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." ogg_to_mp3.py
```
The EXE appears in `dist\ogg_to_mp3.exe`.

### 🧱 How it works
Built with **Python + PyQt6 (QSS)**, driving a bundled **ffmpeg/ffprobe** directly via `subprocess` (no pydub at encode time). PyInstaller packs everything (PyQt6, `ffmpeg.exe`/`ffprobe.exe`) into a single self-extracting EXE via `--onefile`.

### 🧩 Tech stack
`Python 3.14` · `PyQt6 + QSS` · `ffmpeg/ffprobe` · `PyInstaller`

---

## 🇷🇺 Русский

### Что это?
**EasyConvert** — крошечная самостоятельная программа для Windows, которая конвертирует **любое аудио в MP3**.
Перетащи аудио-файл в окно (или на сам `.exe`) — и он станет MP3. И всё.

### ✨ Возможности (v1.1.3)

#### Премиальный UI на PyQt6 (карточки + неоморфизм)
- Сделано на **PyQt6 + QSS** (стандартный tkinter больше не используется). Глубокий
  фон `#13131A`, карточки `#1C1C26` со скруглением 20px и тонкой рамкой.
- Строгая палитра: неоново-бирюзовый `#00F0FF` для СТАРТ, неоново-красный
  `#FF3366` для СТОП, белый текст, `#8A8A9D` второстепенный.
- **Строгие векторные иконки** через QPainter (плюс, папка, корзина, обновление,
  play, stop, галочка, нота). **Без эмодзи.**
- **Шапка**: жирный заголовок + компактный **RU/EN-pill-переключатель** (капсула,
  активная сторона подсвечена) + кнопка-иконка обновления.
- **Две карточки** с отступом 20px: слева **ОЧЕРЕДЬ ФАЙЛОВ** с пунктирной dropzone
  и мини-полосами прогресса в строках; справа **ГОТОВЫЕ MP3** с тонкими тёмными
  скроллбарами. Двойной клик открывает файл.
- **Нижняя карточка настроек и действий**: колонки АУДИО / УПРАВЛЕНИЕ / ПУТИ с
  тёмными скруглёнными выпадающими списками + четыре **Toggle-переключателя**
  (без чекбоксов).
- Крупная кнопка **СТАРТ** (бирюзовая) и кнопка **СТОП** с контуром.
- **Статус-бар** с цветным кружком (зелёный — готово, пульсирующий жёлтый —
  конвертация, красный — ошибка) + тонкая полоса общего прогресса внизу.
- Везде большие отступы (≥15–20px padding, ≥20px между блоками).

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
  --collect-all PyQt6 --collect-all imageio_ffmpeg --collect-all pydub `
  --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." ogg_to_mp3.py
```
EXE появится в `dist\ogg_to_mp3.exe`.

### 🧱 Как это работает
Сделано на **Python + PyQt6 (QSS)**, поверх вшитого **ffmpeg/ffprobe**, вызываемого напрямую через `subprocess` (без pydub при кодировании). PyInstaller упаковывает всё (PyQt6, `ffmpeg.exe`/`ffprobe.exe`) в один самораспаковывающийся EXE через `--onefile`.

### 🧩 Технологии
`Python 3.14` · `PyQt6 + QSS` · `ffmpeg/ffprobe` · `PyInstaller`

---

## 📄 Changelog / История изменений
See / см. [CHANGELOG.md](CHANGELOG.md).

## 📄 License / Лицензия
MIT License — see [LICENSE](LICENSE). Свободно используй, модифицируй и распространяй.

<p align="center"><sub>Made with ❤️ by <a href="https://github.com/MarkHaker">MarkHaker</a></sub></p>
