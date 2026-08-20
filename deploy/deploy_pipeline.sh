# deploy/deploy_pipeline.sh
#!/bin/bash
set -e
docker build -f deploy/pipeline/Dockerfile -t gcr.io/edikte-analytics-2026/pipeline-jobs . --no-cache
docker push gcr.io/edikte-analytics-2026/pipeline-jobs
gcloud run jobs update pipeline-job --image gcr.io/edikte-analytics-2026/pipeline-jobs --region europe-west3
echo "Updated. Run manually to test: gcloud run jobs execute pipeline-job --region europe-west3"