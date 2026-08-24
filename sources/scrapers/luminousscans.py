# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class LuminousScansWebs(MadaraBase):
    def __init__(self):
        self.url = "https://luminousscans.net"
        self.sf = "ls"
        super().__init__()

