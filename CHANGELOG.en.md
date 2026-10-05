# Changelog

**English** · [Português](CHANGELOG.md)

Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). While the version is `0.x`, a minor
release (`0.Y.0`) may change `config.toml` keys; anything that does is listed under
**Changed** or **Removed**. The current version is also in `VERSION`, in
`app/ps5backup.py`.

## [Unreleased]

## [0.6.0] - 2026-10-05

### Added
- `ps5backup diag` and `memcard.exe diag`: read-only FTP diagnostics with version,
  privacy-preserving banner/reply summaries, MLSD, counts and a test RETR.
- `GET /api/diag`, protected by the same API login with Portuguese or English reports.
- Compatibility tables in both languages and an issue form for new reports.

## [0.5.0] - 2026-10-05

### Added
- `memcard.exe` for Windows: a double-click starts backups and opens the web interface in your browser.
- Workflow to build the executable with Python 3.13 and PyInstaller 6.22.3 on `v*` tags,
  with the interface bundled and SHA-256 attached to the release.
- Download, SmartScreen, SHA-256 checking and Windows startup instructions in both README files.

### Changed
- In the executable, `config.toml` and `data/` live next to it; with no arguments, it starts the daemon.
- The executable's interface listens on `127.0.0.1`; `WEB_BIND` allows changing the address.
  Docker and source runs still use `0.0.0.0` by default.
- The web port is reserved before starting the daemon. If it is already in use, a second
  run of the executable only opens the browser and exits with code 0.

## [0.4.2] - 2026-10-05

### Added
- Runs on Windows from source, with Python 3.13 and without Docker;
  instructions in both README files.
- Backup tests against a fake PS5 FTP server and a Windows/Linux test matrix.

### Fixed
- Locking between threads and processes on Windows, retaining `flock` on Linux.
- Config, JSON and log files are written and read as UTF-8, preserving names such as "João".
- Save names are read from SQLite with a valid Windows URI and the database is closed before cleanup.
- JSON writes retry on Windows when a reader prevents replacing the file.

## [0.4.1] - 2026-10-05

### Changed
- **Find now** uses the IP and subnet typed in Settings (even unsaved) and the scan also
  tries 192.168.1.0/24 and 192.168.0.0/24, so it works with an empty or wrong address.

### Fixed
- Changing the IP or port in Settings now marks the PS5 offline within one probe (~13 s)
  instead of waiting for 3 consecutive failures (~40 s); automatic discovery only runs
  after the status has updated.
- An empty `host` no longer connects to the local machine (it showed as "PS5 on at .").

## [0.4.0] - 2026-10-05

### Added
- Automatic PS5 discovery: when the console stops responding, the daemon scans the
  subnet (ports 2121, 1337 and 21), confirms with anonymous FTP on `/user/home` and
  writes `host` and `ftp_port` to `config.toml`. Retries every 5 minutes.
- **Find now** button in Settings, the `/api/discover` route and the `ps5backup discover` command.
- Keys `ps5.auto_discover` (default `true`) and `ps5.subnet` (empty = the /24 of `host`).
- Automatic updates: `compose.yml` ships Watchtower, which pulls the new `main` image
  every 15 minutes and recreates the container.
- `CHANGELOG.md` and an app version (`VERSION`, `ps5backup --version`, a log line on start).

## [0.3.0] - 2026-10-04

### Added
- Ready-made image on the GitHub Container Registry (`ghcr.io/bps2414/memcard`, amd64 and arm64),
  published on every push to `main`.
- GitHub Actions workflow that runs the tests.

### Changed
- The project is now called **Memcard**.

## [0.2.0] - 2026-10-04

### Added
- Weekly Discord summary (`notify.weekly_summary`): play time per game and profile, and disk space.
- Optional web UI password (`WEB_PASSWORD`), covering pages, API, artwork and downloads;
  five wrong passwords block the address for 5 minutes.
- Scheduled integrity check (`triggers.verify_interval_days`): recomputes the checksum of
  every stored version and only alerts if one does not match.
- Configurable "playing now" window (`notify.now_playing_minutes`).
- UI and alerts in English, with `README.en.md` and the `notify.language` key.
- Automated tests (`unittest`) for retention rules, cleanup, config validation, the
  projection and the UI.
- `ROADMAP.md`.

### Changed
- Discord: a new message when the PS5 turns on and a fresh summary when it turns off
  (editing does not notify); the session message shows what is being played now.
- Short network drops no longer raise an alert: the console only counts as off after
  `triggers.offline_grace_seconds`.
- Saves are scanned every 30 s, with a 10 s confirmation when a change is pending.

### Fixed
- `Msg`/`tr` broke on config errors that carry a `key` field.

## [0.1.0] - 2026-10-04

First release.

### Added
- Versioned, read-only backup of PS5 saves over ftpsrv (FTP), with a SHA-256 checksum per version.
- Triggers: save changed, PS5 turned on, schedule and manual.
- Retention that thins old versions instead of deleting by age, with a trash folder, pinned
  versions, a minimum gap per session and a space warning.
- Discord alerts per play session.
- Web UI: one card per profile, one block per game, per-save history, downloads,
  settings and a log grouped by session.
- Dashboard: console usage map, estimated play time, space per game and a 12-month
  projection simulated with the real retention rules.

[Unreleased]: https://github.com/bps2414/memcard/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/bps2414/memcard/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/bps2414/memcard/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/bps2414/memcard/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/bps2414/memcard/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/bps2414/memcard/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/bps2414/memcard/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/bps2414/memcard/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bps2414/memcard/releases/tag/v0.1.0
