<div align="center">
<h1>Coding Agents are Effective Long-Context Processors</h1>

</div>

## Table of Contents
* [Abstract](#abstract)
* [Setup](#setup)
* [Data Preparation](#data-preparation)
* [Running Experiments](#running-experiments)
  * [Basic Usage](#basic-usage)
  * [Arguments](#arguments)
* [Output Format](#output-format)
* [License](#license)

## Abstract
Large Language Models (LLMs) have demonstrated remarkable progress in scaling to access massive contexts. However, the access is via the latent and uninterpretable attention mechanisms, and LLMs fail to effectively *process* long context, exhibiting significant performance degradation as context length increases. In this work, we study whether long-context processing can be externalized from latent attention into explicit, executable interactions, by allowing coding agents to organize text in file systems and manipulate it using its native tools. We evaluate off-the-shelf frontier coding agents as the general interface for tasks that require processing long contexts, including long-context reasoning, retrieval-augmented generation, and open-domain question answering with large-scale corpus containing up to three trillion tokens. Across multiple benchmarks, these agents outperform published state-of-the-art by **17.3%** on average. We attribute this efficacy to two key factors: *native tool proficiency*, which enables agents to leverage executable code and terminal commands rather than passive semantic queries, and *file system familiarity*, which allows them to navigate massive text corpora as directory structures.

## Setup
We recommend install the following dependencies:
```
pip install python-dotenv
```

You will also need one of the following CLI tools available on your `PATH`:

* `codex` — for Codex-based experiments
* `claude` — for Claude Code-based experiments

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

## Running Experiments

### Basic Usage

To run experiments with Codex, use:
```
python run_coding_agents.py \
    --engine codex \
    --pickle /path/to/prompts.pkl \
    --outdir ./codex_outputs \
    --threads 10 \
    --resume
```

To run experiments with Claude, use:
```
python run_coding_agents.py \
    --engine claude \
    --pickle /path/to/prompts.pkl \
    --outdir ./claude_outputs \
    --threads 10 \
    --resume
```

If the engine binary is not on `PATH`, specify a custom binary path:
```
python run_coding_agents.py \
    --engine codex \
    --pickle prompts.pkl \
    --bin /usr/local/bin/codex
```

### Conda Environment Configuration
The script supports conda environment configuration via environment variables or CLI arguments:

* `ENGINE_CONDA_PREFIX`: Absolute path to the conda environment root (recommended)
* `CONDA_PREFIX`: Fallback if `ENGINE_CONDA_PREFIX` is not set
* `ENGINE_CONDA_NAME`: Sets `CONDA_DEFAULT_ENV` (defaults to the last path segment)

Alternatively, specify via CLI:
```
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

### Arguments

We explain the arguments as follows:

* `--engine`: Engine to use. Choose from `codex` or `claude`. (required)
* `--pickle`: Path to pickle file containing `{id: prompt}`. (required)
* `--outdir`: Output directory. Default: `./<engine>_outputs`
* `--limit`: Limit number of prompts processed. Default: None
* `--resume`: Skip prompts with existing `.out.txt` files. Default: False
* `--interval`: Print progress every N completions. Default: 1
* `--threads`: Number of worker threads. Default: 10
* `--bin`: Path to engine binary. Default: auto-detected
* `--conda-prefix`: Conda environment root to prepend to `PATH`. Default: None

## Output Format
For each prompt with ID `key` (sanitized to `safe_id`), the script produces:

* `<outdir>/<safe_id>.out.txt`: Engine stdout (Claude: `result` field from JSON)
* `<outdir>/<safe_id>.err.txt`: Stderr (removed if empty)
* `<outdir>/combined.jsonl`: Aggregated results (one JSON object per prompt)

### Output Data Structure
```
{
    "engine": string,
    "id": string,
    "safe_id": string,
    "exit_code": int,
    "stdout_path": string,
    "stderr_path": string (optional),
    
    // Codex-specific fields:
    "duration_s": float,
    "started_at": string,
    "finished_at": string,
    
    // Claude-specific fields:
    "cost": float,
    "duration_ms": int,
    "duration_api_ms": int,
    "num_turns": int,
    "usage": object,
    "modelUsage": object
}
```

## License

The code in this project is licensed under the MIT license.
