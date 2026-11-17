import re
from dataclasses import dataclass, field

from .models import IssueRecord, Mod

BUG = "bug"
COMPATIBILITY = "compatibility"

_LABEL_NOISE = re.compile(r"[^a-z0-9:+\- ]+")
_COMPAT_LABEL = re.compile(
    r"compat|conflict|other.?mod|another.?mod|external.?mod|cross.?mod|^a-mods$"
)
_BUG_LABEL = re.compile(r"bug|crash|defect|regression")
_NOT_BUG_LABEL = re.compile(r"not.?a.?bug")
_BUG_TYPES = {"bug", "crash"}

_COMPAT_TITLE = re.compile(r"compat|conflict", re.I)
_BUG_TITLE = re.compile(r"\bbug\b|\bcrash", re.I)

# ticket parts in which mod mentions don't matter (logs, stacktrace, mod list)
_CODE_BLOCK = re.compile(r"```.*?(```|$)", re.S)
_DETAILS = re.compile(r"<details>.*?(</details>|$)", re.S | re.I)
_URL = re.compile(r"https?://\S+")
_MAX_BODY_MENTIONS = 5

_COMMON_WORDS = {
    "balm", "bookshelf", "carry on", "clumps", "collective", "comforts", "continuity",
    "controlling", "dynamic lights", "essential", "iris", "jade", "mantle", "melody",
    "mod menu", "moonlight", "placebo", "spark",
}
_FORBIDDEN_ALIASES = {
    "api", "fabric", "forge", "ftb", "lib", "neo", "neoforge", "puzzles", "quilt", "text", "zoom",
}
_GENERIC_SUFFIX = re.compile(r"\s+(api|lib|library|shaders|mod)$", re.I)


@dataclass
class IssueAnalysis:
    kind: str | None
    mentions: set[str] = field(default_factory=set)


def _clean_name(name: str) -> str:
    name = re.sub(r"[^\w\s'\-./()\[\]]", "", name)  # remove emojis and other symbols
    return re.sub(r"\s+", " ", name).strip()


def _aliases(mod: Mod) -> set[str]:
    aliases = set()
    for record in mod.records:
        name = _clean_name(record.name)
        for inner in re.findall(r"[\[(]([^\[\]()/]+)[\])]", name):
            aliases.add(inner.strip())
        base = re.sub(r"\[.*?\]|\(.*\)", "", name)
        base = re.sub(r"\s+\S+/\S+$", "", base)
        for part in re.split(r"\s+-\s+", base):
            part = part.strip()
            aliases.add(part)
            aliases.add(_GENERIC_SUFFIX.sub("", part))
        if "-" in record.slug:
            aliases.add(record.slug)
    return {
        alias for alias in aliases
        if len(alias) >= 3 and alias.lower() not in _FORBIDDEN_ALIASES
    }


class IssueAnalyzer:
    def __init__(self, mods: list[Mod]):
        self._alias_to_mod: dict[str, str] = {}
        sensitive, insensitive = set(), set()
        for mod in mods:
            if mod.is_stub:
                continue
            for alias in _aliases(mod):
                if alias.lower() in _COMMON_WORDS:
                    alias = alias[0].upper() + alias[1:]
                    sensitive.add(alias)
                    self._alias_to_mod[alias] = mod.key
                else:
                    insensitive.add(alias)
                    self._alias_to_mod[alias.lower()] = mod.key
        self._sensitive = self._compile(sensitive, 0)
        self._insensitive = self._compile(insensitive, re.I)

    @staticmethod
    def _compile(aliases: set[str], flags) -> re.Pattern | None:
        if not aliases:
            return None
        # long names before short ones to recognize additional mods, e.g. "Sodium Extra" for "Sodium"
        ordered = sorted(aliases, key=len, reverse=True)
        body = "|".join(re.escape(alias) for alias in ordered)
        return re.compile(rf"(?<![\w\-])(?:{body})(?![\w\-])", flags)

    def find_mods(self, text: str) -> set[str]:
        found = set()
        if self._sensitive:
            found |= {self._alias_to_mod[m] for m in self._sensitive.findall(text)}
        if self._insensitive:
            found |= {self._alias_to_mod[m.lower()] for m in self._insensitive.findall(text)}
        return found

    def analyze(self, issue: IssueRecord, own_mods: set[str]) -> IssueAnalysis:
        title_mentions = self.find_mods(issue.title) - own_mods

        body = _URL.sub(" ", _DETAILS.sub(" ", _CODE_BLOCK.sub(" ", issue.body)))
        body_mentions = self.find_mods(body) - own_mods
        if len(body_mentions) > _MAX_BODY_MENTIONS:
            body_mentions = set()

        labels = [_LABEL_NOISE.sub("", label.lower()).strip() for label in issue.labels]
        if (
            any(_COMPAT_LABEL.search(label) for label in labels)
            or _COMPAT_TITLE.search(issue.title)
            or title_mentions
        ):
            kind = COMPATIBILITY
        elif (
            any(_BUG_LABEL.search(l) and not _NOT_BUG_LABEL.search(l) for l in labels)
            or (issue.issue_type or "").lower() in _BUG_TYPES
            or _BUG_TITLE.search(issue.title)
        ):
            kind = BUG
        else:
            kind = None

        return IssueAnalysis(kind=kind, mentions=title_mentions | body_mentions)
