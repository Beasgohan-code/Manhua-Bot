# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class ManhuaScanWebs(MadaraBase):
    def __init__(self):
        self.url = "https://manhuascan.io"
        self.sf = "ms"
        super().__init__()

