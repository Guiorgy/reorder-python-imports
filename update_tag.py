#!/usr/bin/env python

from __future__ import annotations

import re
import subprocess
import sys
from typing import Literal
from typing import overload

UPSTREAM_REMOTE_NAME = 'base'
UPSTREAM_REMOTE_URL = 'https://github.com/asottile/reorder-python-imports.git'


@overload
def run_git(args: list[str]) -> str: ...


@overload
def run_git(args: list[str], may_fail: Literal[False]) -> str: ...


@overload
def run_git(args: list[str], may_fail: Literal[True]) -> str | None: ...


def run_git(args: list[str], may_fail: bool = False) -> str | None:
    """Executes a git command and returns the stdout"""
    try:
        result = subprocess.run(
            ['git'] + args,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if may_fail:
            return None

        print(f"Git Error: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def setup_remote_if_missing() -> None:
    """Checks whether the remote exists, and adds it if it does not"""
    remotes = run_git(['remote']).splitlines()
    if UPSTREAM_REMOTE_NAME not in remotes:
        print(
            f'Remote "{UPSTREAM_REMOTE_NAME}" not found,'
            f' adding {UPSTREAM_REMOTE_URL}',
        )
        run_git(['remote', 'add', UPSTREAM_REMOTE_NAME, UPSTREAM_REMOTE_URL])
    # Update URL in case it changed
    # else:
    #     run_git([
    #         'remote',
    #         'set-url',
    #         UPSTREAM_REMOTE_NAME,
    #         UPSTREAM_REMOTE_URL,
    #     ])


def get_latest_upstream_tag() -> str:
    """Fetches upstream and finds the most recent tag reachable from main"""
    run_git(['fetch', UPSTREAM_REMOTE_NAME, '--tags'])
    return run_git(
        [
            'describe',
            '--tags',
            '--abbrev=0',
            f'{UPSTREAM_REMOTE_NAME}/main',
        ],
    )


def get_head_tags() -> list[str]:
    """Returns a list of tags pointing to current HEAD"""
    result = run_git(['tag', '--points-at', 'HEAD'], True)
    return result.splitlines() if result else []


def get_head_hash() -> str:
    """Returns the commit hash of the current HEAD"""
    return run_git(['rev-parse', 'HEAD'])


def tag_head(tag: str) -> None:
    """Tags HEAD"""
    run_git(['tag', tag])


def is_ancestor_of_head(hash: str) -> bool:
    """Checks whether the specified hash is an ancestor of HEAD"""
    result = run_git(['merge-base', '--is-ancestor', hash, 'HEAD'], True)
    return result is not None


def get_tag_commit_hash(tag: str) -> str:
    """Returns the commit hash for a specific tag"""
    return run_git(['rev-list', '-n', '1', tag])


def does_tag_exist(tag: str) -> bool:
    """Checks whether the given tag exists"""
    return tag in run_git(['tag', '--list', tag])


def remove_tags(tag_pattenr: str) -> None:
    """Removes the specified tag(s)"""
    tags = run_git(['tag', '--list', tag_pattenr]).splitlines()
    for tag in tags:
        run_git(['tag', '-d', tag])


def get_highest_patch_suffix(base_tag: str) -> int:
    """Finds the highest -p* suffix for a specific tag in the local repo"""
    tags = run_git(['tag', '--list', f'{base_tag}-p*']).splitlines()

    max_patch = 0
    for tag in tags:
        match = re.search(r'-p(\d+)$', tag)
        if match:
            max_patch = max(max_patch, int(match.group(1)))

    return max_patch


def rebase(hash: str) -> None:
    """Rebases the local repo to the specified remote hash"""
    run_git(['rebase', '--onto', hash, f'{UPSTREAM_REMOTE_NAME}/main'])


def sync_and_patch() -> None:
    setup_remote_if_missing()

    print('Fetching from upstream')
    run_git(['fetch', UPSTREAM_REMOTE_NAME])

    latest_tag = get_latest_upstream_tag()
    latest_tag_hash = get_tag_commit_hash(latest_tag)
    print(f'Latest upstream version found: {latest_tag} ({latest_tag_hash})')

    head_tags = get_head_tags()
    for tag in head_tags:
        if tag.startswith(f"{latest_tag}-p"):
            print(f'Current HEAD is already up-to-date with {tag}')
            return

    head_hash = get_head_hash()
    if head_hash == latest_tag_hash:
        print(f'No local patches found relative to {latest_tag_hash}!')
        sys.exit(1)

    if is_ancestor_of_head(latest_tag_hash):
        last_patch = get_highest_patch_suffix(latest_tag)
        new_tag = f'{latest_tag}-p{last_patch + 1}'
        print(
            f'New local patches detected on {latest_tag},'
            ' incrementing to {new_tag}',
        )
    else:
        print(f'New upstream tag {latest_tag} found, rebasing')
        remove_tags('*-p*')

        run_git([
            'rebase',
            '--onto',
            latest_tag_hash,
            f'{UPSTREAM_REMOTE_NAME}/main',
        ])
        new_tag = f'{latest_tag}-p1'

    tag_head(new_tag)
    print(f'Successfully updated to: {new_tag}')
    print(
        'Run '
        '"git push origin main --force && git push origin --tags --prune"'
        ' when ready',
    )


if __name__ == '__main__':
    sync_and_patch()
