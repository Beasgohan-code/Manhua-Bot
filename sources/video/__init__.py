# Manhua-Bot - video source registry

from sources.video.base import VideoScraper

from sources.video.hentai import (
    HAnimeTVWebs,
    HentaiCityWebs,
    HentaiOceanWebs,
    HentaiShWebs,
    HentaverseWebs,
    MyHentaiMovieWebs,
    OnlyHentaiStuffWebs,
    WatchHentaiWebs,
    HStreamWebs,
    OppaiStreamWebs,
)

from sources.video.anime import (
    AllAnimeWebs,
    GogoAnimeWebs,
    AnimePaheWebs,
    AnimeKaiWebs,
)

# Order matters only for display.
VIDEO_SOURCES = [
    # Normal anime
    AllAnimeWebs,
    AnimePaheWebs,
    GogoAnimeWebs,
    AnimeKaiWebs,
    # Adult (hidden unless /adult on)
    HAnimeTVWebs,
    HentaiCityWebs,
    HentaiOceanWebs,
    HentaiShWebs,
    HentaverseWebs,
    MyHentaiMovieWebs,
    OnlyHentaiStuffWebs,
    WatchHentaiWebs,
    HStreamWebs,
    OppaiStreamWebs,
]

__all__ = ["VideoScraper", "VIDEO_SOURCES"] + [c.__name__ for c in VIDEO_SOURCES]
