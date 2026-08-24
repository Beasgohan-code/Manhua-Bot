# Manhua-Bot - MangaDistrictWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class MangaDistrictWebs(MadaraBase):
    def __init__(self):
        self.url = "https://mangadistrict.com"
        self.sf = "mdist"
        super().__init__()
