#!/usr/bin/env python3
"""Build a deterministic NW-API release package for preview/binary-update migration."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST = ROOT / "dist"

PACKAGE_FILES = [
    "services/xapi-portal/xapi_portal.py",
    "services/xapi-portal/sync_model_prices.py",
    "services/xapi-data/xapi_data_api.py",
    "services/xapi-v1-wrapper/xapi_v1_wrapper.py",
    "services/xapi-v1-wrapper/gateway_core.py",
    "services/xapi-v1-wrapper/provider_adapter.py",
    "services/xapi-v1-wrapper/usage_wallet.py",
    "services/xapi-v1-wrapper/README.md",
    "services/hermes-portal/index.html",
    "services/dh-nav/index.html",
    "systemd/xapi-portal.service",
    "systemd/xapi-data.service",
    "systemd/xapi-v1-wrapper.service",
    "systemd/xapi-portal.env.example",
    "systemd/Caddyfile.current",
    "scripts/deploy-aliyun.sh",
    "scripts/deploy-sub2api-host.sh",
    "scripts/bootstrap-working-copy.sh",
    "README.md",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def version_from_source() -> str:
    src = (ROOT / "services/xapi-portal/xapi_portal.py").read_text(encoding="utf-8")
    match = re.search(r"APP_VERSION='([^']+)'", src)
    if not match:
        raise SystemExit("APP_VERSION not found in services/xapi-portal/xapi_portal.py")
    return match.group(1)


def validate_version(version: str) -> str:
    pattern = r"V\d+\.\d+\.\d+(?:\.\d+)?(?:-rc\.\d+)?"
    if not re.fullmatch(pattern, version):
        raise SystemExit(
            "Unsupported version string: "
            f"{version}. Expected V0.0.X, V0.0.X.Y, or V0.0.X-rc.N"
        )
    return version


def add_record(records: list[dict[str, object]], rel: str, data: bytes) -> None:
    digest = hashlib.sha256(data).hexdigest()
    records.append({"path": rel, "size": len(data), "sha256": digest})


def copy_package_tree(package_root: Path, binary: Path | None = None, package_version: str | None = None) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for rel in PACKAGE_FILES:
        src = ROOT / rel
        if not src.is_file():
            raise SystemExit(f"Required package file missing: {rel}")
        dst = package_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        if package_version and rel == "services/xapi-portal/xapi_portal.py":
            text = data.decode("utf-8")
            text = re.sub(r"APP_VERSION='[^']+'", f"APP_VERSION='{package_version}'", text, count=1)
            data = text.encode("utf-8")
        dst.write_bytes(data)
        add_record(records, rel, data)
    if binary is not None:
        if not binary.is_file():
            raise SystemExit(f"Binary asset not found: {binary}")
        rel = "bin/nw-api-preview"
        dst = package_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = binary.read_bytes()
        dst.write_bytes(data)
        dst.chmod(0o755)
        add_record(records, rel, data)
    return records


def write_manifests(package_root: Path, version: str, records: list[dict[str, object]], binary: bool) -> None:
    (package_root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    version_sha = sha256_file(package_root / "VERSION")
    all_records = [{"path": "VERSION", "size": (package_root / "VERSION").stat().st_size, "sha256": version_sha}, *records]

    manifest_json = {
        "name": "nw-api",
        "version": version,
        "platform": "linux-amd64",
        "git_commit": git_commit(),
        "package_format": 2 if binary else 1,
        "runtime": "binary-preview" if binary else "python-preview",
        "files": all_records,
    }
    (package_root / "manifest.json").write_text(
        json.dumps(manifest_json, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_json_sha = sha256_file(package_root / "manifest.json")
    all_records.append({
        "path": "manifest.json",
        "size": (package_root / "manifest.json").stat().st_size,
        "sha256": manifest_json_sha,
    })
    manifest_lines = [f"{r['sha256']}  {r['path']}" for r in sorted(all_records, key=lambda item: str(item["path"]))]
    (package_root / "manifest.sha256").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")


def add_tree(tar: tarfile.TarFile, package_root: Path, arc_root: str) -> None:
    for path in sorted(package_root.rglob("*")):
        rel = path.relative_to(package_root)
        arcname = f"{arc_root}/{rel.as_posix()}"
        info = tar.gettarinfo(str(path), arcname=arcname)
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        info.mtime = 0
        if path.is_file():
            info.mode = 0o755 if rel.as_posix().startswith(("scripts/", "bin/")) else 0o644
            with path.open("rb") as handle:
                tar.addfile(info, handle)
        elif path.is_dir():
            info.mode = 0o755
            tar.addfile(info)


def build(version: str, dist: Path, binary: Path | None = None, set_app_version: bool = False) -> Path:
    version = validate_version(version)
    dist.mkdir(parents=True, exist_ok=True)
    asset_name = f"nw-api-{version}-linux-amd64.tar.gz"
    asset = dist / asset_name
    arc_root = f"nw-api-{version}-linux-amd64"

    with tempfile.TemporaryDirectory() as tmp:
        package_root = Path(tmp) / arc_root
        package_root.mkdir()
        records = copy_package_tree(package_root, binary=binary, package_version=version if set_app_version else None)
        write_manifests(package_root, version, records, binary=binary is not None)
        with asset.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                add_tree(tar, package_root, arc_root)

    checksum = sha256_file(asset)
    (dist / "checksums.txt").write_text(f"{checksum}  {asset_name}\n", encoding="utf-8")
    (dist / f"{asset_name}.sha256").write_text(f"{checksum}  {asset_name}\n", encoding="utf-8")
    # Copy package manifest next to the asset for GitHub Release inspection.
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(asset, "r:gz") as tar:
            member = tar.getmember(f"{arc_root}/manifest.json")
            manifest_bytes = tar.extractfile(member).read()  # type: ignore[union-attr]
        (dist / "manifest.json").write_bytes(manifest_bytes)
    print(asset)
    print(f"sha256={checksum}")
    return asset


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NW-API linux-amd64 release package")
    parser.add_argument("--version", default=version_from_source(), help="Release version; defaults to APP_VERSION")
    parser.add_argument("--dist", type=Path, default=DEFAULT_DIST, help="Output directory")
    parser.add_argument("--binary", type=Path, help="Optional built preview binary to include as bin/nw-api-preview")
    parser.add_argument("--set-app-version", action="store_true", help="Rewrite APP_VERSION in packaged portal only")
    args = parser.parse_args()
    build(args.version, args.dist, binary=args.binary, set_app_version=args.set_app_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
