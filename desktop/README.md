# Artemis desktop (Wails v3 + green portable)

All desktop-client code lives here. This is **not** `src/artemis/infra/desktop`
(remote desktop streaming).

| Path | Role |
|------|------|
| [`portable/`](portable/) | Green zip packaging (was `scripts/green/`) |
| [`src/`](src/) | Wails v3 shell: load bundled zip, spawn Artemis, tray/settings |
| [`package-release.sh`](package-release.sh) | Native end-to-end portable + Wails release build |

## Data directory

Same as the Artemis CLI/server default:

- `ARTEMIS_HOME` → `~/.artemis` (or the existing `ARTEMIS_HOME` env)
- Green runtime extract → `~/.artemis/portable/`
- Shell prefs → `~/.artemis/desktop-settings.json`

## Build green zip

From repo root:

```bash
make -f desktop/portable/Makefile green
```

## Build the complete desktop package locally

Run the end-to-end script on the matching native host. It builds the Dashboard,
creates and verifies the portable runtime, embeds it into Wails, and produces
the final native package:

```bash
desktop/package-release.sh
# Reuse an existing desktop/portable/release/Artemis-portable-<plat>-<version>.zip:
desktop/package-release.sh darwin-arm64 --reuse-portable
```

Wails requires native packaging. Windows packaging also needs [NSIS](https://nsis.sourceforge.io/)
(`makensis`) so the `.exe` is an installer rather than a portable single-file binary.

## Build the Wails shell

Run these from **`desktop/src`** (that directory contains `Taskfile.yml` and
`build/config.yml`). Requires **Go 1.25+**, [Wails v3](https://v3.wails.io/)
`v3.0.0-beta.13`.

```bash
go install github.com/wailsapp/wails/v3/cmd/wails3@v3.0.0-beta.13
cd desktop/src
go mod tidy
wails3 build            # development binary under desktop/src/bin/
wails3 task package ARCH=arm64 VERSION=<version> \
  PORTABLE_ZIP=../portable/release/Artemis-portable-darwin-arm64-<version>.zip
```

Dev against an already-running Artemis (skips the bundled green zip):

```bash
cd desktop/src
ARTEMIS_DESKTOP_URL=http://127.0.0.1:8088 wails3 dev
```

Without `ARTEMIS_DESKTOP_URL`, first launch uses `~/.artemis/portable/` if valid,
otherwise extracts the matching zip shipped with the desktop package (embedded
in the Windows and Linux binaries, under `Contents/Resources` on macOS). The
Wails shell never downloads Artemis. For local runtime debugging, set
`ARTEMIS_DESKTOP_PORTABLE_ZIP=/absolute/path/Artemis-portable-<plat>-<version>.zip`.
On later launches, a newer bundled portable version replaces the extracted
runtime after creating a consistent SQLite backup under `~/.artemis/backups/`.
The upgraded Artemis process then applies the normal database migrations during
startup. Newer extracted runtimes are never downgraded; PostgreSQL remains
externally managed and is not copied by the desktop shell.

The generated packages are intended for local testing and deployment. The Linux
package contains only the GUI binary; it has no separate portable zip or server
terminal process.

Linux also needs GTK4 + WebKitGTK 6 to link. macOS 12+.

## Icons

| File | Used for | Rule |
|------|----------|------|
| `src/build/appicon.png` | Windows `.ico`, Linux | Full-bleed 512x512 artwork |
| `src/build/appicon-macos.png` | macOS `.icns` | 1024x1024 canvas, artwork 824x824 centred |
| `src/assets/tray-icon.png` | Tray + app icon on Windows/Linux | Full-bleed |
| `src/assets/tray-icon-template.png` | macOS menu bar | 88px canvas, 64px black-on-transparent glyph |

macOS sizes both surfaces to a fixed box, so the padding has to live in the
artwork: the Dock follows Apple's 824/1024 icon grid, and Wails scales the menu
bar image to the full `NSStatusBar` thickness (22pt) where the glyph should be
~16pt. Full-bleed sources on either surface render a size bigger than every
other app. On macOS the Dock icon comes from the bundle's `icons.icns` only —
see `applyAppIcon` in `src/icons_darwin.go`.
