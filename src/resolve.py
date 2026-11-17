import re
from dataclasses import dataclass, field

from .models import CURSEFORGE, MODRINTH, Mod, ModRecord, ModRef, RepositoryRecord
from .releases import merge_releases

_PARENTHESES = re.compile(r"\(.*\)")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_STUB_PREFIX = {CURSEFORGE: "cf", MODRINTH: "mr"}


@dataclass
class Catalog:
    mods: list[Mod]
    repositories: list[RepositoryRecord]
    by_ref: dict[ModRef, Mod] = field(default_factory=dict)

    def resolve(self, ref: ModRef) -> Mod:
        return self.by_ref[ref]


def _normalized_name(name: str) -> str:
    return _NON_ALNUM.sub("", _PARENTHESES.sub("", name.lower()))


def _canonical_repo(key: str | None, repo_index: dict[str, RepositoryRecord]) -> str | None:
    if key is None:
        return None
    repository = repo_index.get(key)
    return repository.full_name.lower() if repository else key


def _match_keys(record: ModRecord, repo_index) -> list[tuple[str, str]]:
    keys = []
    repo = _canonical_repo(record.source_repo, repo_index)
    if repo:
        keys.append(("repo", repo))
    keys.append(("slug", record.slug.lower()))
    keys.append(("name", _normalized_name(record.name)))
    return keys


def _pair_records(curseforge, modrinth, repo_index) -> list[list[ModRecord]]:
    cf_index: dict[tuple[str, str], list[ModRecord]] = {}
    for record in curseforge:
        for key in _match_keys(record, repo_index):
            cf_index.setdefault(key, []).append(record)

    groups = []
    paired: set[int] = set()
    for record in modrinth:
        match = None
        for key in _match_keys(record, repo_index):
            candidates = [c for c in cf_index.get(key, []) if id(c) not in paired]
            if candidates:
                match = candidates[0]
                break
        if match is None:
            groups.append([record])
        else:
            paired.add(id(match))
            groups.append([match, record])

    groups.extend([record] for record in curseforge if id(record) not in paired)
    return groups


def _find_repository(records: list[ModRecord], repo_index) -> RepositoryRecord | None:
    for attribute in ("source_repo", "issues_repo"):
        for record in records:
            key = getattr(record, attribute)
            if key in repo_index:
                return repo_index[key]
    return None


def _unique_key(base: str, used: set[str]) -> str:
    key, suffix = base, 2
    while key in used:
        key, suffix = f"{base}_{suffix}", suffix + 1
    used.add(key)
    return key


def build_catalog(curseforge, modrinth, repositories) -> Catalog:
    repo_index = {alias: repo for repo in repositories for alias in repo.aliases}
    catalog = Catalog(mods=[], repositories=repositories)
    used_keys: set[str] = set()

    for group in _pair_records(list(curseforge), list(modrinth), repo_index):
        primary = next((r for r in group if r.platform == MODRINTH), group[0])
        mod = Mod(
            key=_unique_key(primary.slug, used_keys),
            refs={record.ref for record in group},
            records=group,
            repository=_find_repository(group, repo_index),
            releases=merge_releases(group),
        )
        catalog.mods.append(mod)
        for ref in mod.refs:
            catalog.by_ref[ref] = mod

    # mods that are mentioned as dependencies but don't have info in data 
    for mod in list(catalog.mods):
        for release in mod.releases:
            for ref in release.requires | release.incompatible:
                if ref not in catalog.by_ref:
                    platform, mod_id = ref
                    stub = Mod(
                        key=_unique_key(f"{_STUB_PREFIX[platform]}_{mod_id}", used_keys),
                        refs={ref},
                    )
                    catalog.mods.append(stub)
                    catalog.by_ref[ref] = stub

    return catalog
