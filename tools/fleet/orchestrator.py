"""Unified stage runner for multi-stage fleet commands.

Provides ``StageRunner`` which executes a list of :class:`Stage` objects with:

- Local state markers for resume / skip.
- Per-stage retry with configurable policy.
- Interactive failure handling (TTY): retry / skip / abort / show-log / continue.
- Non-interactive failure: die with a ready-to-paste resume command.

Business commands (``deploy``, ``image``, ``install``, ``infect``) define *what*
each stage does and *how* to verify it; the runner handles execution strategy.
"""

from __future__ import annotations

import argparse
import shlex
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from common import die, repo_root


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RunContext:
    """Mutable context passed to every stage's ``run`` / ``verify`` callables."""

    command: str           # e.g. "deploy", "image", "infect"
    target: str            # host or target name
    args: argparse.Namespace
    config: dict
    state_dir: Path        # local directory for ``<stage>.done`` markers
    interactive: bool
    retry: int             # max retries per stage (0 = no retry)
    log_dir: Path          # directory for local log capture
    # mutable bag for stages to share data across the pipeline
    data: dict = field(default_factory=dict)


@dataclass
class Stage:
    """A single unit of work in a multi-stage pipeline."""

    name: str
    description: str
    run: Callable[[RunContext], None]
    verify: Callable[[RunContext], None] | None = None
    retryable: bool = True      # may be auto-retried (also subject to --retry)
    skippable: bool = False     # may be skipped in interactive mode
    destructive: bool = False   # destructive: only retry after explicit confirm


FailureAction = Literal["retry", "skip", "abort", "continue"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def default_interactive() -> bool:
    """Return ``True`` when stdin is a TTY and no override was given."""
    return sys.stdin.isatty()


def resolve_interactive(args) -> bool:
    """Determine interactive mode from CLI flags or TTY detection."""
    if getattr(args, "non_interactive", False):
        return False
    if getattr(args, "interactive", False):
        return True
    return default_interactive()


def state_dir_for(command: str, target: str) -> Path:
    """Return the local state directory for *command* / *target*."""
    safe_target = "".join(c if c.isalnum() or c in "-_." else "-" for c in target)
    return repo_root() / ".fleet" / "state" / f"{command}-{safe_target}"


def log_dir_for(command: str, target: str) -> Path:
    """Return the local log directory for *command* / *target*."""
    safe_target = "".join(c if c.isalnum() or c in "-_." else "-" for c in target)
    return repo_root() / ".fleet" / "logs" / f"{command}-{safe_target}"


def stage_done_marker(ctx: RunContext, stage_name: str) -> Path:
    return ctx.state_dir / f"{stage_name}.done"


def stage_skip_marker(ctx: RunContext, stage_name: str) -> Path:
    return ctx.state_dir / f"{stage_name}.skip"


def is_stage_done(ctx: RunContext, stage_name: str) -> bool:
    return stage_done_marker(ctx, stage_name).exists()


def mark_stage_done(ctx: RunContext, stage_name: str) -> None:
    ctx.state_dir.mkdir(parents=True, exist_ok=True)
    stage_done_marker(ctx, stage_name).write_text(
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n"
    )


def mark_stage_skipped(ctx: RunContext, stage_name: str) -> None:
    ctx.state_dir.mkdir(parents=True, exist_ok=True)
    stage_skip_marker(ctx, stage_name).write_text(
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n"
    )


def clear_stage_markers(ctx: RunContext, stage_name: str) -> None:
    stage_done_marker(ctx, stage_name).unlink(missing_ok=True)
    stage_skip_marker(ctx, stage_name).unlink(missing_ok=True)


def clear_all_markers(ctx: RunContext) -> None:
    """Remove every marker for the current pipeline (used by ``--restart``)."""
    if ctx.state_dir.exists():
        for marker in ctx.state_dir.glob("*.done"):
            marker.unlink()
        for marker in ctx.state_dir.glob("*.skip"):
            marker.unlink()


def resume_hint(ctx: RunContext, stages: list[Stage], failed_stage: str) -> str:
    """Return a ready-to-paste command to resume from *failed_stage*."""
    from_stage = f"--from-stage {failed_stage}" if hasattr(ctx.args, "from_stage") else ""
    # Build a generic resume hint based on the command.
    parts = ["nix", "run", ".#fleet", "--", ctx.command]
    if ctx.target:
        parts.append(ctx.target)
    # Include the most useful resume flag if the command supports it.
    if hasattr(ctx.args, "from_stage") and ctx.args.from_stage is None:
        parts.extend(["--from-stage", failed_stage])
    elif hasattr(ctx.args, "stage"):
        parts.extend(["--stage", failed_stage])
    if getattr(ctx.args, "builder", ""):
        parts.extend(["--builder", ctx.args.builder])
    return "Resume with:\n  " + " ".join(shlex.quote(p) for p in parts)


# ---------------------------------------------------------------------------
# Interactive failure prompt
# ---------------------------------------------------------------------------


def _interactive_failure_prompt(ctx: RunContext, stage: Stage, attempt: int, exc: Exception) -> FailureAction:
    """Prompt the user for a failure action in TTY mode."""
    print(f"\n[fleet] Stage '{stage.name}' failed (attempt {attempt}): {exc}", file=sys.stderr)
    options = ["(r)etry", "(a)bort"]
    if stage.skippable:
        options.append("(s)kip")
    options.append("(c)ontinue")  # treat as success, continue to next stage
    options.append("(l)og")       # show recent log lines then re-prompt
    prompt = f"[fleet] Choose: {' '.join(options)} > "
    while True:
        try:
            answer = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "abort"
        if answer in ("r", "retry"):
            return "retry"
        if answer in ("a", "abort"):
            return "abort"
        if answer in ("s", "skip") and stage.skippable:
            return "skip"
        if answer in ("c", "continue"):
            return "continue"
        if answer in ("l", "log"):
            _show_recent_log(ctx, stage)
            continue
        print(f"  invalid choice: {answer}", file=sys.stderr)


def _show_recent_log(ctx: RunContext, stage: Stage) -> None:
    """Print the last lines of the local log file for *stage*."""
    log_file = ctx.log_dir / f"{stage.name}.log"
    if not log_file.exists():
        print("  (no local log file)", file=sys.stderr)
        return
    try:
        lines = log_file.read_text(errors="replace").splitlines()
        tail = lines[-40:] if len(lines) > 40 else lines
        for line in tail:
            print(f"  | {line}", file=sys.stderr)
    except OSError as exc:
        print(f"  (failed to read log: {exc})", file=sys.stderr)


# ---------------------------------------------------------------------------
# StageRunner
# ---------------------------------------------------------------------------


class StageRunner:
    """Execute a list of :class:`Stage` objects with resume / retry / interact."""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx

    def run_pipeline(self, stages: list[Stage], *, restart: bool = False, from_stage: str | None = None, stop_after: str | None = None) -> None:
        """Execute *stages* in order.

        - ``restart``: clear all existing markers before starting.
        - ``from_stage``: skip stages before this one (does not clear markers).
        - ``stop_after``: stop after this stage completes.
        """
        ctx = self.ctx
        if restart:
            clear_all_markers(ctx)

        # Determine the slice to execute.
        start_idx = 0
        if from_stage:
            names = [s.name for s in stages]
            if from_stage not in names:
                die(f"--from-stage '{from_stage}' is not a known stage; available: {', '.join(names)}")
            start_idx = names.index(from_stage)

        stop_idx = len(stages) - 1
        if stop_after:
            names = [s.name for s in stages]
            if stop_after not in names:
                die(f"--stop-after '{stop_after}' is not a known stage; available: {', '.join(names)}")
            stop_idx = names.index(stop_after)

        active_stages = stages[start_idx : stop_idx + 1]

        for stage in active_stages:
            self._execute_stage(stage)

        print(f"\n[fleet] {ctx.command} pipeline completed ({len(active_stages)} stage(s)).", file=sys.stderr)

    def _execute_stage(self, stage: Stage) -> None:
        ctx = self.ctx

        # Skip if already done (resume).
        if is_stage_done(ctx, stage.name):
            print(f"[fleet] {ctx.command}: stage '{stage.name}' already done — skipping.", file=sys.stderr)
            return

        # Skip if explicitly skipped earlier.
        if stage_skip_marker(ctx, stage.name).exists():
            print(f"[fleet] {ctx.command}: stage '{stage.name}' was skipped earlier — skipping.", file=sys.stderr)
            return

        print(f"\n[fleet] {ctx.command}: stage '{stage.name}' — {stage.description}", file=sys.stderr)

        attempt = 0
        max_attempts = 1 + (ctx.retry if stage.retryable else 0)

        while True:
            attempt += 1
            try:
                stage.run(ctx)
                if stage.verify is not None:
                    stage.verify(ctx)
                mark_stage_done(ctx, stage.name)
                print(f"[fleet] {ctx.command}: stage '{stage.name}' succeeded.", file=sys.stderr)
                return
            except KeyboardInterrupt:
                print(f"\n[fleet] interrupted during stage '{stage.name}'.", file=sys.stderr)
                print(resume_hint(ctx, [], stage.name), file=sys.stderr)
                raise
            except Exception as exc:
                # Destructive stages are never auto-retried.
                can_auto_retry = stage.retryable and not stage.destructive and attempt < max_attempts

                if can_auto_retry:
                    wait = min(2 ** (attempt - 1), 30)
                    print(
                        f"[fleet] stage '{stage.name}' failed (attempt {attempt}/{max_attempts}): {exc}",
                        file=sys.stderr,
                    )
                    print(f"[fleet] auto-retry in {wait}s ...", file=sys.stderr)
                    time.sleep(wait)
                    continue

                # No more auto-retries — either exhausted or non-retryable.
                if ctx.interactive:
                    action = _interactive_failure_prompt(ctx, stage, attempt, exc)
                    if action == "retry":
                        # Clear any partial state then retry.
                        clear_stage_markers(ctx, stage.name)
                        continue
                    if action == "skip":
                        mark_stage_skipped(ctx, stage.name)
                        print(f"[fleet] stage '{stage.name}' skipped by user.", file=sys.stderr)
                        return
                    if action == "continue":
                        mark_stage_done(ctx, stage.name)
                        print(f"[fleet] stage '{stage.name}' marked done by user (continue).", file=sys.stderr)
                        return
                    # abort
                    print(resume_hint(ctx, [], stage.name), file=sys.stderr)
                    die(f"aborted at stage '{stage.name}'.")

                # Non-interactive: die with resume hint.
                print(resume_hint(ctx, [], stage.name), file=sys.stderr)
                die(f"stage '{stage.name}' failed after {attempt} attempt(s): {exc}")


# ---------------------------------------------------------------------------
# Common orchestration CLI helpers
# ---------------------------------------------------------------------------


def add_orchestration_options(parser: argparse.ArgumentParser, *, skip_stage_options: bool = False) -> None:
    """Add common orchestration flags to a subcommand parser.

    When *skip_stage_options* is ``True`` (e.g. for commands that already
    define their own ``--stage`` / ``--stop-after``), the ``--from-stage`` and
    ``--stop-after`` flags are omitted.
    """
    group = parser.add_argument_group("orchestration")
    ex = group.add_mutually_exclusive_group()
    ex.add_argument("--interactive", action="store_true", help="force interactive failure prompts")
    ex.add_argument("--non-interactive", action="store_true", help="never prompt; fail with resume hint")
    group.add_argument("--retry", type=int, default=0, help="auto-retries per retryable stage (default 0)")
    group.add_argument("--restart", action="store_true", help="clear all stage markers before running")
    if not skip_stage_options:
        group.add_argument("--from-stage", default=None, help="resume from this stage (skip earlier ones)")
        group.add_argument("--stop-after", default=None, help="stop after this stage completes")
    group.add_argument("--log-dir", default=None, help="directory for local logs (default .fleet/logs/...)")


def make_context(command: str, target: str, args: argparse.Namespace, config: dict) -> RunContext:
    """Build a :class:`RunContext` from CLI *args*."""
    interactive = resolve_interactive(args)
    sdir = state_dir_for(command, target)
    if getattr(args, "log_dir", None):
        ldir = Path(args.log_dir)
    else:
        ldir = log_dir_for(command, target)
    ldir.mkdir(parents=True, exist_ok=True)
    sdir.mkdir(parents=True, exist_ok=True)
    return RunContext(
        command=command,
        target=target,
        args=args,
        config=config,
        state_dir=sdir,
        interactive=interactive,
        retry=getattr(args, "retry", 0),
        log_dir=ldir,
    )
