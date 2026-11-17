import re

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

MC = Namespace("http://example.org/minecraft-mods#")

PREFIXES = {
    "": MC,
    "owl": OWL,
    "rdf": RDF,
    "rdfs": RDFS,
    "xsd": XSD,
}

_UNSAFE = re.compile(r"[^A-Za-z0-9_\-]+")


def bind_prefixes(graph: Graph) -> Graph:
    for prefix, namespace in PREFIXES.items():
        graph.bind(prefix, namespace, override=True)
    return graph


def _local(*parts) -> str:
    return "_".join(_UNSAFE.sub("_", str(part)).strip("_") for part in parts)


def mod_iri(key: str) -> URIRef:
    return MC[_local("Mod", key)]


def release_iri(mod_key: str, release_key: str) -> URIRef:
    return MC[f"{_local('Rel', mod_key)}_{release_key}"]


def game_version_iri(version: str) -> URIRef:
    return MC[_local("MC", version.replace(".", "_"))]


def loader_iri(name: str) -> URIRef:
    return MC[name]


def person_iri(name: str) -> URIRef:
    return MC[_local("Person", name.lower())]


def team_iri(name: str) -> URIRef:
    return MC[_local("Team", name.lower())]


def repository_iri(full_name: str) -> URIRef:
    return MC[_local("Repo", full_name.lower().replace("/", "_"))]


def issue_iri(full_name: str, number: int) -> URIRef:
    return MC[_local("Issue", full_name.lower().replace("/", "_"), number)]
