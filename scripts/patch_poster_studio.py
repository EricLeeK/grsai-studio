#!/usr/bin/env python3
"""Apply grsai-studio integration patches to the vendored poster-studio app.

Snapshot-based: the final working versions of the modified poster-studio files
live under scripts/poster-studio-overrides/snapshots/ (and the two NEW
components next to this script). This script copies them over a fresh clone and
deletes the removed-feature files, so a fresh checkout reproduces the exact
customized app.

What this encodes (relative to upstream poster-studio):
  * GRS AI 图库 tab in the image picker (paginated 4×5, reads /api/poster/library);
  * Dark mode (ThemeToggle), canvas viewport dark-aware (paper stays white);
  * Topbar: removed Share + hamburger menu (replaced by ThemeToggle);
  * Image picker: removed 网络搜图 + 共享素材 tabs;
  * Removed features (routes + libs + components + dead code + deps):
      网络搜图 (Unsplash), 共享素材 (materials), 分享 (share), 去背景 (remove-bg,
      incl. @imgly/background-removal);
  * Uploads retargeted from Qiniu to FastAPI /api/poster/upload.

Templates (模板) + lib/server/public-store.ts are intentionally KEPT (templates is
a separate, retained feature).

NOTE: snapshots are pinned to a specific poster-studio revision. To upgrade
poster-studio, re-derive the snapshots from the new version after re-applying
the customizations.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PS_DIR = ROOT / "poster-studio"
OVERRIDE_DIR = ROOT / "scripts" / "poster-studio-overrides"
SNAPSHOT_DIR = OVERRIDE_DIR / "snapshots"

# New component files (do not exist upstream) -> app/components/home/
NEW_COMPONENTS = ["GrsImageLibrary.tsx", "ThemeToggle.tsx"]

# Feature files to delete entirely (routes/libs/components of removed features).
REMOVED_FEATURE_PATHS = [
    "app/api/unsplash",
    "app/api/materials",
    "app/api/share",
    "app/share",
    "app/api/remove-bg",
    "lib/unsplash-api.ts",
    "app/components/ShareDialog.tsx",
    "app/components/home/ShareMaterialDialog.tsx",
]


def fail(message: str) -> None:
    print(f"❌ {message}", file=sys.stderr)
    sys.exit(1)


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def apply_overrides() -> None:
    if not PS_DIR.exists():
        fail("poster-studio/ not found — run setup-poster-studio.sh first")

    # New component files.
    for name in NEW_COMPONENTS:
        src = OVERRIDE_DIR / name
        if not src.exists():
            fail(f"override source missing: {src}")
        _copy(src, PS_DIR / "app" / "components" / "home" / name)
        print(f"📋 override: app/components/home/{name}")

    # Snapshot files (final working versions of modified existing files).
    if not SNAPSHOT_DIR.exists():
        fail(f"snapshot dir missing: {SNAPSHOT_DIR}")
    copied = 0
    for path in sorted(SNAPSHOT_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(SNAPSHOT_DIR)
        _copy(path, PS_DIR / rel)
        copied += 1
    print(f"🖼️  applied {copied} snapshot file(s)")


def delete_removed_features() -> None:
    for rel in REMOVED_FEATURE_PATHS:
        target = PS_DIR / rel
        if target.is_dir():
            shutil.rmtree(target)
            print(f"🗑️  removed dir  {rel}")
        elif target.is_file():
            target.unlink()
            print(f"🗑️  removed file {rel}")


def main() -> None:
    apply_overrides()
    delete_removed_features()
    print("✅ poster-studio patches applied")


if __name__ == "__main__":
    main()
