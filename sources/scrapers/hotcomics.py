# Manhua-Bot - HotComicsWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class HotComicsWebs(MadaraBase):
    def __init__(self):
        self.url = "https://hotcomics.me"
        self.sf = "hotc"
        super().__init__()
