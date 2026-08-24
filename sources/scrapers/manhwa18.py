# Manhua-Bot - Manhwa18Webs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class Manhwa18Webs(MadaraBase):
    def __init__(self):
        self.url = "https://manhwa18.com"
        self.sf = "m18"
        super().__init__()
