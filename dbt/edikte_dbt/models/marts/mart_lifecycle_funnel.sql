SELECT
    EXTRACT(YEAR FROM observed_at) AS year,
    EXTRACT(MONTH FROM observed_at) AS month,
    status,
    transition_valid,
    COUNT(*) AS event_count,
    COUNT(DISTINCT aktenzeichen) AS distinct_cases
FROM {{ ref('stg_listing_status_events') }}
GROUP BY year, month, status, transition_valid
ORDER BY year DESC, month DESC, event_count DESC