"""Remote builder long-job management.

Replaces the old heartbeat-only monitoring pattern in ``image.py``.  Instead of
checking whether a ``pid`` is alive, each remote job writes structured state:

    <remote_root>/.fleet/jobs/<job_id>/
      state            — ``running`` / ``succeeded`` / ``failed``
      exit-code        — raw exit code
      started-at       — ISO timestamp
      finished-at      — ISO timestamp (empty while running)
      stdout.log       — captured stdout
      stderr.log       — captured stderr
      artifact-path    — path to the expected artifact (if any)
      artifact-size    — byte size of artifact (if verified)
      artifact-sha256  — sha256 of artifact (if verified)

The local side polls the ``state`` file and optionally verifies the artifact.
If the SSH connection drops, the job keeps running (``nohup``) and we can
reconnect to poll again.
"""

from __future__ import annotations

import shlex
import sys
import time
from dataclasses import dataclass
from typing import Literal

from builder import ssh_args
from common import capture, die


JobState = Literal["running", "succeeded", "failed", "canceled"]


@dataclass
class RemoteJobStatus:
    job_id: str
    state: JobState
    exit_code: int | None
    started_at: str
    finished_at: str | None
    artifact_path: str | None = None
    artifact_size: int | None = None
    artifact_sha256: str | None = None

    @property
    def done(self) -> bool:
        return self.state in ("succeeded", "failed")

    @property
    def succeeded(self) -> bool:
        return self.state == "succeeded"


# ---------------------------------------------------------------------------
# Job directory helpers
# ---------------------------------------------------------------------------


def job_remote_dir(builder: dict, job_id: str) -> str:
    """Return the remote path for *job_id*."""
    return f"{builder['remote_root']}/.fleet/jobs/{job_id}"


def make_job_id(command: str, target: str) -> str:
    """Generate a deterministic-ish job id."""
    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    safe_target = "".join(c if c.isalnum() or c in "-_." else "-" for c in target)
    return f"{command}-{safe_target}-{ts}"


# ---------------------------------------------------------------------------
# Remote runner script generation
# ---------------------------------------------------------------------------


def _remote_runner_script(job_dir: str, inner_script: str, artifact_path: str | None) -> str:
    """Generate the bash wrapper that runs *inner_script* and writes status files.

    Uses ``set -euo pipefail`` so pipeline failures are not masked by ``tee``.
    Writes individual files (not JSON) for robustness.
    """
    artifact_check = ""
    if artifact_path:
        artifact_check = f"""
if [ -s {shlex.quote(artifact_path)} ]; then
  stat -c %s {shlex.quote(artifact_path)} > "$job_dir/artifact-size" 2>/dev/null || true
  sha256sum {shlex.quote(artifact_path)} 2>/dev/null | awk '{{print $1}}' > "$job_dir/artifact-sha256" || true
fi
"""

    return f"""set -euo pipefail
job_dir={shlex.quote(job_dir)}
mkdir -p "$job_dir"
echo $$ > "$job_dir/pid"
echo $$ > "$job_dir/pgid"
date -u +%FT%TZ > "$job_dir/started-at"
printf '%s' 'running' > "$job_dir/state"

set +e
(
  set -euo pipefail
  cd "$job_dir"
  {inner_script}
) > "$job_dir/stdout.log" 2> "$job_dir/stderr.log"
exit_code=$?
set -e

echo "$exit_code" > "$job_dir/exit-code"
date -u +%FT%TZ > "$job_dir/finished-at"
if [ -n {shlex.quote(artifact_path or '')} ]; then
  printf '%s' {shlex.quote(artifact_path or '')} > "$job_dir/artifact-path"
fi
{artifact_check}
if [ "$exit_code" -eq 0 ]; then
  printf '%s' 'succeeded' > "$job_dir/state"
else
  printf '%s' 'failed' > "$job_dir/state"
fi
exit "$exit_code"
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_remote_job(builder: dict, job_id: str, inner_script: str, *, artifact_path: str | None = None) -> str:
    """Launch *inner_script* as a backgrounded job on the builder.

    Returns the remote job directory path.  The job runs under ``setsid`` so it
    survives SSH disconnects and can be killed by process group.
    """
    job_dir = job_remote_dir(builder, job_id)
    runner = _remote_runner_script(job_dir, inner_script, artifact_path)

    # Launch via setsid (new session = own process group).
    # The runner writes its own PID to $job_dir/pid; we wait for that file.
    launch_script = (
        f"setsid bash -c {shlex.quote(runner)} </dev/null >/dev/null 2>&1 & "
        f"for i in $(seq 1 10); do [ -f {shlex.quote(job_dir + '/pid')} ] && break; sleep 0.1; done; "
        f"cat {shlex.quote(job_dir + '/pid')} 2>/dev/null || echo unknown"
    )
    pid = capture([*ssh_args(builder), launch_script]).strip()
    print(f"[fleet] remote job '{job_id}' started on builder (pid={pid})", file=sys.stderr)
    print(f"[fleet] job dir: {job_dir}", file=sys.stderr)
    return job_dir


def _read_remote_file(builder: dict, path: str, default: str = "") -> str:
    """Read a small remote file, returning *default* on any error."""
    try:
        return capture([*ssh_args(builder), f"cat {shlex.quote(path)} 2>/dev/null || true"]).strip()
    except Exception:
        return default


def poll_remote_job(builder: dict, job_id: str) -> RemoteJobStatus:
    """Read the current status of *job_id* from the builder."""
    job_dir = job_remote_dir(builder, job_id)
    state = _read_remote_file(builder, f"{job_dir}/state", "running")
    if not state:
        state = "running"

    exit_code_raw = _read_remote_file(builder, f"{job_dir}/exit-code", "")
    exit_code = int(exit_code_raw) if exit_code_raw.lstrip("-").isdigit() else None

    started_at = _read_remote_file(builder, f"{job_dir}/started-at", "")
    finished_at_raw = _read_remote_file(builder, f"{job_dir}/finished-at", "")
    finished_at = finished_at_raw if finished_at_raw else None

    artifact_path_raw = _read_remote_file(builder, f"{job_dir}/artifact-path", "")
    artifact_path = artifact_path_raw if artifact_path_raw else None

    artifact_size_raw = _read_remote_file(builder, f"{job_dir}/artifact-size", "")
    artifact_size = int(artifact_size_raw) if artifact_size_raw.isdigit() else None

    artifact_sha = _read_remote_file(builder, f"{job_dir}/artifact-sha256", "")
    artifact_sha256 = artifact_sha if artifact_sha else None

    return RemoteJobStatus(
        job_id=job_id,
        state=state,
        exit_code=exit_code,
        started_at=started_at,
        finished_at=finished_at,
        artifact_path=artifact_path,
        artifact_size=artifact_size,
        artifact_sha256=artifact_sha256,
    )


def wait_remote_job(builder: dict, job_id: str, *, poll_interval: int = 30, timeout: int | None = None) -> RemoteJobStatus:
    """Poll *job_id* until it finishes or *timeout* is reached.

    Prints heartbeat-style progress to stderr, but based on structured status
    rather than raw pid checks.
    """
    deadline = time.time() + timeout if timeout else None
    while True:
        status = poll_remote_job(builder, job_id)
        if status.done:
            elapsed_msg = f" (exit_code={status.exit_code})" if status.exit_code is not None else ""
            print(f"[fleet] remote job '{job_id}' {status.state}{elapsed_msg}.", file=sys.stderr)
            if status.artifact_size is not None:
                print(f"[fleet] artifact: {status.artifact_path} ({status.artifact_size} bytes)", file=sys.stderr)
            return status
        print(f"[fleet] remote job '{job_id}' still running ...", file=sys.stderr)
        if deadline and time.time() >= deadline:
            die(f"timed out waiting for remote job '{job_id}'")
        time.sleep(poll_interval)


def fetch_job_log_tail(builder: dict, job_id: str, which: str = "stderr", *, lines: int = 50) -> str:
    """Return the last *lines* of the remote job's stdout or stderr log."""
    if which not in ("stdout", "stderr"):
        die("which must be 'stdout' or 'stderr'")
    job_dir = job_remote_dir(builder, job_id)
    log_path = f"{job_dir}/{which}.log"
    try:
        return capture([*ssh_args(builder), f"tail -n {int(lines)} {shlex.quote(log_path)} 2>/dev/null || true"])
    except Exception:
        return ""


def verify_remote_artifact(builder: dict, artifact_path: str) -> None:
    """Verify that *artifact_path* exists and is non-empty on the builder.

    Dies with a clear message if the artifact is missing or empty.
    """
    check_script = f"""set -eu
test -s {shlex.quote(artifact_path)} || {{ echo "artifact missing or empty: {artifact_path}" >&2; exit 1; }}
size=$(stat -c %s {shlex.quote(artifact_path)})
sha=$(sha256sum {shlex.quote(artifact_path)} | awk '{{print $1}}')
echo "artifact verified: {artifact_path}"
echo "size: $size bytes"
echo "sha256: $sha"
"""
    capture([*ssh_args(builder), check_script])


# ---------------------------------------------------------------------------
# Cancel / list / cleanup
# ---------------------------------------------------------------------------


def cancel_remote_job(builder: dict, job_id: str, *, force: bool = False) -> bool:
    """Terminate a remote job by process group.

    Sends SIGTERM (or SIGKILL if *force*), waits, then marks state as
    ``canceled``.  Returns ``True`` if the job was terminated.
    """
    job_dir = job_remote_dir(builder, job_id)

    pgid_raw = _read_remote_file(builder, f"{job_dir}/pgid", "")
    if not pgid_raw or not pgid_raw.lstrip("-").isdigit():
        print(f"[fleet] no pgid file for job '{job_id}'", file=sys.stderr)
        return False

    sig = "KILL" if force else "TERM"
    capture([*ssh_args(builder), f"kill -{sig} -{pgid_raw} 2>/dev/null || true"])

    if not force:
        time.sleep(3)
        still_running = _read_remote_file(builder, f"{job_dir}/state", "")
        if still_running == "running":
            capture([*ssh_args(builder), f"kill -KILL -{pgid_raw} 2>/dev/null || true"])
            time.sleep(1)

    capture([*ssh_args(builder), f"printf '%s' 'canceled' > {shlex.quote(job_dir + '/state')}"])
    capture([*ssh_args(builder), f"date -u +%FT%TZ > {shlex.quote(job_dir + '/finished-at')}"])
    print(f"[fleet] job '{job_id}' canceled.", file=sys.stderr)
    return True


def list_remote_jobs(builder: dict) -> list[str]:
    """Return a list of job IDs on the builder."""
    jobs_root = f"{builder['remote_root']}/.fleet/jobs"
    result = capture([*ssh_args(builder), f"ls -1 {shlex.quote(jobs_root)} 2>/dev/null || true"])
    return [line.strip() for line in result.splitlines() if line.strip()]


def cleanup_remote_jobs(builder: dict, *, older_than_days: int = 7) -> int:
    """Remove job directories older than *older_than_days*.

    Returns the number of directories removed.
    """
    jobs_root = f"{builder['remote_root']}/.fleet/jobs"
    script = (
        f"find {shlex.quote(jobs_root)} -maxdepth 1 -mindepth 1 -type d "
        f"-mtime +{int(older_than_days)} -print -exec rm -rf {{}} + 2>/dev/null || true"
    )
    result = capture([*ssh_args(builder), script])
    count = len([l for l in result.splitlines() if l.strip()])
    print(f"[fleet] cleaned up {count} job(s) older than {older_than_days} day(s).", file=sys.stderr)
    return count
