"""Py-dlp: a distribution of yt-dlp that adds the ``pydlp`` command.

This repository contains the complete, unmodified yt-dlp engine
(``yt_dlp/``) - all 1,750+ extractors, downloaders and options - plus a
small CLI layer (this ``pydlp`` package) that runs it under the
``pydlp`` name.  Py-dlp's version always equals the bundled engine's
version.
"""

try:
    # same version as the bundled engine (yt_dlp/version.py)
    from yt_dlp.version import __version__
except ImportError:  # engine not on sys.path (e.g. during metadata build)
    __version__ = "0.0.0"

__project_name__ = "Py-dlp"
__homepage__ = "https://github.com/Beasgohan-code/Py-dlp"


def engine_version():
    """Version of the bundled yt-dlp engine."""
    return __version__


def full_version():
    return "pydlp %s (yt-dlp distribution)" % __version__
