# Manhua-Bot - PornhwazWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class PornhwazWebs(MadaraBase):
    def __init__(self):
        self.url = "https://pornhwaz.com"
        self.sf = "phwaz"
        super().__init__()
