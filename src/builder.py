from collections import defaultdict

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from . import namespace as ns
from .issues import BUG, COMPATIBILITY, IssueAnalyzer
from .models import CURSEFORGE, MODRINTH, Mod, ReleaseRecord, RepositoryRecord
from .namespace import MC
from .resolve import Catalog
from .versions import LOADERS, GameVersion

_ISSUE_CLASSES = {BUG: MC.BugIssue, COMPATIBILITY: MC.CompatibilityIssue, None: MC.Issue}


def _string(value: str) -> Literal:
    return Literal(value, datatype=XSD.string)


class GraphBuilder:
    def __init__(self, catalog: Catalog, graph: Graph | None = None):
        self.catalog = catalog
        self.graph = ns.bind_prefixes(graph if graph is not None else Graph())
        self._game_versions: set[GameVersion] = set()

    def add(self, subject, predicate, obj):
        self.graph.add((subject, predicate, obj))

    def build(self) -> Graph:
        self._add_loaders()
        for mod in self.catalog.mods:
            self._add_mod(mod)
        for version in self._game_versions:
            self._add_game_version(version)
        self._add_developers()
        self._add_repositories()
        return self.graph

    def _add_loaders(self):
        for name in LOADERS.values():
            loader = ns.loader_iri(name)
            self.add(loader, RDF.type, MC.Loader)
            self.add(loader, MC.name, _string(name))

    def _add_game_version(self, version: GameVersion):
        node = ns.game_version_iri(version.text)
        self.add(node, RDF.type, MC.GameVersion)
        self.add(node, MC.versionString, _string(version.text))
        self.add(node, MC.majorVersion, Literal(version.major))
        self.add(node, MC.minorVersion, Literal(version.minor))
        self.add(node, MC.patchVersion, Literal(version.patch))

    def _add_mod(self, mod: Mod):
        node = ns.mod_iri(mod.key)
        self.add(node, RDF.type, MC.Mod)

        for platform, mod_id in mod.refs:
            self.add(node, MC.hostedOn, _string(platform))
            if platform == CURSEFORGE:
                self.add(node, MC.curseforgeId, Literal(int(mod_id)))
            elif platform == MODRINTH:
                self.add(node, MC.modrinthId, _string(mod_id))

        if mod.is_stub:
            return

        self.add(node, MC.name, _string(mod.name))
        self.add(node, MC.slug, _string(mod.key))
        summary = next((r.summary for r in sorted(mod.records, key=_modrinth_first) if r.summary), None)
        if summary:
            self.add(node, MC.description, _string(summary))
        for record in mod.records:
            if record.project_url:
                self.add(node, MC.projectUrl, Literal(record.project_url, datatype=XSD.anyURI))
        if mod.repository:
            self.add(node, MC.hasRepository, ns.repository_iri(mod.repository.full_name))

        releases = mod.releases
        for release in releases:
            self._add_release(node, release)

        dated = [r for r in releases if r.published]
        if dated:
            latest = max(dated, key=lambda r: r.published)
            self.add(node, MC.latestModVersion, _string(latest.version))
        game_versions = {v for r in releases for v in r.game_versions}
        if game_versions:
            self.add(node, MC.latestGameVersion, _string(max(game_versions).text))

    def _add_release(self, mod_node: URIRef, release: ReleaseRecord):
        platform = "cf" if release.platform == CURSEFORGE else "mr"
        node = ns.release_iri(platform, release.id)
        self.add(node, RDF.type, MC.Release)
        self.add(node, MC.isReleaseOf, mod_node)
        self.add(node, MC.versionString, _string(release.version))
        if release.published:
            self.add(node, MC.releaseDate, Literal(release.published, datatype=XSD.dateTime))

        for loader in release.loaders:
            self.add(node, MC.supportsLoader, ns.loader_iri(loader))
        for version in release.game_versions:
            self._game_versions.add(version)
            self.add(node, MC.supportsGameVersion, ns.game_version_iri(version.text))

        for prop, refs in ((MC.dependsOn, release.requires), (MC.incompatibleWith, release.incompatible)):
            for ref in refs:
                target = ns.mod_iri(self.catalog.resolve(ref).key)
                if target != mod_node:
                    self.add(node, prop, target)

    def _add_developers(self):
        team_members: dict[str, set[str]] = defaultdict(set)

        for mod in self.catalog.mods:
            mod_node = ns.mod_iri(mod.key)
            persons = {author for record in mod.records for author in record.authors}
            for author in persons:
                person = ns.person_iri(author)
                self.add(person, RDF.type, MC.Person)
                self.add(person, MC.name, _string(author))
                self.add(mod_node, MC.developedBy, person)

            repository = mod.repository
            if repository and repository.owner_is_organization:
                self.add(mod_node, MC.developedBy, ns.team_iri(repository.owner))
                team_members[repository.owner] |= persons

        for team_name, members in team_members.items():
            team = ns.team_iri(team_name)
            self.add(team, RDF.type, MC.Team)
            self.add(team, MC.name, _string(team_name))
            for member in members:
                self.add(team, MC.hasMember, ns.person_iri(member))

    def _add_repositories(self):
        analyzer = IssueAnalyzer(self.catalog.mods)
        mods_by_repo: dict[str, set[str]] = defaultdict(set)
        for mod in self.catalog.mods:
            if mod.repository:
                mods_by_repo[mod.repository.full_name].add(mod.key)

        for repository in self.catalog.repositories:
            self._add_repository(repository, analyzer, mods_by_repo[repository.full_name])

    def _add_repository(self, repository: RepositoryRecord, analyzer: IssueAnalyzer, own_mods: set[str]):
        node = ns.repository_iri(repository.full_name)
        self.add(node, RDF.type, MC.Repository)
        self.add(node, MC.name, _string(repository.full_name))
        self.add(node, MC.projectUrl, Literal(repository.url, datatype=XSD.anyURI))

        for issue in repository.issues:
            analysis = analyzer.analyze(issue, own_mods)
            issue_node = ns.issue_iri(repository.full_name, issue.number)
            self.add(issue_node, RDF.type, _ISSUE_CLASSES[analysis.kind])
            self.add(issue_node, MC.isIssueOf, node)
            self.add(issue_node, MC.issueTitle, _string(issue.title))
            self.add(issue_node, MC.issueNumber, Literal(issue.number))
            self.add(issue_node, MC.issueStatus, _string(issue.state))
            for mod_key in analysis.mentions:
                self.add(issue_node, MC.mentionsMod, ns.mod_iri(mod_key))


def _modrinth_first(record) -> int:
    return 0 if record.platform == MODRINTH else 1
