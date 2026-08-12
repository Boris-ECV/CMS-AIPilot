"""Fixtures for the frontend e2e suite (SDLCAIP1-18).

These tests drive the actual built admin frontend (Vite + React) in a real
browser via Playwright, served by `vite preview` against the production
build artifact (`frontend/dist`) — not a placeholder.

The `POST /login` network call is intercepted at the browser network layer
(Playwright `page.route`) rather than hitting a live backend server. This
mirrors the project's existing test split (see `project-profile.yaml`
`conventions.notes`): the `/login` request/response *contract* (200/401/429
shapes, lockout semantics, JWT claims, etc.) is already exhaustively covered
against the real FastAPI app in `tests/test_login.py` via
`pytest + httpx/TestClient`. This e2e suite's job is to verify the frontend's
own behavior end-to-end in a real browser — building/serving the real bundle,
real `fetch` calls with real headers, real `localStorage`, real
`react-router` navigation — not to re-verify the backend contract, and not to
stand up a second, parallel mock of the backend's DynamoDB/SSM dependencies
just to get a live server running for the browser to call.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend"
PREVIEW_PORT = 4173
PREVIEW_BASE_URL = f"http://127.0.0.1:{PREVIEW_PORT}"


def _npm_cmd() -> str:
    # On Windows, npm is a .cmd shim; shutil.which finds the right one.
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm not found on PATH")
    return npm


def _vite_bin() -> Path:
    # Invoke the vite binary directly (not via `npm run preview`) so the
    # fixture owns a single process it can reliably terminate. `npm run`
    # spawns vite as a grandchild of an intermediate npm-cli process on
    # Windows; terminating the npm process alone leaves the actual vite
    # server orphaned and still holding the port.
    suffix = ".cmd" if shutil.os.name == "nt" else ""
    vite_bin = FRONTEND_DIR / "node_modules" / ".bin" / f"vite{suffix}"
    if not vite_bin.exists():
        raise RuntimeError(f"vite binary not found at {vite_bin} — run npm install first")
    return vite_bin


def _wait_for_port(host: str, port: int, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error: OSError | None = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.2)
    raise TimeoutError(f"{host}:{port} did not become reachable in time") from last_error


@pytest.fixture(scope="session")
def frontend_preview_server() -> Iterator[str]:
    """Build the frontend (if needed) and serve it via `vite preview`."""
    npm = _npm_cmd()
    dist_dir = FRONTEND_DIR / "dist"
    if not dist_dir.exists():
        subprocess.run([npm, "run", "build"], cwd=FRONTEND_DIR, check=True, shell=False)

    process = subprocess.Popen(
        [
            str(_vite_bin()),
            "preview",
            "--host",
            "127.0.0.1",
            "--port",
            str(PREVIEW_PORT),
            "--strictPort",
        ],
        cwd=FRONTEND_DIR,
        shell=False,
    )
    try:
        _wait_for_port("127.0.0.1", PREVIEW_PORT, timeout_seconds=30)
        yield PREVIEW_BASE_URL
    finally:
        _terminate_process_tree(process)


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Terminate `process` and any descendants it spawned.

    On Windows, `vite.cmd` is itself a batch-file shim that Python launches
    via an intermediate `cmd.exe`, which in turn spawns the real `node.exe`
    process actually listening on the port. `Popen.terminate()` only signals
    the immediate child (`cmd.exe`), leaving the real server orphaned and
    still holding the port — so use `taskkill /T /F` to kill the whole tree.
    """
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        process.wait(timeout=10)
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
