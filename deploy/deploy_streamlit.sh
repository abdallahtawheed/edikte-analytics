# deploy/deploy_streamlit.sh
#!/bin/bash
set -e
docker build -f deploy/streamlit/Dockerfile -t gcr.io/edikte-analytics-2026/streamlit-app .
docker push gcr.io/edikte-analytics-2026/streamlit-app
gcloud run deploy edikte-analytics-dashboard \
  --image gcr.io/edikte-analytics-2026/streamlit-app \
  --service-account streamlit-runner@edikte-analytics-2026.iam.gserviceaccount.com \
  --region europe-west3 \
  --allow-unauthenticated \
  --set-secrets DB_PASSWORD=db-password:latest
echo "Deployed. Verifying..."
curl -I $(gcloud run services describe edikte-analytics-dashboard --region europe-west3 --format="value(status.url)")