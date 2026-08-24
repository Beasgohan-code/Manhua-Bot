# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class RizzFablesWebs(MadaraBase):
    def __init__(self):
        self.url = "https://rizzfables.com"
        self.sf = "rf"
        super().__init__()

