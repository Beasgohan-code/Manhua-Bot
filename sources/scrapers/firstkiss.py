# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class FirstKissWebs(MadaraBase):
    def __init__(self):
        self.url = "https://1stkissmanga.me"
        self.sf = "fk"
        super().__init__()

