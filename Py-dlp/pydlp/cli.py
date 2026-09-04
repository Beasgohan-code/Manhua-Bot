"""The ``pydlp`` command line interface.

Py-dlp is a distribution of yt-dlp: the engine in ``yt_dlp/`` is
unmodified upstream code, and this module only

- brands the CLI as ``pydlp`` (program name, usage, --version, epilog)
- replaces the in-app self-updater with repo-appropriate instructions
  (the engine ships in-tree here, so ``-U`` cannot pip-update it)
- delegates everything else, unchanged, to yt-dlp

Every yt-dlp option works exactly as documented upstream:

    https://github.com/yt-dlp/yt-dlp#usage-and-options

The engine can also be used directly: this distribution installs the
``yt-dlp`` command too.
"""

from __future__ import annotations

import sys

from . import __homepage__, engine_version

UPDATE_FLAGS = ("-U", "--update", "--update-to")


def _brand_option_parser():
    """Brand the engine's option parser as pydlp.

    Done via monkey-patch so no upstream code is forked; if yt-dlp ever
    renames the class we degrade gracefully to default branding.
    """
    try:
        import yt_dlp.options as ytdlp_options

        original_init = ytdlp_options._YoutubeDLOptionParser.__init__

        def branded_init(self):
            original_init(self)
            self.prog = "pydlp"
            self.usage = "pydlp [OPTIONS] URL [URL...]"
            self.version = "pydlp %s (yt-dlp distribution)" % (
                engine_version())
            self.epilog = (
                "Py-dlp (yt-dlp distribution): %s\n"
                "Engine: yt-dlp (Unlicense) "
                "https://github.com/yt-dlp/yt-dlp" % __homepage__)

        ytdlp_options._YoutubeDLOptionParser.__init__ = branded_init
    except Exception:  # noqa: BLE001 - branding is best-effort
        pass


def _update_hint():
    return (
        "Py-dlp bundles the yt-dlp engine inside this repository, so it\n"
        "cannot pip-update itself. To update the engine:\n"
        "  1. git pull   (if you installed from this repo), or\n"
        "  2. replace the yt_dlp/ directory with a newer one from\n"
        "     https://github.com/yt-dlp/yt-dlp, then reinstall:\n"
        "     python -m pip install --force-reinstall .")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    else:
        argv = list(argv)

    # --version: print the branded banner (yt-dlp prints a bare version)
    if "--version" in argv:
        print("pydlp %s (yt-dlp distribution)" % engine_version())
        return 0

    # self-update does not apply to an in-tree (vendored) distribution
    for flag in UPDATE_FLAGS:
        if flag in argv or any(arg.startswith(flag + "=")
                               for arg in argv):
            print(_update_hint())
            return 0

    _brand_option_parser()

    import yt_dlp
    sys.argv[0] = "pydlp"
    # yt_dlp.main() raises SystemExit with the proper exit code
    return yt_dlp.main(argv)


if __name__ == "__main__":
    sys.exit(main())
