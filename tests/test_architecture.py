"""Enforce the layer boundaries declared in CLAUDE.md.

The engine is the product; it must not depend on the UI, platform, monetization,
or education layers. We assert this structurally by parsing imports so a stray
``import ui`` in engine code fails CI instead of rotting silently.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# layer -> set of top-level packages it is forbidden from importing
# "nativebridge" is the brief's platform layer (renamed to avoid shadowing the
# stdlib "platform" module). Pure layers must never import device code.
FORBIDDEN = {
    "engine": {"ui", "platform", "nativebridge", "monetization", "education"},
    "education": {"ui", "platform", "nativebridge"},
    "monetization": {"ui", "platform", "nativebridge"},
}


def _module_imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_layer_import_boundaries():
    violations: list[str] = []
    for layer, banned in FORBIDDEN.items():
        layer_dir = REPO_ROOT / layer
        if not layer_dir.exists():
            continue
        for py_file in layer_dir.rglob("*.py"):
            imported = _module_imports(py_file)
            for bad in imported & banned:
                rel = py_file.relative_to(REPO_ROOT)
                violations.append(f"{rel} imports forbidden layer '{bad}'")
    assert not violations, "Layer boundary violations:\n" + "\n".join(violations)


def test_engine_uses_no_unseeded_randomness():
    """engine/ logic must route randomness through engine.rng, not bare random."""
    offenders: list[str] = []
    engine_dir = REPO_ROOT / "engine"
    for py_file in engine_dir.rglob("*.py"):
        if py_file.name == "rng.py":
            continue  # the one place allowed to import `random`
        for root in _module_imports(py_file):
            if root in {"secrets"} or root == "random":
                rel = py_file.relative_to(REPO_ROOT)
                offenders.append(f"{rel} imports '{root}' (use engine.rng.GameRNG)")
    assert not offenders, "Unseeded randomness in engine:\n" + "\n".join(offenders)
