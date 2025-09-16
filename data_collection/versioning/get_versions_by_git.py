#!/usr/bin/env python3
import os
import shutil
import subprocess
import re
import json
import argparse
from contextlib import contextmanager
from typing import List, Dict
from concurrent.futures import ProcessPoolExecutor, as_completed
import glob
@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def run_command(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=True, **kwargs)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}, {e}")
        raise


def get_version_by_git(cloned_dir: str) -> str:
    if not os.path.isdir(cloned_dir):
        raise NotADirectoryError(f"Invalid directory: {cloned_dir}")
    with cd(cloned_dir):
        result = run_command(["git", "describe", "--tags"], capture_output=True, text=True)
        version = result.stdout.strip()
        print(f"✔️ Current version: {version}")
        match = re.search(r"(\d+\.\d+)(?:\.\d+)?", version)
        if match:
            return match.group(1)
        raise RuntimeError(f"Unrecognized version: {version}")


def get_instances(instance_path: str) -> List[Dict]:
    if instance_path.endswith((".jsonl", ".jsonl.all")):
        with open(instance_path, encoding="utf-8") as f:
            return [json.loads(line) for line in f]
    with open(instance_path, encoding="utf-8") as f:
        return json.load(f)


def prepare_repo_cache(tasks: List[Dict], cache_dir: str) -> Dict[str, str]:
    os.makedirs(cache_dir, exist_ok=True)
    repo_cache = {}
    for task in tasks:
        repo = task["repo"]
        if repo in repo_cache:
            continue
        repo_url = f"https://github.com/{repo}.git"
        local_path = os.path.join(cache_dir, repo.replace("/", "__"))
        try:
            run_command(["git", "clone", repo_url, local_path], capture_output=True)
            repo_cache[repo] = local_path
            print(f"✅ Cached repo: {repo}")
        except Exception as e:
            print(f"❌ Failed to clone {repo}: {e}")
    return repo_cache


def process_repo_task(task: Dict, testbed: str, repo_cache: Dict[str, str]) -> Dict | None:
    instance_id = task["instance_id"]
    repo = task["repo"]
    base_commit = task["base_commit"]
    repo_dir = os.path.join(testbed, instance_id)
    os.makedirs(repo_dir, exist_ok=True)
    try:
        cached_repo = repo_cache.get(repo)
        if not cached_repo or not os.path.exists(cached_repo):
            raise RuntimeError(f"Missing cached repo for {repo}")
        shutil.copytree(cached_repo, repo_dir, dirs_exist_ok=True)
        with cd(repo_dir):
            run_command(["git", "checkout", base_commit], capture_output=True)
        version = get_version_by_git(repo_dir)
        result = task.copy()
        result["version"] = version
        return result
    except Exception as e:
        print(f"❌ Failed: {instance_id} | {e}")
        return None
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)


def process_repos(tasks: List[Dict], testbed: str, repo_cache: Dict[str, str], max_workers: int = 4) -> List[Dict]:
    os.makedirs(testbed, exist_ok=True)
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_repo_task, t, testbed, repo_cache) for t in tasks]
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
    return results


def save_results(results: List[Dict], output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if output_path.endswith((".jsonl", ".jsonl.all")):
        with open(output_path, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)


def generate_output_path(instance_path: str, suffix: str) -> str:
    base, ext = os.path.splitext(instance_path)
    ext='.json'
    return f"{base}{suffix}{ext}"

def find_github_file(output_dir: str) -> str | None:
    """
    search file
    """
    # 通配所有 _versions_by_github.json 或 jsonl
    for ext in ('json', 'jsonl'):
        pattern = os.path.join(output_dir, f"*_versions_by_github.{ext}")
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance_path", "-i", type=str, required=True,
                        help="Path to input task file (.json or .jsonl)")
    parser.add_argument("--testbed", "-t", type=str, default="testbed",
                        help="Temp working directory for cloning repos")
    parser.add_argument("--max_workers", "-w", type=int, default=10,
                        help="Number of parallel workers")
    parser.add_argument("--output_dir", "-d", type=str, default=None,
                        help="Directory to save output (keeps original filename + suffix)")
    parser.add_argument("--last_stage_output_dir", "-l", type=str, default=None,
                        help="Directory to save output (keeps original filename + suffix)")
    args = parser.parse_args()


    try:
        tasks = get_instances(args.instance_path)
    except Exception as e:
        print(f"❌ Error reading instance file: {e}")
        return

   
    github_file = find_github_file(args.last_stage_output_dir)
    
    if github_file:
        try:
            processed = get_instances(github_file)
            seen = {item.get('instance_id') for item in processed if 'instance_id' in item}
            before = len(tasks)
            tasks = [t for t in tasks if t.get('instance_id') not in seen]
            print(f"ℹ️ Skipped {before - len(tasks)} tasks already in {os.path.basename(github_file)}")
        except Exception as e:
            print(f"⚠️ Failed to read GitHub versions file: {e}")

    for t in tasks:
        if not {"repo", "base_commit", "instance_id"}.issubset(t):
            print(f"Invalid task format: {t}")
            return


    cache_dir = os.path.join(args.testbed, "_cache")
    repo_cache = prepare_repo_cache(tasks, cache_dir)
    results = process_repos(tasks, args.testbed, repo_cache, args.max_workers)

    tmp = generate_output_path(args.instance_path, "_versions_by_git")
    if args.output_dir:
        output_path = os.path.join(args.output_dir, os.path.basename(tmp))
    else:
        output_path = tmp

    save_results(results, output_path)
    print(f"\n✅ {len(results)} results saved to {output_path}")

if __name__ == "__main__":
    main()
