-- mart_flag_summary.sql, corrected
WITH latest_snapshot_per_object AS (
    SELECT snapshot_id
    FROM {{ ref('stg_listing_snapshots') }}
    WHERE source_url IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY source_url ORDER BY scraped_at DESC) = 1
)

SELECT
    f.category,
    f.flag_type,
    s.ort,
    s.kategorie,
    COUNT(*) AS flag_count,
    COUNT(DISTINCT f.aktenzeichen) AS distinct_cases_flagged
FROM {{ ref('stg_listing_flags') }} f
JOIN {{ ref('stg_listing_snapshots') }} s ON s.snapshot_id = f.snapshot_id
WHERE f.snapshot_id IN (SELECT snapshot_id FROM latest_snapshot_per_object)
GROUP BY f.category, f.flag_type, s.ort, s.kategorie
ORDER BY flag_count DESC