from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceSegment:
    path: Path
    qualname: str
    lineno: int
    end_lineno: int
    text: str

    @property
    def line_count(self) -> int:
        return self.end_lineno - self.lineno + 1


def extract_segment(repo_root: Path, rel_path: str, qualname: str) -> SourceSegment:
    path = repo_root / rel_path
    src = path.read_text()
    tree = ast.parse(src)
    parts = qualname.split(".")

    def find_in_body(body: list[ast.stmt], depth: int) -> ast.AST | None:
        if depth >= len(parts):
            return None
        name = parts[depth]
        for node in body:
            if isinstance(node, ast.ClassDef) and node.name == name:
                if depth == len(parts) - 1:
                    return node
                return find_in_body(node.body, depth + 1)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                if depth == len(parts) - 1:
                    return node
        return None

    node = find_in_body(tree.body, 0)
    if node is None or not hasattr(node, "lineno"):
        raise ValueError(f"{qualname} not found in {rel_path}")
    lines = src.splitlines()
    text = "\n".join(lines[node.lineno - 1 : node.end_lineno]) + "\n"
    return SourceSegment(path=path, qualname=qualname, lineno=node.lineno, end_lineno=node.end_lineno, text=text)


def assert_segment_rules(seg: SourceSegment) -> None:
    if not (10 <= seg.line_count <= 60):
        raise ValueError(f"{seg.qualname} in {seg.path}: {seg.line_count} lines (need 10-60)")
