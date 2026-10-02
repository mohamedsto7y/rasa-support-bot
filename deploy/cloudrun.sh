#!/usr/bin/env bash
# Deploy the three services to Cloud Run with source builds (Cloud Build + Artifact Registry).
# Prereqs: gcloud auth login; a project with billing; run from the repo root.
#   PROJECT_ID=my-project REGION=europe-west1 bash deploy/cloudrun.sh
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-europe-west1}"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# 1. Mock backend (stands in for the client's order / CRM system)
gcloud run deploy mock-api --source mock_api --region "$REGION" \
  --port 8000 --allow-unauthenticated
API_URL=$(gcloud run services describe mock-api --region "$REGION" --format 'value(status.url)')

# 2. Action server
gcloud run deploy rasa-actions --source actions --region "$REGION" \
  --port 5055 --allow-unauthenticated --set-env-vars "ORDERS_API_URL=$API_URL"
ACTIONS_URL=$(gcloud run services describe rasa-actions --region "$REGION" --format 'value(status.url)')

# 3. Rasa server. TensorFlow needs memory; one instance because the demo tracker is in memory.
gcloud run deploy rasa-server --source . --region "$REGION" \
  --port 5005 --memory 4Gi --cpu 2 --max-instances 1 --timeout 300 \
  --allow-unauthenticated --set-env-vars "ACTION_ENDPOINT_URL=$ACTIONS_URL/webhook"
RASA_URL=$(gcloud run services describe rasa-server --region "$REGION" --format 'value(status.url)')

echo "Rasa: $RASA_URL"
echo "Try:  curl -s -X POST $RASA_URL/webhooks/rest/webhook -H 'Content-Type: application/json' -d '{\"sender\":\"demo\",\"message\":\"where is my order 48213\"}'"
