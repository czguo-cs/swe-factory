#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def read_instances(path: Path):
    """
    Reads instance files, returns an empty list if it does not exist.
    Supports .json and .jsonl formats.
    """
    if not path.exists():
        logger.warning(f"File not found: {path}, treating as an empty list")
        return []
    try:
        text = path.read_text(encoding='utf-8')
        if path.suffix.lower() == '.jsonl':
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            return json.loads(text)
    except Exception as e:
        logger.error(f"Failed to read or parse file ({path}): {e}")
        sys.exit(1)

def write_instances(instances, path: Path):
    """
    Writes the list of instances, automatically selecting json or jsonl format based on the suffix.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.suffix.lower() == '.jsonl':
            with path.open('w', encoding='utf-8') as f:
                for inst in instances:
                    f.write(json.dumps(inst, ensure_ascii=False) + '\n')
        else:
            path.write_text(
                json.dumps(instances, indent=2, ensure_ascii=False), encoding='utf-8'
            )
    except Exception as e:
        logger.error(f"Failed to write file ({path}): {e}")
        sys.exit(1)

def merge(primary, secondary):
    """
    Takes primary as the main list and absorbs all pull_numbers from secondary
    that are not in primary, ensuring pull_number uniqueness.
    """
    seen = {inst.get('pull_number') for inst in primary if 'pull_number' in inst}
    out = list(primary)
    for inst in secondary:
        pn = inst.get('pull_number')
        if pn is None:
            logger.warning("Skipping entry with missing pull_number")
            continue
        if pn not in seen:
            out.append(inst)
            seen.add(pn)
    return out

def find_version_file(directory: Path, suffix: str):
    """
    Finds a version file in the directory ending with suffix, supporting .json or .jsonl.
    Returns the first Path found, or None.
    """
    # First, look for a fixed format: dirname + suffix + ext
    for ext in ('.json', '.jsonl'):
        candidate = directory / f"{directory.name}{suffix}{ext}"
        if candidate.exists():
            return candidate
    # Then, use wildcards
    for ext in ('.json', '.jsonl'):
        matches = list(directory.glob(f"*{suffix}{ext}"))
        if matches:
            return matches[0]
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Merges `_versions_by_github` and `_versions_by_git` files in the same directory, and outputs `_versions_final`"
    )
    parser.add_argument("input_dir", help="Directory containing the version files")
    args = parser.parse_args()

    directory = Path(args.input_dir)
    if not directory.is_dir():
        logger.error(f"Input is not a directory: {directory}")
        sys.exit(1)

    # 1. Find the two version files
    github_file = find_version_file(directory, "_versions_by_github")
    git_file    = find_version_file(directory, "_versions_by_git")

    # 2. Read the files
    if github_file:
        logger.info(f"Using GitHub version file: {github_file.name}")
        primary = read_instances(github_file)
        ext = github_file.suffix
    else:
        logger.info("Could not find `_versions_by_github`, setting primary list to empty")
        primary = []
        ext = None

    if git_file:
        logger.info(f"Using Git checkout version file: {git_file.name}")
        secondary = read_instances(git_file)
        if ext is None:
            ext = git_file.suffix
    else:
        logger.info("Could not find `_versions_by_git`, setting secondary list to empty")
        secondary = []
        if ext is None:
            ext = ".json"

    # 3. Merge
    merged = merge(primary, secondary)

    # 3.1 Sort by pull_number in descending order (converted to int)
    try:
        merged.sort(key=lambda x: int(x.get('pull_number', 0)), reverse=True)
    except (ValueError, TypeError):
        merged.sort(key=lambda x: x.get('pull_number', ""), reverse=True)

    # 4. Write to versions_final
    output_path = directory / f"{directory.name}_versions_final{ext}"
    write_instances(merged, output_path)
    logger.info(
        f"✅ Merge complete: {len(primary)} + {len(merged)-len(primary)} new = {len(merged)} total entries, written to {output_path.name}"
    )

if __name__ == "__main__":
    main()