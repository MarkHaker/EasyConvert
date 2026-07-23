# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.4] — 2026-07-23

### Fixed
- **Critical:** the GUI never appeared — `app.exec()` was invoked before
  `MainWindow` was created and shown (a regression introduced in v1.1.3 when
  reorganizing `main()`). The windowed EXE therefore exited immediately with
  no window. Fixed the ordering: build the window, `show()`, then enter the
  event loop.
- Added a `crash.log` writer (custom `sys.excepthook` + try/except around GUI
  startup) so any future startup failure is recorded next to the EXE instead
  of dying silently.

## [1.1.3] — 2026-07-23

### Changed — Complete UI rewrite on PyQt6
- The GUI is now built with **PyQt6 + QSS** (standard tkinter is retired).
  Premium card-based neumorphism look: deep `#13131A` background, `#1C1C26`
  cards with rounded corners (20px) and subtle borders, `#252533` inputs.
- Strict palette per spec: neon-teal `#00F0FF` START, neon-red `#FF3366` STOP,
  white primary text, `#8A8A9D` secondary text.
- **Strict vector icons** drawn with `QPainter` (plus, folder, trash, refresh,
  play, stop, check, cross, note, open-folder). No emojis anywhere.
- **Header**: bold app title on the left; compact **RU/EN pill switch** (capsule
  with the active side highlighted) + icon-only update button on the right.
- **Two raised cards** side by side with 20px gap:
  - Left: **File queue** — dotted dropzone (`#252533`, dashed `#8A8A9D` border,
    rounded 12px) with hint text, plus a queue list with name/size/status/
    per-file progress (mini progress bar drawn in each row).
  - Right: **Converted MP3s** — clean list, double-click to open, thin dark
    custom scrollbars.
- **Bottom settings + action card**: three columns (AUDIO / CONTROL / PATHS)
  with dark rounded comboboxes, a folder-picker, and four **Toggle Switches**
  (no checkboxes) for keep-rate / keep-tags / normalize / recursive.
- Large **START** button (neon teal, black bold text, hover lightens) and
  outlined **STOP** button (`#252533` bg, `#FF3366` text + border).
- **Status bar** with a colored dot indicator (green idle, pulsing yellow while
  converting, red on error) + `#8A8A9D` status text + version label.
- Thin flat overall progress bar at the very bottom.
- Generous spacing everywhere (≥15–20px padding, ≥20px between blocks).

### Added
- Per-file mini progress bar rendered inside each queue row (custom item
  delegate).
- Pulsing status-dot animation while converting.

### Notes
- EXE size grew to ~225 MB because PyQt6 is bundled alongside ffmpeg/ffprobe.
- The app no longer uses `app.setStyle("Fusion")` — it crashed the event loop
  combined with the custom QSS on some Windows builds.

## [1.1.2] — 2026-07-22

### Changed — UI redesign
- Complete UI redesign: modern, minimalist, dark Material/macOS-inspired theme
  (deep blue-grey `#1e1e2e`, soft purple `#bb86fc`, teal `#03dac6` for Start,
  red `#cf6679` for Stop). Clean surfaces, thin separators, no "legacy Tk" look.
- **Header**: logo glyph + app title on the left; compact **RU/EN pill switch**
  and an icon-only "check for updates" button on the right (no more wide text buttons).
- **Two-panel workspace** with raised cards: left = **FILE QUEUE**
  (name, size, status, per-file progress), right = **CONVERTED MP3s**
  (name, folder, size). Per-row status colors (pending/processing/done/failed/skipped).
- Compact **icon action buttons** in each card header:
  `+ files`, `+ folder`, `clear` (trash), `open folder`.
- Large prominent **START (teal ▶) / STOP (red ■)** action bar in the middle.
- **Compact settings panel** (no heavy frame) with grouped sections:
  AUDIO (Bitrate, Channels), CONTROL (Workers), PATHS (Output folder, On clash)
  + a folder-picker icon. Clean modern checkboxes row.
- **Empty-state** prompt in the queue area when no files are loaded.
- **Thin flat overall progress bar** + **status bar** with a colored state icon
  (idle/processing/done/error) and version label on the right.
- Thin modern scrollbars; mouse-wheel scrolling in the queue.

### Added
- **Channels** setting (1 = mono / 2 = stereo) — new audio parameter.
- Per-file progress shown as a percentage in the queue row.
- `--channels` CLI flag.
- File size column in the input queue.

### Fixed
- Settings UI now reliably persists bitrate/channels/workers (references fixed).
- Language switch now re-labels settings group titles and all UI strings instantly.

## [1.1] — 2026-07-22

### Added
- **Two-panel UI**: top = input queue (filename, status, per-file progress);
  bottom = output list (name, folder, size). Double-click opens the produced MP3.
- **Drag & drop on the whole window** (not only the drop zone).
- **Folder drop** — dropping a folder queues all audio inside, with an optional
  recursive subfolder traversal toggle.
- **Bitrate selector** (320 / 256 / 192 / 128 / 96 kbps).
- **"Keep source sample-rate/channels"** option (otherwise 44.1 kHz / stereo).
- **Loudness normalization** (`loudnorm`) toggle.
- **Output folder modes**: by date (`YYYY-MM-DD`), next to source, or a custom folder.
- **Collision policy**: add `_1` suffix / overwrite / skip.
- **Metadata preservation** — `-map_metadata 0:s:0` carries artist/title/album/art
  from the source into the MP3 ID3 tags.
- **Video container support** — MP4/MKV/WebM/... audio streams are extracted (`-vn`).
- **Stop button** — cancels the running queue and terminates the ffmpeg process.
- **Real per-file progress** — parsed from ffmpeg's `time=` output.
- **i18n RU/EN** with an instant top-right switch; defaults to the system language.
- **settings.json** persistence for all options and window geometry.
- **convert.log** — a persistent log next to the program.
- **Update check** via the GitHub Releases API.
- **CLI flags**: `--bitrate`, `--outdir`, `--lang` (in addition to `--cli`).
- GitHub Actions workflow for automatic release builds on `v*` tags.

### Changed
- **Rewrote the conversion core** to call `ffmpeg` directly via `subprocess`
  instead of going through `pydub` at encode time. This gives real progress,
  reliable tag/cover preservation, video support, and removes the `audioop`
  dependency at runtime.
- Window icon now applied via `.iconbitmap()` (the bundled `ico.ico`).
- Status line now reports totals: "Done: X/Y — errors: Z, skipped: W".
- Adaptive (grid/pack-based) layout that resizes cleanly.
- Updated `README.md` with the new feature set and RU/EN toggle.

### Fixed
- pydub's `RuntimeWarning: Couldn't find ffmpeg/ffprobe` — ffmpeg/ffprobe are
  now resolved from the bundled `_MEIPASS` directory and added to `PATH`.
- Unicode crashes in CLI output under cp1251 consoles.
- Name collisions now respect the chosen policy instead of always suffixing.

## [1.0] — 2026-07-22

### Added
- First public release.
- Drag & drop any audio file into the window → MP3 (320 kbps, 44.1 kHz, stereo).
- Auto-dated output folders (`YYYY-MM-DD`) next to the program.
- Same filename as the source; auto-suffix (`_1`, `_2`, …) on collisions.
- Single standalone EXE with `ffmpeg`/`ffprobe` bundled inside (PyInstaller `--onefile`).
- Dark UI in Russian with the tagline
  *"Брось сюда любое аудио в любом формате — а я его превращу в MP3"*.
- Drop files directly onto the EXE (argv paths) or onto the open window.
- CLI mode (`--cli`) for headless conversion.
- MIT License, bilingual README (RU/EN) with a language toggle.
