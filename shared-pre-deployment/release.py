"""
Release gate workflow script for shared-pre-deployment.
Enforces strict test-before-build and test-before-publish ordering.

Execution Steps:
1. Run pytest test suite. Stop immediately on test failure.
2. Clean old distribution artifacts in dist/.
3. Build wheel (.whl) and source distribution (.tar.gz) using uv build.
4. Inspect and verify generated distribution artifacts.
5. Publish to PyPI (if --publish is passed) using uv publish.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def log_step(step_num: int, title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"   [RELEASE GATE STEP {step_num}] {title}")
    print(f"{'=' * 65}\n")


def run_tests() -> bool:
    """Step 1: Execute package test suite. Fails fast if any test fails."""
    log_step(1, "Running package test suite (pytest)")
    cmd = ["uv", "run", "pytest", "-v"]
    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=PACKAGE_DIR)
    if res.returncode != 0:
        print(
            f"\n[RELEASE GATE BLOCKED] Tests failed with exit code {res.returncode}. "
            "Build and publish aborted.",
            file=sys.stderr,
        )
        return False
    print("\n[RELEASE GATE PASS] All tests passed.")
    return True


def build_artifacts() -> bool:
    """Step 2 & 3: Clean dist/ and build wheel & sdist."""
    log_step(2, "Building wheel and source distributions (uv build)")
    dist_dir = PACKAGE_DIR / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    cmd = ["uv", "build"]
    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=PACKAGE_DIR)
    if res.returncode != 0:
        print(f"\n[RELEASE GATE BLOCKED] Build failed with exit code {res.returncode}.", file=sys.stderr)
        return False
    print("\n[RELEASE GATE PASS] Build completed successfully.")
    return True


def verify_artifacts() -> bool:
    """Step 4: Inspect artifacts in dist/ to verify wheel and sdist integrity."""
    log_step(3, "Inspecting and verifying built distribution artifacts")
    dist_dir = PACKAGE_DIR / "dist"
    if not dist_dir.exists():
        print("[FAIL] dist/ directory not found.", file=sys.stderr)
        return False

    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))

    if not wheels:
        print("[FAIL] No wheel (.whl) artifact found in dist/.", file=sys.stderr)
        return False
    if not sdists:
        print("[FAIL] No source distribution (.tar.gz) artifact found in dist/.", file=sys.stderr)
        return False

    whl = wheels[0]
    sdist = sdists[0]

    print(f"[FOUND] Wheel: {whl.name} ({whl.stat().st_size} bytes)")
    print(f"[FOUND] Source Distribution: {sdist.name} ({sdist.stat().st_size} bytes)")

    # Verify wheel contents
    with zipfile.ZipFile(whl, "r") as z:
        names = z.namelist()
        required_whl_files = [
            "shared_pre_deployment/__init__.py",
            "shared_pre_deployment/runner.py",
            "shared_pre_deployment/cli.py",
            "shared_pre_deployment/validators.py",
            "shared_pre_deployment/exceptions.py",
        ]
        for req in required_whl_files:
            if not any(req in n for n in names):
                print(f"[FAIL] Missing {req} in wheel archive.", file=sys.stderr)
                return False
        print(f"[PASS] Wheel archive verified ({len(names)} entries).")

    # Verify sdist contents
    with tarfile.open(sdist, "r:gz") as t:
        sdist_names = t.getnames()
        if not any("pyproject.toml" in n for n in sdist_names):
            print("[FAIL] Missing pyproject.toml in source distribution archive.", file=sys.stderr)
            return False
        print(f"[PASS] Source distribution archive verified ({len(sdist_names)} entries).")

    return True


def publish_artifacts() -> bool:
    """Step 5: Publish distribution artifacts to PyPI."""
    log_step(4, "Publishing artifacts to PyPI (uv publish)")
    token = os.environ.get("UV_PUBLISH_TOKEN")
    if not token:
        print(
            "[ERROR] UV_PUBLISH_TOKEN environment variable is not set. Cannot publish.",
            file=sys.stderr,
        )
        return False

    cmd = ["uv", "publish"]
    print("Executing: uv publish [token masked]")
    res = subprocess.run(cmd, cwd=PACKAGE_DIR)
    if res.returncode != 0:
        print(f"\n[FAIL] uv publish failed with exit code {res.returncode}.", file=sys.stderr)
        return False
    print("\n[SUCCESS] Successfully published to PyPI!")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Release gate workflow for shared-pre-deployment.")
    parser.add_argument("--publish", action="store_true", help="Publish to PyPI after successful test and build.")
    args = parser.parse_args()

    # 1. Test Gate
    if not run_tests():
        sys.exit(1)

    # 2. Build Gate
    if not build_artifacts():
        sys.exit(1)

    # 3. Verification Gate
    if not verify_artifacts():
        sys.exit(1)

    # 4. Optional Publish Gate
    if args.publish:
        if not publish_artifacts():
            sys.exit(1)
    else:
        print(
            "\n[GATE PASS] Build and verification complete. "
            "Artifacts are verified and ready for publication (pass --publish to upload)."
        )


if __name__ == "__main__":
    main()
