#!/usr/bin/env python3
"""Download, verify, and optionally deploy an NW-API GitHub Release package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
ASSET_NAME_RE = re.compile(r"^[A-Za-z0-9._+-]+$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def github_json(path: str, token: str | None = None) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "nw-api-release-updater"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def download_url(url: str, dest: Path, token: str | None = None) -> None:
    headers = {"User-Agent": "nw-api-release-updater"}
    if "api.github.com" in url:
        headers["Accept"] = "application/octet-stream"
        if token:
            headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)


def release_assets(repo: str, tag: str, token: str | None = None) -> dict[str, dict]:
    rel = github_json(f"/repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe='')}", token)
    if not isinstance(rel, dict):
        raise RuntimeError("unexpected GitHub release response")
    out = {}
    for asset in rel.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name"):
            out[str(asset["name"])] = asset
    return out


def parse_checksums(path: Path) -> dict[str, str]:
    checks = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            checks[parts[-1]] = parts[0].lower()
    return checks


def safe_extract_manifest(asset: Path, dest: Path) -> dict:
    with tarfile.open(asset, "r:gz") as tar:
        names = tar.getnames()
        bad = [n for n in names if n.startswith("/") or ".." in Path(n).parts]
        if bad:
            raise RuntimeError("unsafe paths in archive: " + ", ".join(bad[:5]))
        manifest_members = [n for n in names if n.endswith("/manifest.json")]
        sha_members = [n for n in names if n.endswith("/manifest.sha256")]
        if not manifest_members or not sha_members:
            raise RuntimeError("manifest.json or manifest.sha256 missing")
        manifest = json.loads(tar.extractfile(manifest_members[0]).read().decode("utf-8"))  # type: ignore[union-attr]
        tar.extractall(dest)
    return manifest


def run_deploy(command_template: str, asset: Path) -> int:
    cmd = command_template.replace("{asset}", str(asset))
    print("deploy_command=" + cmd)
    p = subprocess.run(["bash", "-lc", cmd], text=True)
    return p.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Download and verify NW-API release asset")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--asset", required=True)
    ap.add_argument("--checksum-asset", default="checksums.txt")
    ap.add_argument("--dest", type=Path, default=Path("/tmp/nw-api-release-updates"))
    ap.add_argument("--deploy-command", default="")
    ap.add_argument("--run-deploy", action="store_true")
    ap.add_argument("--print-manifest", action="store_true")
    args = ap.parse_args()

    if not ASSET_NAME_RE.fullmatch(args.asset) or not ASSET_NAME_RE.fullmatch(args.checksum_asset):
        raise SystemExit("unsafe asset name")

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    assets = release_assets(args.repo, args.tag, token)
    if args.asset not in assets:
        raise SystemExit(f"asset not found: {args.asset}")
    if args.checksum_asset not in assets:
        raise SystemExit(f"checksum asset not found: {args.checksum_asset}")

    work = args.dest / args.tag
    work.mkdir(parents=True, exist_ok=True)
    asset_path = work / args.asset
    checks_path = work / args.checksum_asset

    download_url(assets[args.asset]["url"], asset_path, token)
    download_url(assets[args.checksum_asset]["url"], checks_path, token)

    checks = parse_checksums(checks_path)
    expected = checks.get(args.asset)
    actual = sha256_file(asset_path)
    if not expected:
        raise SystemExit(f"checksum missing for {args.asset}")
    if actual != expected:
        raise SystemExit(f"checksum mismatch: expected {expected}, got {actual}")

    with tempfile.TemporaryDirectory() as td:
        manifest = safe_extract_manifest(asset_path, Path(td))
    if manifest.get("version") != args.tag:
        raise SystemExit(f"manifest version mismatch: {manifest.get('version')} != {args.tag}")
    if args.print_manifest:
        print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    print(f"verified {args.asset} sha256={actual}")

    if args.run_deploy:
        if not args.deploy_command:
            raise SystemExit("--deploy-command required with --run-deploy")
        rc = run_deploy(args.deploy_command, asset_path)
        if rc != 0:
            raise SystemExit(rc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
