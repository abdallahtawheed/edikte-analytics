#!/bin/bash
# deploy/run_pipeline.sh
set -e

echo "Triggering pipeline-job..."
EXECUTION_NAME=$(gcloud run jobs execute pipeline-job --region europe-west3 --format="value(metadata.name)")
echo "Execution started: $EXECUTION_NAME"
echo "Waiting for completion..."

while true; do
    STATE=$(gcloud run jobs executions describe "$EXECUTION_NAME" --region europe-west3 --format="value(status.conditions[0].type,status.conditions[0].status)")
    COMPLETED=$(gcloud run jobs executions describe "$EXECUTION_NAME" --region europe-west3 --format="value(status.completionTime)")
    if [ -n "$COMPLETED" ]; then
        break
    fi
    echo "Still running..."
    sleep 15
done

SUCCEEDED=$(gcloud run jobs executions describe "$EXECUTION_NAME" --region europe-west3 --format="value(status.succeededCount)")

if [ "$SUCCEEDED" == "1" ]; then
    echo "Pipeline completed successfully."
else
    echo "Pipeline failed. Checking logs..."
    gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=pipeline-job AND labels.\"run.googleapis.com/execution_name\"=\"$EXECUTION_NAME\" AND severity>=ERROR" --limit 50 --format "value(textPayload)"
fi