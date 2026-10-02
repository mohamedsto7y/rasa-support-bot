# Bilingual Customer Support Bot (Rasa 3.6 · Python · GCP)

A customer-support assistant built with Rasa Open Source. It understands English and Egyptian Arabic. It tracks orders against a backend API, collects complaints through forms and opens tickets, answers FAQs with a response selector, and hands off to a human agent. It runs locally, in Docker Compose with a Postgres tracker store, and on Google Cloud Run.

## Features

| Area | Where |
|---|---|
| NLU pipeline: DIET (intents and entities together), char n-gram features for Arabic, regex features, synonyms, fallback | `config.yml`, `data/nlu.yml` |
| Dialogue: rules for fixed behaviour, stories for TEDPolicy, UnexpecTED for odd turns | `data/rules.yml`, `data/stories.yml` |
| Forms with slot validation; free-text answers are normalized (`48213` → `ORD-48213`, Arabic digits, `+20` phone prefixes) | `domain.yml` forms, `actions/actions.py` |
| Unhappy paths: cancelling or asking an FAQ mid-form, asking for an agent mid-form | `data/rules.yml` |
| Per-turn language detection: a global `ValidationAction` sets `lang` and conditional response variations reply in the user's language | `ValidatePredefinedSlots`, `domain.yml` |
| Custom actions calling an external API, with timeouts and a fallback when the API is down | `ActionCheckOrderStatus`, `ActionCreateTicket` |
| Retrieval FAQs (`faq/*`) via ResponseSelector | `data/nlu.yml` |
| CI: data validation, training and tests on every push | `.github/workflows/ci.yml`, `tests/test_stories.yml` |
| Containers and deployment: Compose with a Postgres tracker store; Cloud Run script | `Dockerfile`s, `docker-compose.yml`, `deploy/cloudrun.sh` |

## Run locally (Python 3.10)

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt     # Rasa only; it pins old deps, keep FastAPI out of this env
rasa data validate
rasa train
```

Then run these three services, each in its own terminal. Run the mock API from a separate Python environment that has `mock_api/requirements.txt` installed:

```bash
uvicorn mock_api.main:app --port 8000     # backend
rasa run actions                          # action server :5055
rasa shell                                # chat in the terminal
```

Things to try:
- `hi` → `where is my order` → `48213`
- `الأوردر رقم 77777 فين`
- `I have a problem with my order` → `what payment methods do you have?` (an FAQ mid-form) → `broken` → `01012345678`
- `cancel` partway through a form
- `talk to an agent`

Test orders in `mock_api/main.py`: 48213, 10001, 55555, 77777, 12345.

### Tests

```bash
rasa test --stories tests/test_stories.yml                    # NLU and dialogue-policy tests
rasa run --enable-api                                         # then, with actions and the mock API running:
python tests/smoke_test.py                                    # 7 scripted EN/AR conversations, end to end
```

## Docker Compose

```bash
docker compose up --build
curl -X POST localhost:5005/webhooks/rest/webhook -H "Content-Type: application/json" -d "{\"sender\":\"u1\",\"message\":\"where is my order 48213\"}"
```

Conversations are saved in Postgres through the SQL tracker store.

## Google Cloud Run

```bash
PROJECT_ID=<your-project> REGION=europe-west1 bash deploy/cloudrun.sh
```

This deploys three services from source with Cloud Build:
- `mock-api`
- `rasa-actions`
- `rasa-server`, with the model trained inside the image and 4 GiB of memory

### Production version on GCP

- **Compute:** Rasa server and action server on GKE (or Cloud Run) with autoscaling.
- **State:** tracker store on Cloud SQL Postgres, plus a Redis lock store on Memorystore so several replicas can serve the same conversation.
- **Models:** model artifacts versioned in Cloud Storage (`rasa run --remote-storage gcs`).
- **Analytics:** tracker events streamed to BigQuery, for example through a Kafka event broker and a Pub/Sub bridge. Dashboards there show fallback rate, form completion and handoff rate by intent, and they decide the next annotation batch.
- **Voice:** Cloud Speech-to-Text and Text-to-Speech in front of the REST channel.
- **CI/CD:** validate, train, `rasa test`, then promote a model only if it beats the current one. Infrastructure in Terraform.

## Moving to CALM (Rasa Pro)

This project uses the NLU and stories approach of Rasa Open Source. In Rasa Pro's CALM, the two forms would become `flows.yml` flows. An LLM command generator would replace intent classification for starting flows and filling slots. Conversation repair patterns would cover what the unhappy-path rules handle here (cancel, digressions, corrections). The custom actions and the backend integration would stay the same.
