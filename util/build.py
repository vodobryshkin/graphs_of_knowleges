import argparse
import sys
import time
from collections import Counter
from pathlib import Path

from rdflib.namespace import RDF

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.builder import GraphBuilder
from src.config import DATA_DIR, GRAPH_PATH, ONTOLOGY_PATH
from src.namespace import MC
from src.reasoning import materialize
from src.resolve import build_catalog
from src.schema import load_schema
from src.sources import iter_curseforge, iter_modrinth, read_repositories
from src.store import save_graph
from src.validate import validate


class Stopwatch:
    def __init__(self):
        self.start = time.perf_counter()

    def step(self, message: str):
        print(f"[{time.perf_counter() - self.start:6.1f} c] {message}", flush=True)


def print_statistics(graph):
    counts = Counter(graph.objects(None, RDF.type))
    print("\nЭкземпляры классов:")
    for cls in (MC.Mod, MC.Release, MC.Loader, MC.GameVersion, MC.Developer, MC.Person,
                MC.Team, MC.Repository, MC.Issue, MC.BugIssue, MC.CompatibilityIssue):
        print(f"  {graph.qname(cls):<22} {counts[cls]:>8}")

    print("\nСвязи:")
    for prop in (MC.dependsOn, MC.incompatibleWith, MC.supportsLoader, MC.supportsGameVersion,
                 MC.developedBy, MC.hasMember, MC.hasRepository, MC.hasIssue, MC.mentionsMod):
        print(f"  {graph.qname(prop):<22} {len(set(graph.subject_objects(prop))):>8}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="папка с выгрузками API")
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    parser.add_argument("--out", type=Path, default=GRAPH_PATH, help="файл графа (.ttl, .nt, .xml...)")
    parser.add_argument("--no-validate", action="store_true", help="пропустить проверку по онтологии")
    args = parser.parse_args()

    clock = Stopwatch()
    schema = load_schema(args.ontology)
    clock.step(f"Онтология: {len(schema)} триплетов")

    catalog = build_catalog(
        iter_curseforge(args.data),
        iter_modrinth(args.data),
        read_repositories(args.data),
    )
    real_mods = [m for m in catalog.mods if not m.is_stub]
    clock.step(
        f"Данные: {len(real_mods)} модов (+{len(catalog.mods) - len(real_mods)} только как зависимости), "
        f"{len(catalog.repositories)} репозиториев"
    )

    graph = GraphBuilder(catalog).build()
    clock.step(f"Триплетов из данных: {len(graph)}")

    graph += schema
    inferred = materialize(graph, schema)
    clock.step("Выведено: " + ", ".join(f"{rule} +{n}" for rule, n in inferred.items()))

    if not args.no_validate:
        findings = validate(graph, schema)
        clock.step("Проверка по онтологии: " + ("нарушений нет" if not findings else f"{len(findings)} типов предупреждений"))
        for finding in findings:
            print(f"  ! {finding}")

    print_statistics(graph)

    save_graph(graph, args.out)
    size = args.out.stat().st_size / 2**20
    clock.step(f"Сохранено: {args.out} ({len(graph)} триплетов, {size:.1f} МБ)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
