"""Tests for Py-dlp: the branded CLI over the vendored yt-dlp engine.

Runs fully offline against a local HTTP fixture site (tests/localsite.py).
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))

from pydlp import engine_version, full_version  # noqa: E402
from pydlp.cli import main as pydlp_main  # noqa: E402
from localsite import LocalSite, make_ts_segment  # noqa: E402


def run_cli(argv):
    """Run pydlp in-process; returns (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            result = pydlp_main(argv)
            code = result if isinstance(result, int) else 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (
            0 if exc.code is None else 1)
    return code, out.getvalue(), err.getvalue()


class WithSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = LocalSite()
        cls.site.__enter__()
        cls.base = cls.site.url

    @classmethod
    def tearDownClass(cls):
        cls.site.__exit__(None, None, None)

    def download(self, *args, template="%(title)s [%(id)s].%(ext)s"):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, template)
            code, stdout, stderr = run_cli(["--no-warnings", "-q", "-o",
                                            out] + list(args))
            contents = {}
            for root, _dirs, names in os.walk(tmp):
                for name in names:
                    with open(os.path.join(root, name), "rb") as handle:
                        contents[name] = handle.read()
            return code, contents, stdout, stderr


class TestBranding(unittest.TestCase):
    def test_version_banner(self):
        code, stdout, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("pydlp", stdout)
        self.assertIn("yt-dlp", stdout)
        self.assertIn(engine_version(), stdout)
        # the version always tracks the bundled engine
        import yt_dlp
        self.assertEqual(engine_version(), yt_dlp.version.__version__)

    def test_full_version_helper(self):
        self.assertIn("yt-dlp", full_version())

    def test_help_is_branded(self):
        code, stdout, _ = run_cli(["-h"])
        self.assertEqual(code, 0)
        self.assertIn("Usage: pydlp", stdout)
        self.assertIn("Py-dlp", stdout)

    def test_update_flag_gives_hint(self):
        for flag in ("-U", "--update"):
            code, stdout, _ = run_cli([flag])
            self.assertEqual(code, 0, flag)
            self.assertIn("replace the yt_dlp/", stdout)

    def test_engine_importable(self):
        import yt_dlp
        self.assertRegex(yt_dlp.version.__version__, r"\d{4}\.\d{2}\.\d{2}")

    def test_engine_has_extractors(self):
        from yt_dlp.extractor import list_extractors
        extractors = list_extractors()
        names = {e.IE_NAME.lower() for e in extractors}
        self.assertGreater(len(extractors), 1000)
        self.assertIn("youtube", names)
        self.assertIn("generic", names)


class TestDownloads(WithSite):
    def test_direct_file(self):
        code, files, _out, _err = self.download(
            self.base + "/files/video.mp4")
        self.assertEqual(code, 0, files)
        video = [n for n in files if n.endswith(".mp4")]
        self.assertEqual(len(video), 1)
        self.assertEqual(files[video[0]], make_ts_segment(7, 256 * 1024))

    def test_generic_html5_page(self):
        code, files, _out, _err = self.download(
            self.base + "/page/html5.html")
        self.assertEqual(code, 0, files)
        video = [n for n in files if n.endswith((".mp4", ".webm"))]
        self.assertEqual(len(video), 1, files)

    def test_generic_og_page(self):
        code, files, _out, _err = self.download(
            self.base + "/page/og.html")
        self.assertEqual(code, 0, files)
        self.assertEqual(len(files), 1, files)

    def test_hls_master(self):
        code, files, _out, err = self.download(
            self.base + "/hls/master.m3u8")
        self.assertEqual(code, 0, (list(files), err))
        video = [n for n in files if not n.endswith(".txt")]
        self.assertEqual(len(video), 1, files)

    def test_hls_aes128(self):
        code, files, _out, err = self.download(
            self.base + "/hls-aes/seg720/playlist.m3u8")
        self.assertEqual(code, 0, (list(files), err))
        video = [n for n in files if n.endswith((".mp4", ".ts"))]
        self.assertEqual(len(video), 1, files)
        # decrypted output must equal the plaintext segments
        self.assertEqual(files[video[0]],
                         make_ts_segment(101, 48 * 1024) * 6)

    def test_dash_manifest(self):
        code, files, _out, err = self.download(
            self.base + "/dash/manifest.mpd", "-f", "v720")
        self.assertEqual(code, 0, (list(files), err))
        self.assertGreaterEqual(len(files), 1, files)

    def test_dump_json(self):
        code, stdout, _err = run_cli(
            ["-q", "--skip-download", "--dump-json",
             self.base + "/page/og.html"])
        self.assertEqual(code, 0)
        self.assertIn("OG Video Title", stdout)

    def test_get_title(self):
        code, stdout, _err = run_cli(
            ["-q", "--skip-download", "--print", "title",
             self.base + "/page/html5.html"])
        self.assertEqual(code, 0)
        self.assertIn("HTML5 Demo Video", stdout)

    def test_list_formats(self):
        code, stdout, _err = run_cli(
            ["-q", "--skip-download", "-F", self.base + "/page/og.html"])
        self.assertEqual(code, 0)
        self.assertIn("ID", stdout)

    def test_list_extractors_flag(self):
        code, stdout, _err = run_cli(["--list-extractors"])
        self.assertEqual(code, 0)
        self.assertGreater(stdout.count("\n"), 1000)

    def test_extractor_descriptions_flag(self):
        code, stdout, _err = run_cli(["--extractor-descriptions"])
        self.assertEqual(code, 0)
        self.assertGreater(stdout.count("\n"), 1000)


if __name__ == "__main__":
    unittest.main()
