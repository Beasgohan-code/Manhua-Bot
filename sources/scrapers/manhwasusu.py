# Manhua-Bot - ManhwaSusuWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class ManhwaSusuWebs(MadaraBase):
    def __init__(self):
        self.url = "https://manhwasusu.com"
        self.sf = "msusu"
        super().__init__()
