# Coding Agents are Effective Long-Context Processors

**Abstract**

Large Language Models (LLMs) have demonstrated remarkable progress in scaling to access massive contexts. However, the access is via the latent and uninterpretable attention mechanisms, and LLMs fail to effectively *process* long context, exhibiting significant performance degradation as context length increases. In this work, we study whether long-context processing can be externalized from latent attention into explicit, executable interactions, by allowing coding agents to organize text in file systems and manipulate it using its native tools. We evaluate off-the-shelf frontier coding agents as the general interface for tasks that require processing long contexts, including long-context reasoning, retrieval-augmented generation, and open-domain question answering with large-scale corpus containing up to three trillion tokens. Across multiple benchmarks, these agents outperform published state-of-the-art by **17.3%** on average. We attribute this efficacy to two key factors: *native tool proficiency*, which enables agents to leverage executable code and terminal commands rather than passive semantic queries, and *file system familiarity*, which allows them to navigate massive text corpora as directory structures.

---

## Installation

### Requirements

- Python 3.8+
- `python-dotenv` (optional, for environment variable management)

Install dependencies:

```bash
pip install python-dotenv
```

You will also need one of the following CLI tools available on your `PATH`:

- `codex` — for Codex-based experiments
- `claude` — for Claude Code-based experiments

---

## Data Preparation

Prepare your prompts as a Python pickle file containing a dictionary mapping IDs to prompts:

```python
import pickle

prompts = {
    "example_1": "Write a Python function that returns 42.",
    "example_2": "Count the words in this sentence.",
}

with open("prompts.pkl", "wb") as f:
    pickle.dump(prompts, f)
```

---

## Running Experiments

### Basic Usage

**With Codex:**

```bash
python run_coding_agents.py \
    --engine codex \
    --pickle /path/to/prompts.pkl \
    --outdir ./codex_outputs \
    --threads 10 \
    --resume
```

**With Claude:**

```bash
python run_coding_agents.py \
    --engine claude \
    --pickle /path/to/prompts.pkl \
    --outdir ./claude_outputs \
    --threads 10 \
    --resume
```

### Specifying a Custom Binary Path

If the engine binary is not on `PATH`:

```bash
python run_coding_agents.py \
    --engine codex \
    --pickle prompts.pkl \
    --bin /usr/local/bin/codex
```

### Conda Environment Configuration

The script supports conda environment configuration via environment variables or CLI arguments:

| Variable | Description |
|----------|-------------|
| `ENGINE_CONDA_PREFIX` | Absolute path to the conda environment root (recommended) |
| `CONDA_PREFIX` | Fallback if `ENGINE_CONDA_PREFIX` is not set |
| `ENGINE_CONDA_NAME` | Sets `CONDA_DEFAULT_ENV` (defaults to the last path segment) |

Alternatively, specify via CLI:

```bash
python run_coding_agents.py \
    --engine codex \
    --pickle prompts.pkl \
    --conda-prefix /opt/conda/envs/myenv
```

Or use a `.env` file (loaded automatically):

```
ENGINE_CONDA_PREFIX=/opt/conda/envs/myenv
ENGINE_CONDA_NAME=myenv
```

---

## Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--engine` | Engine to use (`codex` or `claude`) | *required* |
| `--pickle` | Path to pickle file containing `{id: prompt}` | *required* |
| `--outdir` | Output directory | `./<engine>_outputs` |
| `--limit` | Limit number of prompts processed | None |
| `--resume` | Skip prompts with existing `.out.txt` files | False |
| `--interval` | Print progress every N completions | 1 |
| `--threads` | Number of worker threads | 10 |
| `--bin` | Path to engine binary | auto-detected |
| `--conda-prefix` | Conda environment root to prepend to `PATH` | None |

---

## Output Format

For each prompt with ID `key` (sanitized to `safe_id`), the script produces:

| File | Description |
|------|-------------|
| `<outdir>/<safe_id>.out.txt` | Engine stdout (Claude: `result` field from JSON) |
| `<outdir>/<safe_id>.err.txt` | Stderr (removed if empty) |
| `<outdir>/combined.jsonl` | Aggregated results (one JSON object per prompt) |

### JSONL Schema

**Common fields:** `engine`, `id`, `safe_id`, `exit_code`, `stdout_path`, `stderr_path` (optional)

**Codex-specific:** `duration_s`, `started_at`, `finished_at`

**Claude-specific:** `cost`, `duration_ms`, `duration_api_ms`, `num_turns`, `usage`, `modelUsage`
