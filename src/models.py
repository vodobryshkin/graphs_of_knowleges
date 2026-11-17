from dataclasses import dataclass, field
from datetime import datetime

from .versions import GameVersion

CURSEFORGE = "CurseForge"
MODRINTH = "Modrinth"

# mod link on platform, e.g. ("CurseForge", 238222) or ("Modrinth", "u6dRKJwZ")
ModRef = tuple[str, int | str]


@dataclass
class ReleaseRecord:
    platform: str
    id: int | str
    version: str
    published: datetime | None
    file_name: str | None = None
    sha1: str | None = None
    loaders: set[str] = field(default_factory=set)
    game_versions: set[GameVersion] = field(default_factory=set)
    requires: set[ModRef] = field(default_factory=set)
    incompatible: set[ModRef] = field(default_factory=set)


@dataclass
class Release:
    key: str  # IRI after mod key, e.g. "1.21.1-fabric-0.6.0"
    records: list[ReleaseRecord]  # Modrinth first

    @property
    def ids(self) -> set[tuple[str, int | str]]:
        return {(record.platform, record.id) for record in self.records}

    @property
    def version(self) -> str:
        return self.records[0].version

    @property
    def published(self) -> datetime | None:
        dates = [record.published for record in self.records if record.published]
        return min(dates) if dates else None

    @property
    def loaders(self) -> set[str]:
        return set().union(*(record.loaders for record in self.records))

    @property
    def game_versions(self) -> set[GameVersion]:
        return set().union(*(record.game_versions for record in self.records))

    @property
    def requires(self) -> set[ModRef]:
        return set().union(*(record.requires for record in self.records))

    @property
    def incompatible(self) -> set[ModRef]:
        return set().union(*(record.incompatible for record in self.records))


@dataclass
class ModRecord:
    platform: str
    id: int | str
    slug: str
    name: str
    summary: str | None
    project_url: str | None
    source_repo: str | None
    issues_repo: str | None
    authors: list[str] = field(default_factory=list)
    releases: list[ReleaseRecord] = field(default_factory=list)

    @property
    def ref(self) -> ModRef:
        return (self.platform, self.id)


@dataclass
class IssueRecord:
    number: int
    title: str
    body: str
    state: str  # open / closed
    labels: list[str]
    issue_type: str | None


@dataclass
class RepositoryRecord:
    full_name: str
    aliases: set[str]
    url: str
    owner: str
    owner_is_organization: bool
    issues: list[IssueRecord] = field(default_factory=list)


@dataclass
class Mod:
    key: str
    refs: set[ModRef] = field(default_factory=set)
    records: list[ModRecord] = field(default_factory=list)
    repository: RepositoryRecord | None = None
    releases: list[Release] = field(default_factory=list)

    @property
    def platforms(self) -> set[str]:
        return {platform for platform, _ in self.refs}

    @property
    def is_stub(self) -> bool:
        return not self.records

    @property
    def name(self) -> str | None:
        modrinth = [r for r in self.records if r.platform == MODRINTH]
        return (modrinth or self.records)[0].name if self.records else None
