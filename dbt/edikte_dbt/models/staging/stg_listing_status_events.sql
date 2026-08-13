SELECT
    status_event_id,
    aktenzeichen,
    status,
    CAST(observed_at AS TIMESTAMP) AS observed_at,
    previous_status,
    transition_valid,
    anomaly_note
FROM {{ source('raw', 'raw_listing_status_events') }}