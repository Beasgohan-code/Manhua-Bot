# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class NatoMangaWebs(MadaraBase):
    def __init__(self):
        self.url = "https://www.natomanga.com"
        self.sf = "nm"
        super().__init__()

