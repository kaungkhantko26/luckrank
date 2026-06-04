# LuckRank

This is a Python decision-support web app and CLI for ranking practical routes with local scoring.

The website is local-first by default. The browser never receives your API key, requests go through the local Python server, and `.env` is ignored by git.

It is designed to avoid locking you into one fixed model:

- Default model: `openrouter/auto`
- OpenRouter fallback routing: enabled with `route: "fallback"`
- Local retry fallback models: configurable through `OPENROUTER_FALLBACK_MODELS`

## Scoring

Routes are ranked with:

```text
Score = (P_success * Reward) / (Cost * Time * Risk)
Luck = Do + Show
```

`Luck` is treated as a small multiplier on the route probability. It rewards routes where the user can take action (`Do`) and increase visibility/distribution (`Show`) without pretending effort guarantees success.

## Setup

For local website use, no external key is required. For optional CLI/external analysis, put your key in `.env`:

```text
OPENROUTER_API_KEY=your_openrouter_key
WEB_USE_EXTERNAL_ANALYSIS=false
```

Do not commit `.env`. Use `.env.example` as the public template.

Optional:

```text
OPENROUTER_MODEL=openrouter/auto
OPENROUTER_FALLBACK_MODELS=anthropic/claude-3.5-sonnet,openai/gpt-4o-mini,google/gemini-flash-1.5
OPENROUTER_SITE_URL=http://localhost
OPENROUTER_APP_NAME=AI Decision Support System
```

## Run

Website:

```bash
python3 web_app.py
```

Then open:

```text
http://127.0.0.1:8000
```

CLI:

```bash
python3 decision_support.py
```

One-shot:

```bash
python3 decision_support.py \
  --problem "I want to start an online business" \
  --factors-json '{"budget":"$500","hours_per_week":"20","skills":"web design, marketing","risk_tolerance":"medium","desired_reward":"increase monthly income"}'
```

## Test

```bash
python3 -m unittest
```

## GitHub Actions Deploy Artifact

This repo includes:

- `.github/workflows/ci.yml`: runs tests, compile checks, and a basic secret scan.
- `.github/workflows/docker-publish.yml`: builds and publishes a Docker image to GitHub Container Registry on pushes to `main`.

The website is local-first by default. Set `WEB_USE_EXTERNAL_ANALYSIS=true` only if you explicitly want the server to call the configured external model provider.
