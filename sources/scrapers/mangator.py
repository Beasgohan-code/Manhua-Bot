# Manhua-Bot - Mangator
from sources.scrapers._madara import MadaraBase

class MangatorWebs(MadaraBase):
    def __init__(self):
        self.url = "https://mangator.com"
        self.sf = "mtor"
        super().__init__()
