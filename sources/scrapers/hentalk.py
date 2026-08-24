# Manhua-Bot - Hentalk (adult)
from sources.scrapers._madara import MadaraBase

class HentalkWebs(MadaraBase):
    def __init__(self):
        self.url = "https://hentalk.online"
        self.sf = "htalk"
        super().__init__()
