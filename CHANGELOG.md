# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
