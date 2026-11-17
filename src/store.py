from pathlib import Path

from rdflib import Graph
from rdflib.util import guess_format

from .namespace import bind_prefixes


def _format(path: Path) -> str:
    return guess_format(str(path)) or "turtle"


def save_graph(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=path, format=_format(path), encoding="utf-8")


def load_graph(path: Path) -> Graph:
    if not path.exists():
        raise FileNotFoundError(f"{path} не найден - сначала соберите граф: python util/build.py")
    return bind_prefixes(Graph()).parse(path, format=_format(path))
