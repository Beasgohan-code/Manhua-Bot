# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class NightScansWebs(MadaraBase):
    def __init__(self):
        self.url = "https://nightscans.org"
        self.sf = "ns"
        super().__init__()

