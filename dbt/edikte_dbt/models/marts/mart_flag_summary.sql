SELECT
    f.category,
    f.flag_type,
    s.ort,
    s.kategorie,
    COUNT(*) AS flag_count,
    COUNT(DISTINCT f.aktenzeichen) AS distinct_cases_flagged
FROM {{ ref('stg_listing_flags') }} f
JOIN {{ ref('stg_listing_snapshots') }} s ON s.snapshot_id = f.snapshot_id
GROUP BY f.category, f.flag_type, s.ort, s.kategorie
ORDER BY flag_count DESC