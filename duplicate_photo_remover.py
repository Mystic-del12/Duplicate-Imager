#!/usr/bin/env python3
"""
Duplicate / similar image finder with:
 - threaded perceptual hashing (imagehash + Pillow)
 - grouping by Hamming distance (configurable threshold)
 - CLI options (threshold, keep strategy, action, dry-run, backup folder, threads)
 - CSV report option
 - optional interactive preview mode that opens images one-by-one for visual inspection
 - tqdm progress bars for hashing and processing

Dependencies:
    pip install pillow imagehash tqdm
Optional (safer deletion):
    pip install send2trash

Usage examples:
    # dry-run with progress bars
    python duplicate_photo_tool_documented_interactive.py /path/to/photos --dry-run --threshold 8 --keep largest --action move

    # interactive preview before moving (will open images)
    python duplicate_photo_tool_documented_interactive.py ~/Pictures --interactive

Notes:
 - Use --dry-run to simulate actions before running destructive operations.
 - Interactive mode will open each image using the system default viewer:
    - Windows: os.startfile
    - macOS: open
    - Linux: xdg-open
 - After viewing images for a group, the CLI asks whether to choose the keep file,
   use automatic strategy, skip the group, or quit the program.
"""

# ----------------------------
# Standard / 3rd-party imports
# ----------------------------
import argparse
import csv
import hashlib
import os
import shutil
import subprocess
import sys
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

# Third-party libs
try:
    import imagehash
    from PIL import Image
except Exception:
    print("Missing required libraries. Install with: pip install pillow imagehash")
    raise

# tqdm for progress bars; fallback to a dummy if not installed
try:
    from tqdm import tqdm
except Exception:
    # minimal fallback so code still runs if tqdm isn't available
    def tqdm(iterable=None, **kwargs):
        return iterable if iterable is not None else []
    print("tqdm not installed; progress bars will be disabled. Install with: pip install tqdm")

# Optional: send files to system trash (safer than permanent delete)
try:
    from send2trash import send2trash
    _HAVE_SEND2TRASH = True
except Exception:
    _HAVE_SEND2TRASH = False

# Allowed image file extensions (lowercase)
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}


# ----------------------------
# Helper functions
# ----------------------------

def compute_hash(path: Path, hash_size: int = 8) -> Tuple[Path, imagehash.ImageHash or None]:
    """
    Compute a perceptual hash for the image at `path`.
    Returns (path, hash) or (path, None) on failure.

    - Convert to grayscale and resize to 64x64 for stable hashing.
    - Use Image.LANCZOS for high-quality downsampling (works across Pillow versions).
    - Use dhash if available; fallback to phash.
    """
    try:
        with Image.open(path) as img:
            img = img.convert('L').resize((64, 64), Image.LANCZOS)
            h = imagehash.dhash(img, hash_size=hash_size) if hasattr(imagehash, 'dhash') else imagehash.phash(img)
            return path, h
    except Exception as e:
        print(f"Warning: could not hash {path}: {e}")
        return path, None


def find_image_files(root: Path) -> List[Path]:
    """
    Recursively find image files under `root`.
    Return list of pathlib.Path objects.
    """
    files = []
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            files.append(p)
    return files


def group_hashes(hash_list: List[Tuple[Path, imagehash.ImageHash]], threshold: int) -> Dict[str, List[Path]]:
    """
    Group images by Hamming distance threshold.

    - For speed, each new hash is compared only to the *first* hash in existing groups.
      This heuristic is simple and fast; for extremely large datasets consider an ANN approach.

    Returns dict mapping representative_hash_str -> list of Paths for groups with length > 1.
    """
    groups: List[List[Tuple[imagehash.ImageHash, Path]]] = []
    for path, h in hash_list:
        if h is None:
            continue
        placed = False
        for group in groups:
            if (h - group[0][0]) <= threshold:
                group.append((h, path))
                placed = True
                break
        if not placed:
            groups.append([(h, path)])
    result = {}
    for grp in groups:
        if len(grp) > 1:
            rep = str(grp[0][0])
            result[rep] = [p for _, p in grp]
    return result


def choose_keep_file(paths: List[Path], strategy: str) -> Path:
    """
    Choose which file to keep in a group based on strategy:
    - 'first'   : keep the first in sorted order
    - 'largest' : keep file with largest size
    - 'newest'  : keep file with newest mtime
    """
    if strategy == 'first':
        return paths[0]
    if strategy == 'largest':
        return max(paths, key=lambda p: p.stat().st_size)
    if strategy == 'newest':
        return max(paths, key=lambda p: p.stat().st_mtime)
    return paths[0]


def safe_move(src: Path, dst_folder: Path, dry_run=False) -> Path:
    """
    Move src into dst_folder, creating dst_folder if needed and avoiding filename collisions.
    If collision, append short SHA1 suffix to filename stem. If dry_run, do not perform move.
    Return the destination Path (actual or hypothetical).
    """
    dst_folder.mkdir(parents=True, exist_ok=True)
    dst = dst_folder / src.name
    if dst.exists():
        suffix = hashlib.sha1(str(src).encode()).hexdigest()[:8]
        dst = dst_folder / f"{src.stem}_{suffix}{src.suffix}"
    if dry_run:
        print(f"[DRY-RUN] Move: {src} -> {dst}")
    else:
        shutil.move(str(src), str(dst))
    return dst


def write_report_csv(report_path: Path, duplicates: Dict[str, List[Path]]):
    """
    Write CSV report with columns: group_hash, file_path
    """
    with report_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['group_hash', 'file_path'])
        for h, paths in duplicates.items():
            for p in paths:
                writer.writerow([h, str(p)])


def open_file_with_default_viewer(path: Path):
    """
    Open the file with the system's default image viewer.
    - Windows: os.startfile
    - macOS: 'open' command
    - Linux: 'xdg-open'
    We don't block after opening: the external viewer may spawn; the user can close it.
    """
    try:
        system = platform.system()
        if system == 'Windows':
            os.startfile(str(path))
        elif system == 'Darwin':  # macOS
            subprocess.call(['open', str(path)])
        else:  # assume Linux / Unix
            subprocess.call(['xdg-open', str(path)])
    except Exception as e:
        print(f"Could not open {path} with default viewer: {e}")


def interactive_choose_keep(paths: List[Path], default_strategy: str) -> Tuple[str, Path]:
    """
    Interactive routine used when --interactive is enabled.

    - Shows each image in the group one-by-one (opens with default viewer).
    - After viewing, prompts the user:
        [0..n-1] : type the index of the file you want to KEEP (keeps that file; others are duplicates)
        'a'      : use automatic strategy (default_strategy)
        's'      : skip this group (do nothing)
        'q'      : quit the entire program immediately

    Returns a tuple (decision, chosen_path)
      - decision: 'auto' | 'manual' | 'skip' | 'quit'
      - chosen_path: Path of chosen file to keep if applicable, else None
    """
    print("\nInteractive preview: opening images one-by-one for this group.")
    print("Close the external viewer window (if needed), then return here and follow the prompt.")
    # Open images sequentially so user can view; we open all so user can decide
    for idx, p in enumerate(paths):
        print(f"[{idx}] Opening: {p}")
        open_file_with_default_viewer(p)
    # Now prompt user for a choice
    while True:
        print("\nEnter the index of the file you want to KEEP (e.g. 0), or:")
        print("  a = use automatic strategy (use --keep strategy),")
        print("  s = skip this group (do nothing),")
        print("  q = quit program")
        choice = input("Your choice: ").strip().lower()
        if choice == 'a':
            # Use automatic strategy
            chosen = choose_keep_file(paths, default_strategy)
            return 'auto', chosen
        if choice == 's':
            return 'skip', None
        if choice == 'q':
            return 'quit', None
        # If numeric index, choose that file (validate)
        if choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(paths):
                return 'manual', paths[idx]
            else:
                print("Index out of range. Try again.")
        else:
            print("Unrecognized input. Try again.")


# ----------------------------
# Main CLI flow
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Find and handle duplicate/similar images by perceptual hash.")
    parser.add_argument('root', type=Path, help="Root folder to scan")
    parser.add_argument('--threshold', type=int, default=9, help="Hamming distance threshold (lower = more strict)")
    parser.add_argument('--keep', choices=['first', 'largest', 'newest'], default='first',
                        help="Which file to keep in each group")
    parser.add_argument('--action', choices=['move', 'copy', 'report'], default='move',
                        help="Action for duplicates (excluding kept file)")
    parser.add_argument('--backup-folder', type=Path, default=None,
                        help="Backup folder (defaults to <root>/duplicates_backup)")
    parser.add_argument('--dry-run', action='store_true', help="Simulate actions; do not move/copy/delete")
    parser.add_argument('--threads', type=int, default=8, help="Number of threads for hashing")
    parser.add_argument('--report-csv', type=Path, default=None, help="Write CSV report of duplicate groups")
    parser.add_argument('--interactive', action='store_true',
                        help="Interactive preview mode: open images one-by-one and ask which to keep")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print("Root folder must exist and be a directory.")
        sys.exit(1)

    backup_dir = args.backup_folder or root / "duplicates_backup"
    backup_dir = backup_dir.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {root} for images...")
    files = find_image_files(root)
    print(f"Found {len(files)} images. Hashing with {args.threads} threads...")

    # Threaded hashing with progress bar (tqdm)
    hash_list: List[Tuple[Path, imagehash.ImageHash or None]] = []
    if files:
        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            # Submit all tasks
            futures = {ex.submit(compute_hash, p): p for p in files}
            # Use tqdm to show progress; as futures complete increment the progress bar
            with tqdm(total=len(futures), desc="Hashing", unit="file") as pbar:
                for fut in as_completed(futures):
                    p, h = fut.result()
                    hash_list.append((p, h))
                    pbar.update(1)
    else:
        print("No files to process.")
        return

    print("Grouping similar images...")
    # We can show a trivial progress bar for grouping, but grouping is quick; still show for parity
    with tqdm(total=1, desc="Grouping", unit="step") as pbar_grp:
        duplicates = group_hashes(hash_list, threshold=args.threshold)
        pbar_grp.update(1)

    if not duplicates:
        print("No duplicate groups found.")
        return

    total_groups = len(duplicates)
    total_files = sum(len(v) for v in duplicates.values())
    print(f"Found {total_groups} duplicate groups comprising {total_files} files.")

    if args.report_csv:
        write_report_csv(args.report_csv, duplicates)
        print(f"Wrote CSV report to {args.report_csv}")

    moved = []
    # Use tqdm on groups being processed
    groups_items = list(duplicates.items())
    with tqdm(total=len(groups_items), desc="Processing groups", unit="group") as pbar_proc:
        for h, paths in groups_items:
            # Sort for deterministic behavior (affects 'first' strategy)
            paths_sorted = sorted(paths, key=lambda p: str(p))
            # Default chosen keep according to strategy (if not using interactive or user chooses 'a')
            auto_keep = choose_keep_file(paths_sorted, args.keep)

            chosen_keep = auto_keep  # may be overridden by interactive session
            # Interactive preview: open images and ask which to keep
            if args.interactive:
                decision, selected = interactive_choose_keep(paths_sorted, args.keep)
                if decision == 'quit':
                    print("Quitting program as requested by user.")
                    return
                if decision == 'skip':
                    print("Skipping this group (no changes).")
                    pbar_proc.update(1)
                    continue
                if decision in ('auto', 'manual'):
                    if decision == 'auto':
                        chosen_keep = selected  # selected == auto_keep here
                    else:
                        chosen_keep = selected

            # Files to handle are all except chosen_keep
            to_handle = [p for p in paths_sorted if p != chosen_keep]
            hash_folder = backup_dir / h

            # For each duplicate, perform the requested action
            for p in to_handle:
                if args.action == 'report':
                    print(f"[REPORT] Keep: {chosen_keep}  Duplicate: {p}")
                    continue

                if args.action == 'copy':
                    dst = hash_folder / p.name
                    if dst.exists():
                        suffix = hashlib.sha1(str(p).encode()).hexdigest()[:8]
                        dst = hash_folder / f"{p.stem}_{suffix}{p.suffix}"
                    if args.dry_run:
                        print(f"[DRY-RUN] Copy: {p} -> {dst}")
                    else:
                        hash_folder.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(p), str(dst))
                        print(f"Copied {p} -> {dst}")
                        moved.append(dst)
                else:  # move
                    dst = safe_move(p, hash_folder, dry_run=args.dry_run)
                    moved.append(dst)

            pbar_proc.update(1)

    print(f"Processing complete. {'(dry-run)' if args.dry_run else ''} Processed {len(moved)} files.")

    # Offer to send backup folder to system trash if send2trash is available
    if not args.dry_run and moved:
        if _HAVE_SEND2TRASH:
            confirm = input("Send backup folder to system trash? (y/n): ").strip().lower()
            if confirm == 'y':
                try:
                    send2trash(str(backup_dir))
                    print("Backup folder moved to trash.")
                except Exception as e:
                    print(f"Error sending to trash: {e}")
        else:
            print("send2trash not installed; backup folder left at:", backup_dir)
            print("Install send2trash to enable safer deletion: pip install send2trash")


if __name__ == "__main__":
    main()
