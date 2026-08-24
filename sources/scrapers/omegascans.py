# Manhua-Bot auto site wrapper
from sources.scrapers._madara import MadaraBase

class OmegaScansWebs(MadaraBase):
    def __init__(self):
        self.url = "https://omegascans.org"
        self.sf = "os"
        super().__init__()

