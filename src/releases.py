import re

from .models import MODRINTH, ModRecord, Release, ReleaseRecord
from .versions import LOADERS

_SEPARATORS = re.compile(r"([-_ ]+)")
_DIGIT = re.compile(r"\d")
_UNSAFE = re.compile(r"[^a-z0-9.\-]+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MIN_NAME_LETTERS = 5
_EXTENSION = re.compile(r"\.(jar|zip)$", re.I)


def _normalized(text: str) -> str:
    return _NON_ALNUM.sub("", text.lower())


def _is_name_word(token: str) -> bool:
    if token.lower() in LOADERS:
        return False
    if not _DIGIT.search(token):
        return True
    letters = sum(char.isalpha() for char in token)
    return token[0].isalpha() and "." not in token and letters >= _MIN_NAME_LETTERS


def release_label(release: ReleaseRecord, mod_names: set[str] = frozenset()) -> str:
    stem = _EXTENSION.sub("", release.file_name or release.version)
    tokens = _SEPARATORS.split(stem)

    # get longest prefix with mod name, e.g. fabric-api-..., 3dskinlayers-...
    start = 0
    for end in range(len(tokens) - 1, 0, -2):
        if _normalized("".join(tokens[:end - 1])) in mod_names:
            start = end
            break
    
    # remove other words, but loaders and versions
    while start < len(tokens) - 2 and _is_name_word(tokens[start]):
        start += 2

    # remove modname from version, e.g. journey1.0.0 -> 1.0.0
    rest = tokens[start:]
    for name in mod_names:
        if rest[0].lower().startswith(name) and rest[0][len(name):][:1].isdigit():
            rest[0] = rest[0][len(name):]
            break
    label = _UNSAFE.sub("_", "".join(rest).lower()).strip("_.-")
    return label or _UNSAFE.sub("_", str(release.id).lower())


def _modrinth_first(record: ModRecord) -> int:
    return 0 if record.platform == MODRINTH else 1


def _group(records: list[ModRecord]) -> list[list[ReleaseRecord]]:
    groups: list[list[ReleaseRecord]] = []
    by_sha: dict[str, list[ReleaseRecord]] = {}
    by_name: dict[str, list[ReleaseRecord]] = {}

    for record in sorted(records, key=_modrinth_first):
        for release in record.releases:
            group = by_sha.get(release.sha1) if release.sha1 else None
            if group is None and release.file_name:
                candidate = by_name.get(release.file_name)
                if candidate and all(r.platform != release.platform for r in candidate):
                    group = candidate
            if group is None:
                group = []
                groups.append(group)
            group.append(release)
            if release.sha1:
                by_sha.setdefault(release.sha1, group)
            if release.file_name:
                by_name.setdefault(release.file_name, group)
    return groups


def _order(group: list[ReleaseRecord]):
    dates = [r.published for r in group if r.published]
    return (min(dates).timestamp() if dates else 0.0, str(group[0].id))


def merge_releases(records: list[ModRecord]) -> list[Release]:
    mod_names = {_normalized(text) for record in records for text in (record.slug, record.name)}
    releases = []
    used: set[str] = set()
    for group in sorted(_group(records), key=_order):
        base = release_label(group[0], mod_names)
        key, suffix = base, 2
        while key in used:
            key, suffix = f"{base}_{suffix}", suffix + 1
        used.add(key)
        releases.append(Release(key=key, records=group))
    return releases
