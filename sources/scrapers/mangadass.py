# Manhua-Bot - MangaDassWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class MangaDassWebs(MadaraBase):
    def __init__(self):
        self.url = "https://mangadass.com"
        self.sf = "mdass"
        super().__init__()
