"""Tests for AST dependency-graph construction (regex + tree-sitter paths)."""

from __future__ import annotations

from pathlib import Path

from app.services.ast_parser import (
    build_dependency_graph,
    detect_languages,
    regex_extract,
    treesitter_extract,
)


def _write(root: Path, relative: str, content: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


class TestRegexExtraction:
    def test_python_imports_and_symbols(self) -> None:
        code = (
            "import os, sys\n"
            "from app.services import vault\n"
            "\n"
            "def open_vault():\n"
            "    pass\n"
            "\n"
            "class Vault:\n"
            "    pass\n"
        )
        imports, symbols = regex_extract("python", code)
        assert "os" in imports and "sys" in imports
        assert "app.services" in imports
        assert "open_vault" in symbols and "Vault" in symbols

    def test_javascript_imports(self) -> None:
        code = (
            "import React from 'react';\n"
            "import { Button } from './ui/Button';\n"
            "const x = require('lodash');\n"
            "function App() { return null; }\n"
        )
        imports, symbols = regex_extract("javascript", code)
        assert "react" in imports
        assert "./ui/Button" in imports
        assert "lodash" in imports
        assert "App" in symbols

    def test_go_imports(self) -> None:
        code = "import \"fmt\"\nfunc main() { fmt.Println(1) }\n"
        imports, symbols = regex_extract("go", code)
        assert "fmt" in imports
        assert "main" in symbols


class TestDependencyGraph:
    def test_python_edge_resolution(self, tmp_path: Path) -> None:
        _write(tmp_path, "pkg/__init__.py", "")
        _write(tmp_path, "pkg/models.py", "class User:\n    pass\n")
        _write(tmp_path, "pkg/api.py", "from pkg.models import User\n\ndef handler(u: User):\n    pass\n")
        graph = build_dependency_graph(tmp_path, ["pkg/__init__.py", "pkg/models.py", "pkg/api.py"])
        paths = {node.path for node in graph.nodes}
        assert paths == {"pkg/__init__.py", "pkg/models.py", "pkg/api.py"}
        edges = {(e["source"], e["target"]) for e in graph.edges}
        assert ("pkg/api.py", "pkg/models.py") in edges

    def test_external_packages_collected(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "import fastapi\nimport httpx\nfrom app import local\n")
        graph = build_dependency_graph(tmp_path, ["app.py"])
        assert "fastapi" in graph.external_packages
        assert "httpx" in graph.external_packages

    def test_treesitter_path_available_or_fallback(self, tmp_path: Path) -> None:
        _write(tmp_path, "m.py", "import os\n")
        graph = build_dependency_graph(tmp_path, ["m.py"])
        assert len(graph.nodes) == 1  # never raises regardless of grammar availability

    def test_treesitter_extract_handles_missing_grammar(self) -> None:
        assert treesitter_extract("brainfuck", "+++") is None


class TestLanguageDetection:
    def test_histogram(self) -> None:
        histogram = detect_languages(["a.py", "b.py", "c.ts", "d.md"])
        assert histogram == {"python": 2, "typescript": 1}
