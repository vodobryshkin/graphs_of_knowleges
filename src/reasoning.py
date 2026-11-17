from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS


def _superclasses(schema: Graph) -> dict:
    direct = {}
    for sub, sup in schema.subject_objects(RDFS.subClassOf):
        direct.setdefault(sub, set()).add(sup)

    closure = {}
    for cls in direct:
        seen, stack = set(), list(direct[cls])
        while stack:
            parent = stack.pop()
            if parent not in seen:
                seen.add(parent)
                stack.extend(direct.get(parent, ()))
        closure[cls] = seen
    return closure


def materialize(graph: Graph, schema: Graph) -> dict[str, int]:
    stats = {}
    before = len(graph)

    for prop, inverse in schema.subject_objects(OWL.inverseOf):
        for subject, obj in list(graph.subject_objects(prop)):
            graph.add((obj, inverse, subject))
        for subject, obj in list(graph.subject_objects(inverse)):
            graph.add((obj, prop, subject))
    stats["owl:inverseOf"] = len(graph) - before

    before = len(graph)
    for cls, parents in _superclasses(schema).items():
        for individual in list(graph.subjects(RDF.type, cls)):
            for parent in parents:
                graph.add((individual, RDF.type, parent))
    stats["rdfs:subClassOf"] = len(graph) - before

    return stats
