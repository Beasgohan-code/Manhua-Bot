# Manhua-Bot - ManhwaReadWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class ManhwaReadWebs(MadaraBase):
    def __init__(self):
        self.url = "https://manhwaread.com"
        self.sf = "mread"
        super().__init__()
