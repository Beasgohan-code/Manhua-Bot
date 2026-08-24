# Manhua-Bot - Manga18fxWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class Manga18fxWebs(MadaraBase):
    def __init__(self):
        self.url = "https://manga18fx.com"
        self.sf = "m18fx"
        super().__init__()
