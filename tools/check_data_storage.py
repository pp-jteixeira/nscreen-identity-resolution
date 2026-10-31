#!/usr/bin/env python3
"""Reject stored query/debug datasets and notebook outputs, locally or in Git's index."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '.venv', 'venv', 'env', 'node_modules', '__pycache__', '.cache', 'forge', 'aggr3'}
DATA_SUFFIXES = {'.csv', '.tsv', '.parquet', '.feather', '.arrow', '.xlsx', '.xls', '.db', '.duckdb',
                 '.sqlite', '.sqlite3', '.pkl', '.pickle', '.jsonl', '.ndjson'}
RESULT_DIRS = {'results', 'runs', 'output', 'outputs', 'logs', 'evidence', 'research', 'review', 'target', 'validation'}


def problem(path, content=None):
    p = Path(path)
    if p.name == 'nicknames.csv' and p.parent.name == 'seeds':
        return None  # Versioned reference vocabulary, never a warehouse extract.
    if (p.suffix.lower() in DATA_SUFFIXES or
            any(str(p).endswith(ext + tail) for ext in DATA_SUFFIXES
                for tail in ('.gz', '.bz2', '.zst', '.tmp', '.partial', '.wal'))):
        return 'dataset/export file'
    if RESULT_DIRS.intersection(p.parts) and p.suffix.lower() in {'.json', '.txt', '.log', '.html'}:
        return 'saved query/debug result'
    if p.suffix == '.ipynb' and content is not None:
        try:
            notebook = json.loads(content)
        except (ValueError, UnicodeDecodeError):
            return 'invalid notebook'
        if notebook.get('metadata', {}).get('widgets') or any(
                cell.get('outputs') or cell.get('attachments') or cell.get('execution_count') is not None
                for cell in notebook.get('cells', [])):
            return 'notebook output, attachment, widget state, or execution count'
    return None


def check_staged():
    names = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'], cwd=ROOT)
    for path in filter(None, names.decode().split('\0')):
        content = subprocess.check_output(['git', 'show', ':' + path], cwd=ROOT) if path.endswith('.ipynb') else None
        issue = problem(path, content)
        if issue:
            yield path, issue


def check_local():
    for directory, children, files in os.walk(ROOT, followlinks=False):
        children[:] = [name for name in children if name not in SKIP]
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            relative = str(path.relative_to(ROOT))
            content = path.read_bytes() if path.suffix == '.ipynb' else None
            issue = problem(relative, content)
            if issue:
                yield relative, issue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', help='Check staged versions, including ignored force-added files')
    args = parser.parse_args()
    issues = list(check_staged() if args.staged else check_local())
    for path, issue in issues:
        print(f'{path}: {issue}')
    print(f'Data storage check: {len(issues)} prohibited artifacts')
    return bool(issues)


if __name__ == '__main__':
    raise SystemExit(main())
