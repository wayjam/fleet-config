"""`fleet jobs` — manage remote builder jobs (list / status / log / cancel / cleanup)."""

import shlex
import sys

from builder import apply_builder_overrides, builder_config, ssh_args
from common import capture, die
from remote_job import (
    cancel_remote_job,
    cleanup_remote_jobs,
    job_remote_dir,
    list_remote_jobs,
    poll_remote_job,
    fetch_job_log_tail,
)


def _get_builder(args, config):
    if not args.builder:
        die("--builder is required for jobs commands")
    return apply_builder_overrides(builder_config(config, args.builder), args)


def cmd_jobs(args, config):
    if args.jobs_command == "list":
        _jobs_list(args, config)
    elif args.jobs_command == "status":
        _jobs_status(args, config)
    elif args.jobs_command == "log":
        _jobs_log(args, config)
    elif args.jobs_command == "cancel":
        _jobs_cancel(args, config)
    elif args.jobs_command == "cleanup":
        _jobs_cleanup(args, config)
    else:
        die(f"unknown jobs command: {args.jobs_command}")


def _jobs_list(args, config):
    builder = _get_builder(args, config)
    jobs = list_remote_jobs(builder)
    if not jobs:
        print("(no jobs)", file=sys.stderr)
        return
    for job_id in jobs:
        status = poll_remote_job(builder, job_id)
        print(f"  {job_id:40s}  {status.state:10s}  exit={status.exit_code}", file=sys.stderr)


def _jobs_status(args, config):
    builder = _get_builder(args, config)
    status = poll_remote_job(builder, args.job_id)
    print(f"job:     {status.job_id}", file=sys.stderr)
    print(f"state:   {status.state}", file=sys.stderr)
    print(f"exit:    {status.exit_code}", file=sys.stderr)
    print(f"started: {status.started_at}", file=sys.stderr)
    print(f"finished:{status.finished_at or ' (still running)'}", file=sys.stderr)
    if status.artifact_path:
        print(f"artifact:{status.artifact_path}", file=sys.stderr)
        if status.artifact_size is not None:
            print(f"size:    {status.artifact_size} bytes", file=sys.stderr)
        if status.artifact_sha256:
            print(f"sha256:  {status.artifact_sha256}", file=sys.stderr)
    print(f"dir:     {job_remote_dir(builder, args.job_id)}", file=sys.stderr)


def _jobs_log(args, config):
    builder = _get_builder(args, config)
    which = args.which
    lines = args.lines
    log = fetch_job_log_tail(builder, args.job_id, which=which, lines=lines)
    if not log:
        print("(empty or no log)", file=sys.stderr)
        return
    print(log, end="")


def _jobs_cancel(args, config):
    builder = _get_builder(args, config)
    cancel_remote_job(builder, args.job_id, force=args.force)


def _jobs_cleanup(args, config):
    builder = _get_builder(args, config)
    cleanup_remote_jobs(builder, older_than_days=args.older_than)
