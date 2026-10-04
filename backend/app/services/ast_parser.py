"""AST dependency-graph construction via tree-sitter (with regex fallback).

For every source file we extract:
* imports / dependency targets (module specifiers),
* top-level symbols (classes, functions, components).

These feed the dependency graph (edges resolved to sibling files) and the
token-aware context windowing stage. When tree-sitter grammars are not
installed the parser degrades gracefully to battle-tested regex extraction
per language, so ingestion never hard-fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional native dependency
    from tree_sitter_language_pack import get_parser

    TREE_SITTER_AVAILABLE = True
except ImportError:  # pragma: no cover
    TREE_SITTER_AVAILABLE = False

LANGUAGE_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
}

_MAX_FILE_BYTES = 1_000_000  # skip absurdly large sources


@dataclass(slots=True)
class FileNode:
    """A parsed source file."""

    path: str
    language: str
    loc: int
    imports: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DependencyGraphData:
    """Result of parsing a repository."""

    nodes: list[FileNode] = field(default_factory=list)
    edges: list[dict[str, str | None]] = field(default_factory=list)
    external_packages: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": node.path,
                    "path": node.path,
                    "language": node.language,
                    "loc": node.loc,
                    "imports": node.imports,
                    "symbols": node.symbols,
                }
                for node in self.nodes
            ],
            "edges": self.edges,
            "external_packages": self.external_packages,
        }


# ── Regex fallbacks ─────────────────────────────────────────────────────────
_PY_IMPORT = re.compile(
    r"^\s*(?:from\s+(?P<from>[\w\.]+)\s+import|import\s+(?P<plain>[\w\., \t]+))",
    re.MULTILINE,
)
_PY_SYMBOL = re.compile(r"^\s*(?:class|def)\s+(?P<name>\w+)", re.MULTILINE)
_JS_IMPORT = re.compile(
    r"""(?:import\s+(?:[\w{}\s,*]+\s+from\s+)?[\"'](?P<spec>[^\"']+)[\"']|"""
    r"""require\(\s*[\"'](?P<req>[^\"']+)[\"']\s*\)|"""
    r"""import\(\s*[\"'](?P<dynamic>[^\"']+)[\"']\s*\))"""
)
_JS_SYMBOL = re.compile(
    r"""(?:function\s+(?P<fn>\w+)|class\s+(?P<cls>\w+)|const\s+(?P<const>\w+)\s*=\s*(?:\(|async))"""
)
_GO_IMPORT = re.compile(
    r"^\s*(?:import\s+)?[\"'](?P<spec>[\w./-]+)[\"']\s*$", re.MULTILINE
)
_GO_SYMBOL = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(?P<name>\w+)", re.MULTILINE)
_RS_USE = re.compile(r"^\s*use\s+(?P<spec>[\w::{},\s]+);", re.MULTILINE)
_RS_SYMBOL = re.compile(r"^\s*(?:pub\s+)?(?:fn|struct|enum|trait)\s+(?P<name>\w+)", re.MULTILINE)
_RB_REQUIRE = re.compile(r"^\s*require(?:_relative)?\s+[\"'](?P<spec>[^\"']+)[\"']", re.MULTILINE)
_RB_SYMBOL = re.compile(r"^\s*(?:class|module|def)\s+(?P<name>[\w:]+)", re.MULTILINE)
_JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?(?P<spec>[\w.\*]+);", re.MULTILINE)
_JAVA_SYMBOL = re.compile(r"\b(?:class|interface|enum)\s+(?P<name>\w+)")


def _match_all(pattern: re.Pattern[str], text: str, group: str) -> list[str]:
    return [m.group(group) for m in pattern.finditer(text) if m.group(group)]


def _split_commas(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def regex_extract(language: str, text: str) -> tuple[list[str], list[str]]:
    """Language-aware regex extraction of (imports, symbols)."""
    imports: list[str] = []
    symbols: list[str] = []
    if language == "python":
        for match in _PY_IMPORT.finditer(text):
            if match.group("from"):
                imports.append(match.group("from"))
            elif match.group("plain"):
                imports.extend(_split_commas(match.group("plain")))
        symbols = _match_all(_PY_SYMBOL, text, "name")
    elif language in ("javascript", "typescript"):
        for match in _JS_IMPORT.finditer(text):
            spec = next(
                (g for g in (match.group("spec"), match.group("req"), match.group("dynamic")) if g),
                None,
            )
            if spec:
                imports.append(spec)
        for match in _JS_SYMBOL.finditer(text):
            symbols.append(next(g for g in match.groups() if g))
    elif language == "go":
        imports = _match_all(_GO_IMPORT, text, "spec")
        symbols = _match_all(_GO_SYMBOL, text, "name")
    elif language == "rust":
        for match in _RS_USE.finditer(text):
            for part in re.split(r"[{},]", match.group("spec")):
                part = part.replace("crate::", "").strip()
                if part and part.isidentifier():
                    imports.append(part)
        symbols = _match_all(_RS_SYMBOL, text, "name")
    elif language == "ruby":
        imports = _match_all(_RB_REQUIRE, text, "spec")
        symbols = _match_all(_RB_SYMBOL, text, "name")
    elif language == "java":
        imports = _match_all(_JAVA_IMPORT, text, "spec")
        symbols = _match_all(_JAVA_SYMBOL, text, "name")
    return imports, symbols


# ── tree-sitter extraction ──────────────────────────────────────────────────
_TS_QUERIES: dict[str, str] = {
    "python": """
        (import_from_statement module_name: (dotted_name) @import)
        (import_statement name: (dotted_name) @import)
        (function_definition name: (identifier) @symbol)
        (class_definition name: (identifier) @symbol)
    """,
    "javascript": """
        (import_statement source: (string) @import)
        (call_expression function: (identifier) @_req arguments: (arguments (string) @import)
          (#eq? @_req "require"))
        (function_declaration name: (identifier) @symbol)
        (class_declaration name: (identifier) @symbol)
    """,
    "typescript": """
        (import_statement source: (string) @import)
        (function_declaration name: (identifier) @symbol)
        (class_declaration name: (identifier) @symbol)
        (interface_declaration name: (type_identifier) @symbol)
    """,
}


def treesitter_extract(language: str, text: str) -> tuple[list[str], list[str]] | None:
    """Try tree-sitter extraction; return None when unavailable."""
    if not TREE_SITTER_AVAILABLE or language not in _TS_QUERIES:
        return None
    try:
        parser = get_parser(language)
        query = _TS_QUERIES[language]
        tree = parser.parse(text.encode("utf-8", "replace"))
        captures: dict[str, list[str]] = {}
        compiled = parser.language.query(query) if hasattr(parser, "language") else None
        if compiled is None:
            return None
        for capture_name, nodes in compiled.captures(tree.root_node).items():
            captures[capture_name] = [
                n.text.decode("utf-8", "replace").strip("\"'") for n in nodes
            ]
        return captures.get("import", []), captures.get("symbol", [])
    except Exception:  # noqa: BLE001 - any grammar issue → graceful fallback
        return None


# ── Graph construction ──────────────────────────────────────────────────────
def _normalize_relative_import(base_dir: str, module: str) -> str:
    """Convert ``pkg.mod`` module syntax into a repo-relative path guess."""
    parts = module.lstrip(".").split(".")
    while parts and parts[0] in ("src", "lib", "app"):
        parts.pop(0)
    if not parts:
        return ""
    return "/".join(parts)


def build_dependency_graph(
    root: Path,
    relative_paths: list[str],
) -> DependencyGraphData:
    """Parse every source file and resolve edges to sibling files."""
    graph = DependencyGraphData()
    path_set = set(relative_paths)
    stem_index: dict[str, list[str]] = {}
    for relative in relative_paths:
        stem = Path(relative).stem
        stem_index.setdefault(stem, []).append(relative)

    external: set[str] = set()

    for relative in relative_paths:
        suffix = Path(relative).suffix.lower()
        language = LANGUAGE_BY_SUFFIX.get(suffix)
        if language is None:
            continue
        target = root / relative
        try:
            if target.stat().st_size > _MAX_FILE_BYTES:
                continue
            text = target.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        extracted = treesitter_extract(language, text)
        if extracted is None:
            extracted = regex_extract(language, text)
        imports, symbols = extracted
        loc = len(text.splitlines())
        graph.nodes.append(
            FileNode(path=relative, language=language, loc=loc, imports=imports, symbols=symbols)
        )

        importer_dir = str(Path(relative).parent)
        for module in imports:
            candidate = _resolve_import(
                importer_dir, module, language, path_set, stem_index
            )
            if candidate and candidate != relative:
                graph.edges.append(
                    {"source": relative, "target": candidate, "symbol": None}
                )
            elif not module.startswith((".", "/", "node_modules")):
                root_package = re.split(r"[./]", module)[0]
                if root_package and root_package not in ("", "crate"):
                    external.add(root_package)

    graph.external_packages = sorted(external)
    graph.nodes.sort(key=lambda n: n.path)
    graph.edges.sort(key=lambda e: (str(e["source"]), str(e["target"])))
    return graph


def _resolve_import(
    importer_dir: str,
    module: str,
    language: str,
    path_set: set[str],
    stem_index: dict[str, list[str]],
) -> str:
    """Best-effort resolution of an import to a file inside the repo."""
    module = module.strip().strip("\"'")

    if language in ("javascript", "typescript"):
        if module.startswith("."):
            base = (Path(importer_dir) / module).as_posix().lstrip("./")
            base = base.removesuffix(".js").removesuffix(".ts")
            for suffix in ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"):
                candidate = f"{base}{suffix}"
                if candidate in path_set:
                    return candidate
            return ""
        stem = module.rsplit("/", 1)[-1]
        for candidate in stem_index.get(stem, []):
            return candidate
        return ""

    if language == "python":
        if module.startswith("."):
            depth = len(module) - len(module.lstrip("."))
            name = module.lstrip(".")
            base_parts = Path(importer_dir).parts
            keep = max(0, len(base_parts) - (depth - 1))
            prefix = "/".join(base_parts[:keep])
            candidates = [f"{prefix}/{name.replace('.', '/')}.py" if prefix else f"{name.replace('.', '/')}.py"]
            candidates.append(
                f"{prefix}/{Path(name.replace('.', '/')).stem}/__init__.py"
                if prefix
                else f"{Path(name.replace('.', '/')).stem}/__init__.py"
            )
            for candidate in candidates:
                if candidate in path_set:
                    return candidate
            return ""
        guess = _normalize_relative_import(importer_dir, module)
        if not guess:
            return ""
        for candidate in (f"{guess}.py", f"{guess}/__init__.py"):
            if candidate in path_set:
                return candidate
        stem = module.rsplit(".", 1)[-1]
        matches = stem_index.get(stem, [])
        return matches[0] if len(matches) == 1 else ""

    if language == "go":
        guess = module.lstrip("./")
        for candidate in (f"{guess}.go",):
            if candidate in path_set:
                return candidate
        return ""

    if language in ("rust", "java", "ruby"):
        stem = re.split(r"[/:.]", module)[-1]
        matches = stem_index.get(stem, [])
        return matches[0] if len(matches) == 1 else ""

    return ""


def detect_languages(relative_paths: list[str]) -> dict[str, int]:
    """Histogram of language → file count."""
    histogram: dict[str, int] = {}
    for relative in relative_paths:
        language = LANGUAGE_BY_SUFFIX.get(Path(relative).suffix.lower())
        if language:
            histogram[language] = histogram.get(language, 0) + 1
    return dict(sorted(histogram.items(), key=lambda kv: -kv[1]))
