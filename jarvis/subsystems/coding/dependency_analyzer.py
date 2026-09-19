"""File Dependency Awareness Engine for JARVIS Coding Agent (Phase 13).

Analyzes Python module ASTs across the workspace to trace internal dependencies,
reverse dependencies, and correlations between source files and test suites.
"""

from __future__ import annotations
import ast
import os
from typing import Dict, List, Optional, Set

from jarvis.subsystems.coding.schemas import FileDependencyGraph


class DependencyAnalyzer:
    """Discovers internal dependencies and correlates source code with test files."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = os.path.abspath(workspace_root)

    def analyze_workspace(
        self,
        target_dirs: Optional[List[str]] = None,
        max_files: int = 150,
    ) -> FileDependencyGraph:
        """Constructs an AST-derived dependency and test correlation graph."""
        dirs_to_scan = target_dirs or ["jarvis", "tests"]
        py_files: List[str] = []

        for d in dirs_to_scan:
            full_d = os.path.join(self.workspace_root, d)
            if not os.path.exists(full_d):
                continue
            for root, _, files in os.walk(full_d):
                if any(ignored in root for ignored in [".git", "__pycache__", "venv", ".venv"]):
                    continue
                for f in files:
                    if f.endswith(".py"):
                        py_files.append(os.path.abspath(os.path.join(root, f)))
                        if len(py_files) >= max_files:
                            break

        imports_by_file: Dict[str, List[str]] = {}
        dependents_by_file: Dict[str, List[str]] = {}
        test_mapping: Dict[str, List[str]] = {}

        for fpath in py_files:
            imported_modules = self.extract_imports(fpath)
            resolved_deps = self._resolve_internal_imports(imported_modules, py_files)
            imports_by_file[fpath] = resolved_deps

            for dep in resolved_deps:
                dependents_by_file.setdefault(dep, []).append(fpath)

        # Map tests to source modules
        for fpath in py_files:
            rel_p = os.path.relpath(fpath, self.workspace_root).replace("\\", "/")
            if rel_p.startswith("tests/") or "test_" in os.path.basename(fpath):
                # This is a test file. Check which source files it imports
                for dep in imports_by_file.get(fpath, []):
                    test_mapping.setdefault(dep, []).append(fpath)

                # Heuristic name matching: test_research_agent.py -> research_agent or schemas/planner
                base_stem = os.path.basename(fpath).replace("test_", "").replace(".py", "")
                for other_f in py_files:
                    if base_stem in os.path.basename(other_f).lower() and other_f != fpath:
                        if fpath not in test_mapping.setdefault(other_f, []):
                            test_mapping[other_f].append(fpath)

        return FileDependencyGraph(
            imports_by_file=imports_by_file,
            dependents_by_file=dependents_by_file,
            test_mapping=test_mapping,
        )

    def extract_imports(self, file_path: str) -> List[str]:
        """Parses AST to extract all module imports in a file."""
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code_text = f.read()
            tree = ast.parse(code_text, filename=file_path)
        except Exception:
            return []

        imported_names: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.add(node.module)

        return list(imported_names)

    def _resolve_internal_imports(
        self,
        import_names: List[str],
        known_files: List[str],
    ) -> List[str]:
        """Resolves module import paths like 'jarvis.subsystems.research' to absolute paths."""
        resolved: List[str] = []
        known_map = {f.replace("\\", "/").lower(): f for f in known_files}

        for imp in import_names:
            parts = imp.split(".")
            rel_candidate_py = "/".join(parts) + ".py"
            rel_candidate_init = "/".join(parts) + "/__init__.py"

            for candidate in [rel_candidate_py, rel_candidate_init]:
                for full_k, original_path in known_map.items():
                    if full_k.endswith(candidate.lower()):
                        if original_path not in resolved:
                            resolved.append(original_path)
                        break

        return resolved

    def find_associated_tests(self, source_file: str, graph: Optional[FileDependencyGraph] = None) -> List[str]:
        """Returns list of test files known to cover or reference the target source file."""
        fpath = os.path.abspath(source_file)
        if graph:
            return graph.get_associated_tests(fpath)

        # Fast heuristic fallback
        base_name = os.path.basename(fpath).replace(".py", "")
        tests_dir = os.path.join(self.workspace_root, "tests")
        candidates: List[str] = []

        if os.path.exists(tests_dir):
            for f in os.listdir(tests_dir):
                if f.endswith(".py") and (base_name in f or f"test_{base_name}" in f):
                    candidates.append(os.path.abspath(os.path.join(tests_dir, f)))

        return candidates
