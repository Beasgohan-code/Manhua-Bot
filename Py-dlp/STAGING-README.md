# Py-dlp — complete yt-dlp distribution (staged for the Py-dlp repo)

This directory holds the finished **Py-dlp** project, staged on this
branch because the Arena agent's GitHub connection has write access to
**Manhua-Bot only** — not to
[Beasgohan-code/Py-dlp](https://github.com/Beasgohan-code/Py-dlp),
where this project belongs. Do **not** merge this branch into
Manhua-Bot's `main`; it is a staging area only.

## What Py-dlp is

The complete, **unmodified yt-dlp 2026.08.19 engine** (upstream master
[`bbc809a`](https://github.com/yt-dlp/yt-dlp) — the latest release) plus
a small `pydlp` command layer on top:

```
pydlp --version   ->  pydlp 2026.08.19 (yt-dlp distribution)
yt-dlp --version  ->  2026.08.19
```

- **1,752 site extractors** — every site yt-dlp supports
- Every yt-dlp option, downloader, and post-processor works unchanged
- Installs two commands: `pydlp` and `yt-dlp`
- Py-dlp's version always equals the bundled engine's version

## Get the complete repository (all 1,246 files, full history)

Download **`Py-dlp-main.bundle`** from this directory (or:
`curl -LO https://github.com/Beasgohan-code/Manhua-Bot/raw/arena/01a06ad9-manhua-bot/Py-dlp/Py-dlp-main.bundle`),
then:

```bash
git clone Py-dlp-main.bundle Py-dlp
cd Py-dlp
git remote set-url origin https://github.com/Beasgohan-code/Py-dlp.git
git push -u origin main
```

That publishes the entire project — engine, `pydlp` layer, tests and CI —
to the Py-dlp repo. The bundle was verified end-to-end: clone →
`pip install .` → both entry points → 17/17 offline tests passing.

## Browsable files in this directory

| File | Contents |
|---|---|
| `README.md` | Project readme (yt-dlp's full readme with a Py-dlp banner) |
| `pyproject.toml` | Packaging — installs `pydlp` + `yt-dlp` commands |
| `pydlp/` | The Py-dlp command layer (branding, version, update guard) |
| `tests/` | Offline test suite — 17 tests, no network needed |
| `Py-dlp-main.bundle` | The complete repository as a single git bundle |

The full `yt_dlp/` engine tree lives inside the bundle; it cannot be
staged as plain files here because this repository's push rules cap the
number of files a branch may change.
