"""Build reviewed VEYRIS source into an Ed25519-signed GitHub release.

Signing key is supplied only through the VEYRIS_SIGNING_KEY_B64 environment
variable and is never stored by this script.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
FILES = ("server.py", "brain.py", "app.js", "index.html", "style.css")
DIST = ROOT / "release_dist"


def main():
    secret = os.environ.get("VEYRIS_SIGNING_KEY_B64", "")
    if not secret:
        raise RuntimeError("Missing VEYRIS_SIGNING_KEY_B64: signing disabled")
    raw = base64.b64decode(secret, validate=True)
    if len(raw) != 32:
        raise RuntimeError("Signing key must be 32 bytes")
    key = Ed25519PrivateKey.from_private_bytes(raw)
    source = (ROOT / "server.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', source, re.M)
    if not match:
        raise RuntimeError("Application version missing")
    version = match.group(1)
    # Manual workflow dispatch uses the main branch as GITHUB_REF_NAME.
    # Validate the requested tag instead of treating that branch as the release tag.
    ci_tag = os.environ.get("VEYRIS_RELEASE_TAG") or (
        os.environ.get("GITHUB_REF_NAME") if os.environ.get("GITHUB_REF_TYPE") == "tag" else None
    )
    if ci_tag != f"v{version}":
        raise RuntimeError("Requested release tag and application version disagree")

    buffer = io.BytesIO()
    hashes = {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            data = (ROOT / name).read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            info = zipfile.ZipInfo(filename=name, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    archive = buffer.getvalue()
    manifest = {
        "schema": 1, "version": version,
        "package_sha256": hashlib.sha256(archive).hexdigest(),
        "files": hashes
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = key.sign(manifest_bytes)
    DIST.mkdir(exist_ok=True)
    (DIST / "veyris-release.zip").write_bytes(archive)
    (DIST / "veyris-manifest.json").write_bytes(manifest_bytes)
    (DIST / "veyris-manifest.sig").write_bytes(signature)
    print(f"Built signed VEYRIS v{version}; signing key never written.")


if __name__ == "__main__":
    main()
