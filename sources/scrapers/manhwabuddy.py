# Manhua-Bot - ManhwaBuddyWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class ManhwaBuddyWebs(MadaraBase):
    def __init__(self):
        self.url = "https://manhwabuddy.com"
        self.sf = "mbuddy"
        super().__init__()
