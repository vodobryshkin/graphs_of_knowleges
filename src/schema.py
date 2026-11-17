from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .namespace import bind_prefixes

_SCHEMA_NAMESPACES = (str(OWL), str(RDF), str(RDFS))


def _is_schema_type(node) -> bool:
    return isinstance(node, URIRef) and str(node).startswith(_SCHEMA_NAMESPACES)


def load_schema(path: Path) -> Graph:
    ontology = Graph().parse(path, format="turtle")
    individuals = {
        subject
        for subject, cls in ontology.subject_objects(RDF.type)
        if not _is_schema_type(cls)
    }
    schema = bind_prefixes(Graph())
    for triple in ontology:
        if triple[0] not in individuals:
            schema.add(triple)
    return schema
