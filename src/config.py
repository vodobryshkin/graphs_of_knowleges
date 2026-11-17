from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ONTOLOGY_PATH = ROOT / "graph" / "ontology.ttl"
GRAPH_PATH = ROOT / "graph" / "graph-full.ttl"
