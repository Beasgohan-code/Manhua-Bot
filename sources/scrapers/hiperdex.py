# Manhua-Bot - HiperDexWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class HiperDexWebs(MadaraBase):
    def __init__(self):
        self.url = "https://hiperdex.com"
        self.sf = "hdx"
        super().__init__()
