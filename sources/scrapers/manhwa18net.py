# Manhua-Bot - Manhwa18NetWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class Manhwa18NetWebs(MadaraBase):
    def __init__(self):
        self.url = "https://manhwa18.net"
        self.sf = "m18n"
        super().__init__()
