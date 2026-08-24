# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class WebtoonXYZWebs(MadaraBase):
    def __init__(self):
        self.url = "https://www.webtoon.xyz"
        self.sf = "wxyz"
        super().__init__()

