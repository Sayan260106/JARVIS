"""Advanced File Organization Tools for JARVIS.

Implements directory inspection, SHA-256 duplicate detection, and category-based file sorting.
"""

from __future__ import annotations
import hashlib
import os
import shutil
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification


CATEGORY_EXTENSIONS: Dict[str, List[str]] = {
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".pptx", ".xlsx", ".md", ".csv", ".rtf"],
    "Images": [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"],
    "Media": [".mp3", ".wav", ".mp4", ".mkv", ".avi", ".mov", ".flac", ".m4a"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "Code": [".py", ".java", ".cpp", ".c", ".js", ".ts", ".html", ".css", ".json", ".sql"],
    "Executables": [".exe", ".msi", ".bat", ".cmd", ".ps1"],
}


def get_category_for_extension(ext: str) -> str:
    """Map file extension to standard category name."""
    clean_ext = ext.lower()
    for cat, exts in CATEGORY_EXTENSIONS.items():
        if clean_ext in exts:
            return cat
    return "Others"


def calculate_sha256(filepath: str, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file efficiently."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


class InspectDirectoryTool(BaseTool):
    """Deep inspection of a directory: total files, sizes, extensions, and categories."""
    name = "inspect_directory"
    description = "Scans a directory and returns file counts, category distribution, total size, and existing folders."
    risk_level = RiskLevel.LOW
    parameters = {
        "directory": ToolParameter("directory", "string", "Directory path to inspect.", required=True),
    }

    def execute(self, directory: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        abs_dir = os.path.abspath(directory)
        if not os.path.exists(abs_dir) or not os.path.isdir(abs_dir):
            return ToolResult(
                success=False,
                output=None,
                error=f"Directory does not exist: {abs_dir}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        total_files = 0
        total_bytes = 0
        categories = defaultdict(int)
        extensions = defaultdict(int)
        existing_folders = []
        file_list = []

        try:
            for item in os.listdir(abs_dir):
                full_path = os.path.join(abs_dir, item)
                if os.path.isdir(full_path):
                    existing_folders.append(item)
                elif os.path.isfile(full_path):
                    total_files += 1
                    size = os.path.getsize(full_path)
                    total_bytes += size
                    _, ext = os.path.splitext(item)
                    ext = ext.lower()
                    extensions[ext or "no_ext"] += 1
                    cat = get_category_for_extension(ext)
                    categories[cat] += 1
                    file_list.append({
                        "name": item,
                        "path": full_path,
                        "size": size,
                        "extension": ext,
                        "category": cat,
                    })

            output = {
                "directory": abs_dir,
                "total_files": total_files,
                "total_size_mb": round(total_bytes / (1024 * 1024), 2),
                "categories": dict(categories),
                "extension_breakdown": dict(extensions),
                "existing_folders": existing_folders,
                "file_list": file_list,
            }
            return ToolResult(
                success=True,
                output=output,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Inspection failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Inspected {result.output['total_files']} files across {len(result.output['categories'])} categories."
        )


class DetectDuplicatesTool(BaseTool):
    """Detects duplicate files in a directory using file size pre-filtering + SHA-256 hashes."""
    name = "detect_duplicates"
    description = "Identifies duplicate files in a directory based on identical content SHA-256 hashes."
    risk_level = RiskLevel.LOW
    parameters = {
        "directory": ToolParameter("directory", "string", "Directory path to check for duplicates.", required=True),
    }

    def execute(self, directory: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        abs_dir = os.path.abspath(directory)
        if not os.path.exists(abs_dir) or not os.path.isdir(abs_dir):
            return ToolResult(
                success=False,
                output=None,
                error=f"Directory does not exist: {abs_dir}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        try:
            # 1. Group files by size first (fast pre-filter)
            size_map = defaultdict(list)
            for item in os.listdir(abs_dir):
                full_path = os.path.join(abs_dir, item)
                if os.path.isfile(full_path):
                    try:
                        size = os.path.getsize(full_path)
                        size_map[size].append(full_path)
                    except OSError:
                        continue

            # 2. Hash only files that share the same size
            hash_map = defaultdict(list)
            for size, paths in size_map.items():
                if len(paths) > 1:
                    for p in paths:
                        try:
                            f_hash = calculate_sha256(p)
                            hash_map[f_hash].append(p)
                        except OSError:
                            continue

            # 3. Filter clusters with > 1 file sharing identical hash
            duplicate_clusters = []
            duplicate_file_paths = []
            total_duplicate_files = 0

            for f_hash, paths in hash_map.items():
                if len(paths) > 1:
                    duplicate_clusters.append({
                        "hash": f_hash,
                        "count": len(paths),
                        "files": paths,
                    })
                    # Exclude the original (first one), count remainder as duplicates
                    duplicate_file_paths.extend(paths[1:])
                    total_duplicate_files += (len(paths) - 1)

            output = {
                "directory": abs_dir,
                "total_duplicate_clusters": len(duplicate_clusters),
                "total_duplicates_found": total_duplicate_files,
                "duplicate_files": duplicate_file_paths,
                "clusters": duplicate_clusters,
            }
            return ToolResult(
                success=True,
                output=output,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Duplicate check failed: {result.error}")
        count = result.output.get("total_duplicates_found", 0)
        return ToolVerification(verified=True, details=f"Duplicate detection completed: {count} duplicates detected.")


class BatchOrganizeFilesTool(BaseTool):
    """Sorts files in a directory into categorized folders, preserving duplicates untouched."""
    name = "batch_organize_files"
    description = "Organizes files in a directory into category folders (Documents, Images, Media, Archives, Code, Executables), safely leaving duplicates untouched."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "directory": ToolParameter("directory", "string", "Directory path to organize.", required=True),
        "exclude_duplicates": ToolParameter("exclude_duplicates", "boolean", "If True, leaves duplicate files untouched.", required=False, default=True),
    }

    def execute(self, directory: str, exclude_duplicates: bool = True, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        abs_dir = os.path.abspath(directory)
        if not os.path.exists(abs_dir) or not os.path.isdir(abs_dir):
            return ToolResult(
                success=False,
                output=None,
                error=f"Directory does not exist: {abs_dir}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        try:
            # 1. Detect duplicates if requested
            duplicates_to_skip = set()
            if exclude_duplicates:
                detector = DetectDuplicatesTool()
                dup_res = detector.execute(directory=abs_dir)
                if dup_res.success:
                    # Mark duplicate files to skip (keep them untouched)
                    for cluster in dup_res.output.get("clusters", []):
                        for fpath in cluster["files"]:
                            duplicates_to_skip.add(os.path.normpath(fpath))

            moved_count = 0
            skipped_duplicates = 0
            categories_created = set()
            moved_records = []

            # 2. Iterate through files in directory
            for item in list(os.listdir(abs_dir)):
                full_path = os.path.join(abs_dir, item)
                norm_full = os.path.normpath(full_path)

                # Skip directories (already created categories)
                if os.path.isdir(full_path):
                    continue

                # Skip duplicates if requested
                if exclude_duplicates and norm_full in duplicates_to_skip:
                    skipped_duplicates += 1
                    continue

                # Determine category
                _, ext = os.path.splitext(item)
                category = get_category_for_extension(ext)
                target_folder = os.path.join(abs_dir, category)
                os.makedirs(target_folder, exist_ok=True)
                categories_created.add(category)

                dest_path = os.path.join(target_folder, item)
                # If name collision in target, append index
                if os.path.exists(dest_path):
                    base, e = os.path.splitext(item)
                    dest_path = os.path.join(target_folder, f"{base}_{int(time.time())}{e}")

                shutil.move(full_path, dest_path)
                moved_count += 1
                moved_records.append({"file": item, "category": category, "destination": dest_path})

            output = {
                "directory": abs_dir,
                "moved_files_count": moved_count,
                "categories_created": list(categories_created),
                "skipped_duplicates_count": skipped_duplicates,
                "moved_records": moved_records,
            }
            return ToolResult(
                success=True,
                output=output,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Batch organization failed: {result.error}")
        moved = result.output.get("moved_files_count", 0)
        cats = len(result.output.get("categories_created", []))
        return ToolVerification(
            verified=True,
            details=f"Organized {moved} files into {cats} categories."
        )
