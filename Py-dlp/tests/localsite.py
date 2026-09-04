"""A tiny local site used by the offline test-suite.

Serves: a range-enabled mp4, HTML fixture pages, HLS (plain + AES-128)
and DASH manifests with generated segments.
"""

import http.server
import os
import re
import struct
import threading

# AES for the encrypted-HLS fixture comes from the bundled engine itself
from yt_dlp.aes import aes_cbc_encrypt_bytes as aes_cbc_encrypt

KEY = b"\x01" * 16  # AES key used by /hls-aes/


def make_ts_segment(seed, size=40 * 1024):
    """Pseudo-random but deterministic MPEG-TS-looking payload."""
    state = seed or 1
    out = bytearray(b"\x47" + struct.pack(">H", seed & 0xFFFF) +
                    b"\x00\x00")
    while len(out) < size:
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        out.append(state & 0xFF)
        out.append((state >> 8) & 0xFF)
    return bytes(out)


class SiteFixture:
    """Builds all fixture content in memory."""

    def __init__(self):
        self.files = {}
        self._build()

    # ------------------------------------------------------------- builders
    def _build(self):
        files = self.files

        files["/files/video.mp4"] = make_ts_segment(7, 256 * 1024)
        files["/files/audio.mp3"] = make_ts_segment(8, 64 * 1024)
        files["/files/big.bin"] = make_ts_segment(9, 512 * 1024)

        # ------------------------------------------------------ html pages
        files["/page/html5.html"] = (
            "<html><head><title>HTML5 Demo Video</title></head><body>"
            "<video controls poster=\"/thumb.jpg\" width=\"640\" "
            "height=\"360\">"
            "<source src=\"/files/video.mp4\" type=\"video/mp4\">"
            "<source src=\"/files/video.webm\" type=\"video/webm\">"
            "</video></body></html>").encode()

        files["/page/og.html"] = (
            "<html><head><title>OG Demo Video</title>"
            "<meta property=\"og:title\" content=\"OG Video Title\">"
            "<meta property=\"og:video\" content=\"/files/video.mp4\">"
            "<meta property=\"og:video:width\" content=\"1280\">"
            "<meta property=\"og:video:height\" content=\"720\">"
            "<meta property=\"og:image\" content=\"/thumb.jpg\">"
            "</head><body>hello</body></html>").encode()

        files["/page/jsonld.html"] = (
            "<html><head><title>JSON-LD page</title>"
            "<script type=\"application/ld+json\">"
            "{\"@type\":\"VideoObject\",\"name\":\"JSONLD Video\","
            "\"duration\":\"PT42S\","
            "\"contentUrl\":\"/files/video.mp4\","
            "\"thumbnailUrl\":\"/thumb.jpg\"}"
            "</script></head><body></body></html>").encode()

        files["/page/iframe.html"] = (
            "<html><head><title>Frame host</title></head><body>"
            "<iframe src=\"/page/html5.html\"></iframe>"
            "</body></html>").encode()

        files["/page/scan.html"] = (
            "<html><head><title>Scan Demo</title></head><body>"
            "<script>var player = {\"u\":\"https:\\/\\/cdn.example.org"
            "\\/media\\/clip.mp4?token=abc\"};</script>"
            "</body></html>").encode()

        files["/page/empty.html"] = (
            "<html><head><title>Nothing here</title></head><body>"
            "<p>text only</p></body></html>").encode()

        # redirect chain
        files["/redirect/1"] = ("redirect", "/redirect/2")
        files["/redirect/2"] = ("redirect", "/files/video.mp4")

        # ------------------------------------------------------------- hls
        self._build_hls(prefix="/hls", encrypted=False)
        self._build_hls(prefix="/hls-aes", encrypted=True)

        # ------------------------------------------------------------ dash
        self._build_dash()

    def _build_hls(self, prefix, encrypted):
        files = self.files
        seg_count = 6
        # build segments per variant
        variants = {"720": make_ts_segment(101, 48 * 1024),
                    "480": make_ts_segment(102, 32 * 1024)}
        audio_seed = make_ts_segment(103, 16 * 1024)
        for name, payload in variants.items():
            for index in range(seg_count):
                files["%s/seg%s/%d.ts" % (prefix, name, index)] = payload
        for index in range(seg_count):
            files["%s/audio/%d.aac" % (prefix, index)] = audio_seed

        master = ["#EXTM3U"]
        master.append("#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID=\"aud\","
                      'NAME="english",DEFAULT=YES,URI="%s/audio/'
                      'playlist.m3u8"' % prefix)
        for name, height in (("720", 720), ("480", 480)):
            master.append("#EXT-X-STREAM-INF:BANDWIDTH=%d,RESOLUTION=%dx%d"
                          % (height * 2000, height * 16 // 9, height))
            master.append("%s/seg%s/playlist.m3u8" % (prefix, name))
        files["%s/master.m3u8" % prefix] = \
            ("\n".join(master) + "\n").encode()

        def media_playlist(prefix, seg_dir, ext, count):
            lines = ["#EXTM3U", "#EXT-X-VERSION:3",
                     "#EXT-X-TARGETDURATION:4", "#EXT-X-MEDIA-SEQUENCE:0"]
            if encrypted:
                lines.append('#EXT-X-KEY:METHOD=AES-128,URI="%s/key.bin"'
                             % prefix)
            for index in range(count):
                lines.append("#EXTINF:4.000,")
                lines.append("%s/%d.%s" % (seg_dir, index, ext))
            lines.append("#EXT-X-ENDLIST")
            return ("\n".join(lines) + "\n").encode()

        for name in variants:
            files["%s/seg%s/playlist.m3u8" % (prefix, name)] = \
                media_playlist(prefix, "%s/seg%s" % (prefix, name), "ts",
                               seg_count)
        files["%s/audio/playlist.m3u8" % prefix] = media_playlist(
            prefix, "%s/audio" % prefix, "aac", seg_count)

        if encrypted:
            # re-encrypt: each segment independently encrypted with
            # IV = segment index (big-endian 16 bytes)
            for name, payload in variants.items():
                for index in range(seg_count):
                    iv = struct.pack(">QQ", 0, index)
                    files["%s/seg%s/%d.ts" % (prefix, name, index)] = \
                        aes_cbc_encrypt(payload, KEY, iv)
            for index in range(seg_count):
                iv = struct.pack(">QQ", 0, index)
                files["%s/audio/%d.aac" % (prefix, index)] = \
                    aes_cbc_encrypt(audio_seed, KEY, iv)
            files["%s/key.bin" % prefix] = KEY


    def _build_dash(self):
        files = self.files
        seg_count = 5
        video = make_ts_segment(201, 32 * 1024)
        audio = make_ts_segment(202, 12 * 1024)
        files["/dash/video/init.mp4"] = b"INITVIDEO" + b"\x00" * 32
        files["/dash/audio/init.mp4"] = b"INITAUDIO" + b"\x00" * 16
        for index in range(seg_count):
            files["/dash/video/seg-%d.m4s" % index] = video
            files["/dash/audio/seg-%d.m4s" % index] = audio
        manifest = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" '
            'mediaPresentationDuration="PT20S" profiles="urn:mpeg:dash:'
            'profile:isoff-on-demand:2011">'
            '<Period duration="PT20S">'
            '<AdaptationSet mimeType="video/mp4" codecs="avc1.64001e">'
            '<SegmentTemplate media="/dash/video/seg-$Number$.m4s" '
            'initialization="/dash/video/init.mp4" '
            'duration="4" timescale="1" startNumber="0"/>'
            '<Representation id="v720" bandwidth="2000000" width="1280" '
            'height="720"/>'
            '<Representation id="v360" bandwidth="800000" width="640" '
            'height="360"/>'
            '</AdaptationSet>'
            '<AdaptationSet mimeType="audio/mp4" codecs="mp4a.40.2">'
            '<SegmentTemplate media="/dash/audio/seg-$Number$.m4s" '
            'initialization="/dash/audio/init.mp4" '
            'duration="4" timescale="1" startNumber="0"/>'
            '<Representation id="a128" bandwidth="128000"/>'
            '</AdaptationSet>'
            '</Period></MPD>')
        files["/dash/manifest.mpd"] = manifest.encode()

        files["/page/dash.html"] = (
            "<html><head><title>DASH demo</title>"
            "<meta property=\"og:video\" content=\"/dash/manifest.mpd\">"
            "</head><body></body></html>").encode()


class Handler(http.server.BaseHTTPRequestHandler):
    fixture = None  # type: SiteFixture
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # silence
        pass

    def do_HEAD(self):
        self._serve(head=True)

    def do_GET(self):
        self._serve(head=False)

    def _resolve(self):
        path = self.path.split("?")[0]
        seen = set()
        while True:
            if path in seen:
                return None, None, 404
            seen.add(path)
            item = self.fixture.files.get(path)
            if isinstance(item, tuple) and item and item[0] == "redirect":
                return None, item[1], 302
            if item is None:
                return None, None, 404
            return path, item, 200

    def _serve(self, head):
        path, item, status = self._resolve()
        if status == 302:
            self.send_response(302)
            self.send_header("Location", item)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if status == 404:
            body = b"not found"
            self.send_response(404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)
            return
        data = item
        total = len(data)
        rng = self.headers.get("Range")
        start, end = 0, total - 1
        partial = False
        if rng:
            match = re.match(r"bytes=(\d*)-(\d*)", rng)
            if match and (match.group(1) or match.group(2)):
                start = int(match.group(1) or 0)
                if match.group(2):
                    end = int(match.group(2))
                else:
                    end = total - 1
                if start >= total:
                    self.send_response(416)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                end = min(end, total - 1)
                partial = True
        chunk = data[start:end + 1]
        self.send_response(206 if partial else 200)
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range",
                             "bytes %d-%d/%d" % (start, end, total))
        self.send_header("Content-Length", str(len(chunk)))
        self.send_header("Content-Type",
                         self._content_type(path))
        self.end_headers()
        if not head:
            self.wfile.write(chunk)

    @staticmethod
    def _content_type(path):
        if path.endswith((".html",)):
            return "text/html; charset=utf-8"
        if path.endswith(".m3u8"):
            return "application/vnd.apple.mpegurl"
        if path.endswith(".mpd"):
            return "application/dash+xml"
        if path.endswith(".mp4"):
            return "video/mp4"
        if path.endswith(".ts"):
            return "video/mp2t"
        if path.endswith(".mp3"):
            return "audio/mpeg"
        if path.endswith(".aac"):
            return "audio/aac"
        return "application/octet-stream"


class LocalSite:
    """Context manager that runs the fixture site on a random port."""

    def __init__(self):
        self.fixture = SiteFixture()
        Handler.fixture = self.fixture
        self.httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.port

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
