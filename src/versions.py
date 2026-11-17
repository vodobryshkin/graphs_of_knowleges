import re
from typing import NamedTuple

# snapshots, pre-release and release candidate are ignored
_RELEASE_VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")

LOADERS = {
    "forge": "Forge",
    "fabric": "Fabric",
    "neoforge": "NeoForge",
    "quilt": "Quilt",
}

# old mods have always Forge loader
_LEGACY_FORGE_BEFORE = (1, 14, 0)

class GameVersion(NamedTuple):
    major: int
    minor: int
    patch: int

    @property
    def text(self) -> str:
        if self.patch == 0:
            return f"{self.major}.{self.minor}"
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_game_version(value: str) -> GameVersion | None:
    match = _RELEASE_VERSION.match((value or "").strip())
    if not match:
        return None
    major, minor, patch = match.groups()
    return GameVersion(int(major), int(minor), int(patch or 0))


def normalize_loader(value: str) -> str | None:
    return LOADERS.get((value or "").strip().lower())


def implied_loaders(loaders: set[str], game_versions: set[GameVersion]) -> set[str]:
    if loaders or not game_versions:
        return loaders
    if max(game_versions) < _LEGACY_FORGE_BEFORE:
        return {"Forge"}
    return loaders
