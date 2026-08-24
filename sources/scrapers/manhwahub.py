# Manhua-Bot - ManhwaHubWebs (adult/manhwa)
from sources.scrapers._madara import MadaraBase

class ManhwaHubWebs(MadaraBase):
    def __init__(self):
        self.url = "https://manhwahub.net"
        self.sf = "mhub"
        super().__init__()
