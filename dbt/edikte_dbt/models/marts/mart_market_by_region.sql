-- dbt/edikte_dbt/models/marts/mart_market_by_region.sql

WITH by_ort_plz_kategorie AS (
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
        COUNTIF(total_flags > 0) AS flagged_listing_count,
        FALSE AS is_city_rollup
    FROM {{ ref('mart_current_objects') }}
    WHERE status_title LIKE 'Versteigerung%'
    GROUP BY ort, plz, kategorie
),

by_ort AS (
    SELECT
        ort,
        CAST(NULL AS INT64) AS plz,
        CAST(NULL AS STRING) AS kategorie,
        SUM(listing_count) AS listing_count,
        -- weighted average: accounts for each underlying group having a
        -- different listing_count, a plain AVG() here would incorrectly
        -- treat a 1-listing group and a 49-listing group equally
        ROUND(SAFE_DIVIDE(SUM(avg_schaetzwert * listing_count), SUM(listing_count)), 2) AS avg_schaetzwert,
        ROUND(SAFE_DIVIDE(SUM(avg_geringstes_gebot * listing_count), SUM(listing_count)), 2) AS avg_geringstes_gebot,
        ROUND(SAFE_DIVIDE(SUM(avg_price_per_sqm * listing_count), SUM(listing_count)), 2) AS avg_price_per_sqm,
        ROUND(MIN(min_price_per_sqm), 2) AS min_price_per_sqm,
        ROUND(MAX(max_price_per_sqm), 2) AS max_price_per_sqm,
        SUM(total_flags_in_region) AS total_flags_in_region,
        SUM(flagged_listing_count) AS flagged_listing_count,
        TRUE AS is_city_rollup
    FROM by_ort_plz_kategorie
    GROUP BY ort
)

SELECT * FROM by_ort_plz_kategorie
UNION ALL
SELECT * FROM by_ort
ORDER BY listing_count DESC