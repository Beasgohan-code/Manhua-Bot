# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class MangaHereWebs(MadaraBase):
    def __init__(self):
        self.url = "https://www.mangahere.cc"
        self.sf = "mh"
        super().__init__()

