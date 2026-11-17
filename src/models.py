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
    loaders: set[str] = field(default_factory=set)
    game_versions: set[GameVersion] = field(default_factory=set)
    requires: set[ModRef] = field(default_factory=set)
    incompatible: set[ModRef] = field(default_factory=set)


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

    @property
    def releases(self) -> list[ReleaseRecord]:
        return [release for record in self.records for release in record.releases]
