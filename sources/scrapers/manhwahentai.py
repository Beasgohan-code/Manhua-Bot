# Manhua-Bot - ManhwaHentaiWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class ManhwaHentaiWebs(MadaraBase):
    def __init__(self):
        self.url = "https://manhwahentai.me"
        self.sf = "mhent"
        super().__init__()
