from dataclasses import dataclass, field
from itertools import combinations

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

from .namespace import MC

_EXAMPLES = 3


@dataclass
class Finding:
    check: str
    count: int
    examples: list = field(default_factory=list)

    def __str__(self) -> str:
        examples = "; ".join(map(str, self.examples))
        return f"{self.check}: {self.count} (например: {examples})"


def _class_set(schema: Graph, node) -> set:
    """Именованный класс или owl:unionOf из нескольких классов."""
    if isinstance(node, BNode):
        union = schema.value(node, OWL.unionOf)
        return set(Collection(schema, union)) if union is not None else set()
    return {node}


def _types(graph: Graph) -> dict:
    types = {}
    for subject, cls in graph.subject_objects(RDF.type):
        types.setdefault(subject, set()).add(cls)
    return types


def _report(findings, check, violations):
    if violations:
        findings.append(Finding(check, len(violations), violations[:_EXAMPLES]))


def check_disjoint_classes(graph, schema, types, findings):
    for group in schema.subjects(RDF.type, OWL.AllDisjointClasses):
        members = list(Collection(schema, schema.value(group, OWL.members)))
        for first, second in combinations(members, 2):
            violations = [s for s, ts in types.items() if first in ts and second in ts]
            _report(findings, f"owl:AllDisjointClasses {graph.qname(first)} / {graph.qname(second)}", violations)


def check_functional(graph, schema, findings):
    for prop in schema.subjects(RDF.type, OWL.FunctionalProperty):
        counts = {}
        for subject in graph.subjects(prop, None):
            counts[subject] = counts.get(subject, 0) + 1
        violations = [s for s, n in counts.items() if n > 1]
        _report(findings, f"owl:FunctionalProperty {graph.qname(prop)}", violations)


def check_disjoint_properties(graph, schema, findings):
    for first, second in schema.subject_objects(OWL.propertyDisjointWith):
        pairs = set(graph.subject_objects(first)) & set(graph.subject_objects(second))
        _report(
            findings,
            f"owl:propertyDisjointWith {graph.qname(first)} / {graph.qname(second)}",
            sorted(pairs),
        )


def check_domain_range(graph, schema, types, findings):
    for prop in set(schema.subjects(RDF.type, OWL.ObjectProperty)) | set(
        schema.subjects(RDF.type, OWL.DatatypeProperty)
    ):
        domain = schema.value(prop, RDFS.domain)
        range_ = schema.value(prop, RDFS.range)
        domain_classes = _class_set(schema, domain) if domain is not None else set()
        datatype = range_ if range_ is not None and str(range_).startswith(str(XSD)) else None
        range_classes = _class_set(schema, range_) if range_ is not None and datatype is None else set()

        bad_domain, bad_range = [], []
        for subject, obj in graph.subject_objects(prop):
            if domain_classes and not domain_classes & types.get(subject, set()):
                bad_domain.append(subject)
            if datatype is not None:
                if not isinstance(obj, Literal) or obj.datatype != datatype:
                    bad_range.append((subject, obj))
            elif range_classes and not range_classes & types.get(obj, set()):
                bad_range.append((subject, obj))
        _report(findings, f"rdfs:domain {graph.qname(prop)}", bad_domain)
        _report(findings, f"rdfs:range {graph.qname(prop)}", bad_range)


def check_undeclared(graph, schema, findings):
    declared = set(schema.subjects(RDF.type, None))
    used = {p for p in graph.predicates() if isinstance(p, URIRef) and str(p).startswith(str(MC))}
    used |= {o for o in graph.objects(None, RDF.type) if str(o).startswith(str(MC))}
    _report(findings, "Не объявлены в онтологии", sorted(used - declared))


def check_releases_have_mod(graph, findings):
    orphans = [r for r in graph.subjects(RDF.type, MC.Release) if graph.value(r, MC.isReleaseOf) is None]
    _report(findings, "Релиз без :isReleaseOf", orphans)


def validate(graph: Graph, schema: Graph) -> list[Finding]:
    findings: list[Finding] = []
    types = _types(graph)
    check_undeclared(graph, schema, findings)
    check_disjoint_classes(graph, schema, types, findings)
    check_functional(graph, schema, findings)
    check_disjoint_properties(graph, schema, findings)
    check_domain_range(graph, schema, types, findings)
    check_releases_have_mod(graph, findings)
    return findings
