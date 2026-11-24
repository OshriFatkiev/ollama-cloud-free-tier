# Ollama Free Cloud Models

> [!WARNING]
> **Ollama Cloud no longer has a free tier.** On 2026-11-24 no cloud model answered from a Free account: 21 of the 23 models probed returned HTTP 402 ("Add usage credits or subscribe"), including `gemma4` and `nemotron-3`, which were free on 2026-10-22. Ollama's [pricing page](https://ollama.com/pricing) now lists "Pay as you go: pay per token for every cloud model".
>
> The table below shows that last probe. Earlier results, back to May 2026, are in [`data/history.jsonl`](data/history.jsonl).

Unofficial tracker for Ollama cloud models that worked on the Free Ollama Cloud tier.

This repo checked whether Ollama cloud models could be used from a Free Ollama account.

It answered one question:

> Can this Ollama cloud model run on Free right now?

## Legend

**Free?**
- ✅ - model returned a successful response from a Free Ollama account
- 🔒 - Ollama returned a subscription or upgrade error
- ⚠️ - probe failed for another reason

## Models
<!-- MODELS_TABLE_START -->
> Last checked: 2026-11-24 06:08 UTC

| Model | Free? |
|---|:---:|
| [`beam:cloud`](https://ollama.com/library/beam:cloud) | 🔒 |
| [`deepseek-v4.1-flash:1017-cloud`](https://ollama.com/library/deepseek-v4.1-flash:1017-cloud) | 🔒 |
| [`deepseek-v4.1-flash:cloud`](https://ollama.com/library/deepseek-v4.1-flash:cloud) | 🔒 |
| [`gemma4:31b-cloud`](https://ollama.com/library/gemma4:31b-cloud) | 🔒 |
| [`gemma4:cloud`](https://ollama.com/library/gemma4:cloud) | 🔒 |
| [`glm-5.2:cloud`](https://ollama.com/library/glm-5.2:cloud) | 🔒 |
| [`glm-5.3-flash:cloud`](https://ollama.com/library/glm-5.3-flash:cloud) | 🔒 |
| [`glm-5.3:cloud`](https://ollama.com/library/glm-5.3:cloud) | 🔒 |
| [`hy4:cloud`](https://ollama.com/library/hy4:cloud) | 🔒 |
| [`inkling-2-small:cloud`](https://ollama.com/library/inkling-2-small:cloud) | 🔒 |
| [`kimi-k2.7-code:cloud`](https://ollama.com/library/kimi-k2.7-code:cloud) | 🔒 |
| [`kimi-k3.1-pro:cloud`](https://ollama.com/library/kimi-k3.1-pro:cloud) | 🔒 |
| [`kimi-k3:cloud`](https://ollama.com/library/kimi-k3:cloud) | 🔒 |
| [`mimo-v2.6-flash:cloud`](https://ollama.com/library/mimo-v2.6-flash:cloud) | 🔒 |
| [`mimo-v2.6-pro:cloud`](https://ollama.com/library/mimo-v2.6-pro:cloud) | 🔒 |
| [`minimax-m3.1-flash:cloud`](https://ollama.com/library/minimax-m3.1-flash:cloud) | 🔒 |
| [`minimax-m3:cloud`](https://ollama.com/library/minimax-m3:cloud) | 🔒 |
| [`mistral-large-4:cloud`](https://ollama.com/library/mistral-large-4:cloud) | 🔒 |
| [`muse-spark-open:cloud`](https://ollama.com/library/muse-spark-open:cloud) | 🔒 |
| [`nemotron-3-super:cloud`](https://ollama.com/library/nemotron-3-super:cloud) | 🔒 |
| [`nemotron-3-ultra:cloud`](https://ollama.com/library/nemotron-3-ultra:cloud) | 🔒 |
| [`clef:27b-cloud`](https://ollama.com/library/clef:27b-cloud) | ⚠️ |
| [`clef:cloud`](https://ollama.com/library/clef:cloud) | ⚠️ |
<!-- MODELS_TABLE_END -->

## Methodology

Each model is tested with a minimal prompt:

```text
Reply with exactly: OK
```

The probe records only:
- model name
- status
- HTTP status
- checked time
- short sanitized error excerpt

Untested discovered models are not shown in the table. The table shows only the models from the latest probe run.

Statuses are observed from a Free account and may change. A subscription error means the model was not Free-accessible at the time of testing. It does not mean the model is unavailable to paid Ollama users.

## Usage

Install dependencies:
```bash
uv sync
```
Discover candidate cloud models:
```bash
uv run python scripts/discover.py
```
Probe one model:
```bash
export OLLAMA_API_KEY="your_free_ollama_api_key"
uv run python scripts/probe.py --model glm-5.1:cloud
uv run python scripts/render_readme.py
```
Probe candidates:
```bash
export OLLAMA_API_KEY="your_free_ollama_api_key"
uv run python scripts/probe.py --all --max 20 --delay-seconds 10
uv run python scripts/render_readme.py
```

## GitHub Action

The workflow is manual-only.

Add this repository secret:
```bash
OLLAMA_FREE_API_KEY
```
Then run the workflow manually from GitHub Actions.

## License

This project is licensed under the [MIT License](LICENSE).

