SELECT
    ort,
    plz,
    kategorie,
    COUNT(*) AS listing_count,
    ROUND(AVG(schaetzwert), 2) AS avg_schaetzwert,
    ROUND(AVG(geringstes_gebot), 2) AS avg_geringstes_gebot,
    ROUND(AVG(price_per_sqm), 2) AS avg_price_per_sqm,
    ROUND(MIN(price_per_sqm), 2) AS min_price_per_sqm,
    ROUND(MAX(price_per_sqm), 2) AS max_price_per_sqm,
    SUM(total_flags) AS total_flags_in_region,
    COUNTIF(total_flags > 0) AS flagged_listing_count
FROM {{ ref('mart_current_objects') }}
WHERE status_title LIKE 'Versteigerung%'
GROUP BY ort, plz, kategorie
HAVING COUNT(*) >= 1
ORDER BY listing_count DESC