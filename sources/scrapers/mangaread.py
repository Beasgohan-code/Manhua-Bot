# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class MangaReadWebs(MadaraBase):
    def __init__(self):
        self.url = "https://www.mangaread.org"
        self.sf = "mr"
        super().__init__()

