#!/usr/bin/env python3
import argparse
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
import threading
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


def load_prompts(pickle_path: Path):
    with open(pickle_path, "rb") as f:
        prompts = pickle.load(f)
    if not isinstance(prompts, dict):
        raise TypeError("Expected a dict of {id: prompt} in pickle")
    return prompts


def sanitize_id(key: str) -> str:
    s = str(key)
    s = re.sub(r"[^A-Za-z0-9_.-]", "_", s)
    return s[:200]


def process_prompt(
    *,
    engine: str,
    key,
    prompt,
    outdir: Path,
    bin_path: str,
    combined_path: Path,
    lock: threading.Lock,
    resume: bool,
):
    try:
        safe_id = sanitize_id(key)
        out_txt = outdir / f"{safe_id}.out.txt"
        err_txt = outdir / f"{safe_id}.err.txt"

        if resume and out_txt.exists():
            return ("skipped", key, safe_id, 0, None)

        # Optionally prefer a specific conda env if provided via env vars
        # ENGINE_CONDA_PREFIX takes precedence; otherwise falls back to CONDA_PREFIX
        custom_env = os.environ.copy()
        conda_env_root = os.getenv("ENGINE_CONDA_PREFIX") or os.getenv("CONDA_PREFIX")
        if conda_env_root:
            conda_env_bin = os.path.join(conda_env_root, "bin")
            custom_env["PATH"] = f"{conda_env_bin}:{custom_env['PATH']}"
            # Best-effort to set conda-related vars without hard-coding personal info
            default_env_name = os.getenv("ENGINE_CONDA_NAME") or os.path.basename(conda_env_root.rstrip("/"))
            custom_env["CONDA_DEFAULT_ENV"] = default_env_name
            custom_env["CONDA_PREFIX"] = conda_env_root
            custom_env["CONDA_SHLVL"] = custom_env.get("CONDA_SHLVL", "1")
            custom_env["CONDA_AUTO_ACTIVATE_BASE"] = custom_env.get("CONDA_AUTO_ACTIVATE_BASE", "false")

        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.time()

        try:
            if engine == "codex":
                cmd = [
                    bin_path,
                    "exec",
                    "--skip-git-repo-check",
                    "--dangerously-bypass-approvals-and-sandbox",
                    str(prompt),
                ]
            elif engine == "claude":
                cmd = [
                    bin_path,
                    "-p",
                    str(prompt),
                    "--dangerously-skip-permissions",
                    "--output-format",
                    "json",
                ]
            else:
                raise ValueError(f"Unknown engine: {engine}")

            res = subprocess.run(
                cmd,
                env=custom_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            stdout = res.stdout
            stderr = res.stderr
            exit_code = res.returncode
        except Exception as e:
            stdout = ""
            stderr = f"Exception while running {engine}: {e}"
            exit_code = -1

        duration = time.time() - t0
        finished_at = datetime.now(timezone.utc).isoformat()

        # Engine-specific stdout handling
        if engine == "claude":
            model_result = ""
            try:
                stdout_dict = json.loads(stdout or "{}")
                model_result = stdout_dict.get("result", "")
            except Exception as e:
                # If JSON parse fails, keep raw stdout and note error in stderr
                if stderr:
                    stderr = f"{stderr}\nJSON parse error: {e}"
                else:
                    stderr = f"JSON parse error: {e}"
                model_result = stdout
            out_txt.write_text(model_result if model_result is not None else "")
        else:  # codex
            out_txt.write_text(stdout)

        if stderr:
            err_txt.write_text(stderr)
        elif err_txt.exists():
            try:
                err_txt.unlink()
            except Exception:
                pass

        # Build combined record
        record = {
            "engine": engine,
            "id": key,
            "safe_id": safe_id,
            "exit_code": exit_code,
            "stdout_path": str(out_txt),
        }

        if engine == "codex":
            record.update(
                {
                    "duration_s": round(duration, 3),
                    "started_at": started_at,
                    "finished_at": finished_at,
                }
            )
        else:  # claude
            try:
                stdout_dict = json.loads(stdout or "{}")
                record.update(
                    {
                        "cost": stdout_dict.get("total_cost_usd"),
                        "duration_ms": stdout_dict.get("duration_ms"),
                        "duration_api_ms": stdout_dict.get("duration_api_ms"),
                        "num_turns": stdout_dict.get("num_turns"),
                        "usage": stdout_dict.get("usage"),
                        "modelUsage": stdout_dict.get("modelUsage"),
                    }
                )
            except Exception:
                pass

        if stderr:
            record["stderr_path"] = str(err_txt)

        # Thread-safe append to combined JSONL
        with lock:
            with open(combined_path, "a", encoding="utf-8") as w:
                w.write(json.dumps(record, ensure_ascii=False) + "\n")

        # For codex, include duration as extra; for claude, None
        extra = duration if engine == "codex" else None
        return ("processed", key, safe_id, exit_code, extra)

    except Exception as e:
        return ("error", key, str(e), -1, None)


def main():
    parser = argparse.ArgumentParser(
        description="Run prompts in parallel using specified engine ('codex' or 'claude') and save outputs."
    )
    parser.add_argument("--engine", choices=["codex", "claude"], required=True, help="Which engine to use")
    parser.add_argument("--pickle", required=True, help="Path to prompts pickle containing a dict {id: prompt}")
    parser.add_argument("--outdir", default=None, help="Directory to store outputs (default: ./<engine>_outputs)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of prompts to run")
    parser.add_argument("--resume", action="store_true", help="Skip prompts that already have output files")
    parser.add_argument("--interval", type=int, default=1, help="Print progress every N prompts")
    parser.add_argument("--threads", type=int, default=10, help="Number of worker threads to use")
    parser.add_argument("--bin", default=None, help="Path to engine binary; defaults to first found on PATH")
    parser.add_argument("--conda-prefix", dest="conda_prefix", default=None, help="Conda env prefix to prepend to PATH (overrides env)")
    args = parser.parse_args()

    pickle_path = Path(args.pickle)
    outdir = Path(args.outdir or f"./{args.engine}_outputs")
    outdir.mkdir(parents=True, exist_ok=True)

    prompts = load_prompts(pickle_path)
    keys = list(prompts.keys())
    try:
        keys = sorted(keys)
    except Exception:
        pass

    if args.limit is not None:
        keys = keys[: args.limit]

    # Resolve engine binary
    bin_name = args.engine
    bin_path = args.bin or shutil.which(bin_name)
    if not bin_path:
        print(f"ERROR: '{bin_name}' not found on PATH.", file=sys.stderr)
        sys.exit(1)

    # Allow overriding conda prefix from CLI
    if args.conda_prefix:
        os.environ["ENGINE_CONDA_PREFIX"] = args.conda_prefix

    combined_path = outdir / "combined.jsonl"
    lock = threading.Lock()

    total = len(keys)
    print(
        f"Found {total} prompt(s). Engine: {args.engine}. Threads: {args.threads}. Writing outputs under: {outdir}"
    )

    processed_count = 0
    skipped_count = 0
    futures = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        for key in keys:
            prompt = prompts[key]
            futures.append(
                executor.submit(
                    process_prompt,
                    engine=args.engine,
                    key=key,
                    prompt=prompt,
                    outdir=outdir,
                    bin_path=bin_path,
                    combined_path=combined_path,
                    lock=lock,
                    resume=args.resume,
                )
            )

        for future in concurrent.futures.as_completed(futures):
            try:
                status, key, data, exit_code, extra = future.result()

                log_msg = ""
                if status == "skipped":
                    skipped_count += 1
                    log_msg = f"resume skip: {key}"
                elif status == "processed":
                    processed_count += 1
                    status_str = "OK" if exit_code == 0 else f"ERR({exit_code})"
                    out_name = f"{data}.out.txt"  # data is safe_id
                    if args.engine == "codex" and isinstance(extra, (int, float)):
                        log_msg = f"{status_str}: {key} -> {out_name} ({extra:.2f}s)"
                    else:
                        log_msg = f"{status_str}: {key} -> {out_name}"
                elif status == "error":
                    processed_count += 1
                    log_msg = f"WORKER_ERR: {key} ({data})"  # data is exception string

                total_completed = processed_count + skipped_count
                if total_completed % args.interval == 0 or total_completed == total:
                    if log_msg:
                        print(f"[{total_completed}/{total}] {log_msg}")

            except Exception as e:
                total_completed = processed_count + skipped_count
                print(
                    f"[{total_completed}/{total}] FATAL ERROR: A future failed: {e}",
                    file=sys.stderr,
                )

    total_completed = processed_count + skipped_count
    print(
        f"Done. Processed {processed_count}, Skipped {skipped_count}. Total completed {total_completed}/{total}. Combined log: {combined_path}"
    )


if __name__ == "__main__":
    main()
