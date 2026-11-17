import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import (
    CURSEFORGE,
    MODRINTH,
    IssueRecord,
    ModRecord,
    ReleaseRecord,
    RepositoryRecord,
)
from .versions import implied_loaders, normalize_loader, parse_game_version

# https://docs.curseforge.com/rest-api/#tocS_FileRelationType
CF_REQUIRED_DEPENDENCY = 3
CF_INCOMPATIBLE = 5
# https://docs.curseforge.com/rest-api/#tocS_HashAlgo
CF_HASH_SHA1 = 1

_GITHUB_REPO = re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+)/([^/?#\s]+)", re.I)


def repo_key(owner_and_name: str) -> str:
    """Ключ для сопоставления репозиториев: совпадает с именем файла data/github_<key>.json."""
    return owner_and_name.lower().removesuffix(".git").replace("/", "_")


def github_repo(url: str | None) -> str | None:
    match = _GITHUB_REPO.match(url or "")
    if not match:
        return None
    return repo_key(f"{match.group(1)}/{match.group(2)}")


def _read_json(path: Path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _make_release(platform, release_id, version, published, raw_loaders, raw_versions, file_name, sha1):
    game_versions = {v for v in map(parse_game_version, raw_versions) if v}
    loaders = {l for l in map(normalize_loader, raw_loaders) if l}
    loaders = implied_loaders(loaders, game_versions)
    if not loaders:
        return None
    return ReleaseRecord(
        platform=platform,
        id=release_id,
        version=version,
        published=_datetime(published),
        file_name=file_name,
        sha1=sha1,
        loaders=loaders,
        game_versions=game_versions,
    )


def read_curseforge(path: Path) -> ModRecord:
    raw = _read_json(path)
    mod = raw["mod"]
    links = mod.get("links") or {}

    record = ModRecord(
        platform=CURSEFORGE,
        id=mod["id"],
        slug=mod["slug"],
        name=mod["name"],
        summary=mod.get("summary") or None,
        project_url=links.get("websiteUrl") or None,
        source_repo=github_repo(links.get("sourceUrl")),
        issues_repo=github_repo(links.get("issuesUrl")),
        authors=[author["name"] for author in mod.get("authors", [])],
    )

    for file in raw["files"]:
        # CurseForge keeps loaders and game version in one list
        tags = file.get("gameVersions", [])
        release = _make_release(
            CURSEFORGE,
            file["id"],
            file.get("displayName") or file["fileName"],
            file.get("fileDate"),
            tags,
            tags,
            file["fileName"],
            next((h["value"] for h in file.get("hashes", []) if h["algo"] == CF_HASH_SHA1), None),
        )
        if release is None:
            continue
        for dependency in file.get("dependencies", []):
            target = (CURSEFORGE, dependency["modId"])
            if dependency["relationType"] == CF_REQUIRED_DEPENDENCY:
                release.requires.add(target)
            elif dependency["relationType"] == CF_INCOMPATIBLE:
                release.incompatible.add(target)
        record.releases.append(release)

    return record


def read_modrinth(path: Path) -> ModRecord:
    raw = _read_json(path)
    project = raw["project"]

    record = ModRecord(
        platform=MODRINTH,
        id=project["id"],
        slug=project["slug"],
        name=project["title"],
        summary=project.get("description") or None,
        project_url=f"https://modrinth.com/mod/{project['slug']}",
        source_repo=github_repo(project.get("source_url")),
        issues_repo=github_repo(project.get("issues_url")),
        authors=[member["user"]["username"] for member in raw.get("members", [])],
    )

    for version in raw["versions"]:
        files = version.get("files", [])
        primary = next((f for f in files if f.get("primary")), files[0] if files else {})
        release = _make_release(
            MODRINTH,
            version["id"],
            version["version_number"],
            version.get("date_published"),
            version.get("loaders", []),
            version.get("game_versions", []),
            primary.get("filename"),
            primary.get("hashes", {}).get("sha1"),
        )
        if release is None:
            continue
        for dependency in version.get("dependencies", []):
            if not dependency.get("project_id"):
                continue
            target = (MODRINTH, dependency["project_id"])
            if dependency["dependency_type"] == "required":
                release.requires.add(target)
            elif dependency["dependency_type"] == "incompatible":
                release.incompatible.add(target)
        record.releases.append(release)

    return record


def read_github(path: Path) -> RepositoryRecord:
    raw = _read_json(path)
    repository = raw["repository"]
    requested_key = path.stem.removeprefix("github_")

    issues = []
    for issue in raw.get("issues", []):
        if "pull_request" in issue:
            continue
        issue_type = issue.get("type")
        issues.append(
            IssueRecord(
                number=issue["number"],
                title=issue.get("title") or "",
                body=issue.get("body") or "",
                state=issue["state"],
                labels=[label["name"] for label in issue.get("labels", [])],
                issue_type=issue_type.get("name") if isinstance(issue_type, dict) else None,
            )
        )

    return RepositoryRecord(
        full_name=repository["full_name"],
        aliases={requested_key, repo_key(repository["full_name"])},
        url=repository["html_url"],
        owner=repository["owner"]["login"],
        owner_is_organization=repository["owner"]["type"] == "Organization",
        issues=issues,
    )


def iter_curseforge(data_dir: Path) -> Iterator[ModRecord]:
    for path in sorted(data_dir.glob("curseforge_*.json")):
        yield read_curseforge(path)


def iter_modrinth(data_dir: Path) -> Iterator[ModRecord]:
    for path in sorted(data_dir.glob("modrinth_*.json")):
        yield read_modrinth(path)


def read_repositories(data_dir: Path) -> list[RepositoryRecord]:
    by_name: dict[str, RepositoryRecord] = {}
    for path in sorted(data_dir.glob("github_*.json")):
        repository = read_github(path)
        canonical = repository.full_name.lower()
        if canonical in by_name:
            existing = by_name[canonical]
            existing.aliases |= repository.aliases
            if len(repository.issues) > len(existing.issues):
                existing.issues = repository.issues
        else:
            by_name[canonical] = repository
    return list(by_name.values())
