import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from . import storage


def _resolve_store_path(raw_path: str | None) -> Path:
    if raw_path:
        return Path(raw_path).expanduser()
    return storage._default_store_path()


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2))


def _validate_dir_store(path: Path) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "store_path": str(path),
        "mode": "directory",
        "total_files": 0,
        "valid_files": 0,
        "errors": [],
    }
    if not path.exists():
        return report
    for entry_path in sorted(path.glob("*.json")):
        report["total_files"] += 1
        try:
            entry = storage._load_tree_file(entry_path)
        except Exception as exc:
            report["errors"].append(
                {"path": str(entry_path), "error": str(exc)}
            )
            continue
        if not isinstance(entry, dict) or "tree_id" not in entry:
            report["errors"].append(
                {"path": str(entry_path), "error": "Missing tree_id"}
            )
            continue
        report["valid_files"] += 1
    return report


def _validate_file_store(path: Path) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "store_path": str(path),
        "mode": "file",
        "tree_count": 0,
        "errors": [],
    }
    try:
        store = storage._load_store(path)
    except Exception as exc:
        report["errors"].append({"path": str(path), "error": str(exc)})
        return report
    trees = store.get("trees", {})
    report["tree_count"] = len(trees)
    for tree_id, entry in trees.items():
        if not isinstance(entry, dict):
            report["errors"].append(
                {"tree_id": tree_id, "error": "Entry is not an object"}
            )
        elif "tree_id" not in entry:
            report["errors"].append(
                {"tree_id": tree_id, "error": "Missing tree_id"}
            )
    return report


def _validate_store(path: Path) -> Dict[str, Any]:
    if storage._is_dir_store(path):
        return _validate_dir_store(path)
    return _validate_file_store(path)


def _prune_dir_store(path: Path) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "store_path": str(path),
        "mode": "directory",
        "removed_files": 0,
        "errors": [],
    }
    if not path.exists():
        return report
    for entry_path in sorted(path.glob("*.json")):
        try:
            entry = storage._load_tree_file(entry_path)
        except Exception:
            entry_path.unlink()
            report["removed_files"] += 1
            continue
        if not isinstance(entry, dict) or "tree_id" not in entry:
            entry_path.unlink()
            report["removed_files"] += 1
    return report


def _prune_file_store(path: Path) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "store_path": str(path),
        "mode": "file",
        "removed_entries": 0,
        "errors": [],
    }
    try:
        store = storage._load_store(path)
    except Exception as exc:
        report["errors"].append({"path": str(path), "error": str(exc)})
        return report
    trees = store.get("trees", {})
    to_delete = []
    for tree_id, entry in trees.items():
        if not isinstance(entry, dict) or "tree_id" not in entry:
            to_delete.append(tree_id)
    for tree_id in to_delete:
        del trees[tree_id]
    report["removed_entries"] = len(to_delete)
    if to_delete:
        store["trees"] = trees
        storage._write_store(path, store)
    return report


def _prune_store(path: Path) -> Dict[str, Any]:
    if storage._is_dir_store(path):
        return _prune_dir_store(path)
    return _prune_file_store(path)


def main() -> None:
    parser = argparse.ArgumentParser(prog="draversal-store")
    parser.add_argument(
        "--store-path",
        help="Path to the tree store file or directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List stored trees.")
    list_parser.add_argument("--limit", type=int)

    subparsers.add_parser("validate", help="Validate the tree store.")
    subparsers.add_parser("prune", help="Remove corrupted entries.")

    args = parser.parse_args()
    store_path = _resolve_store_path(args.store_path)

    if args.command == "list":
        payload = storage.list_trees(limit=args.limit, store_path=store_path)
        _print_json(payload)
        return
    if args.command == "validate":
        report = _validate_store(store_path)
        _print_json(report)
        if report.get("errors"):
            sys.exit(1)
        return
    if args.command == "prune":
        report = _prune_store(store_path)
        _print_json(report)
        if report.get("errors"):
            sys.exit(1)
        return


if __name__ == "__main__":
    main()
