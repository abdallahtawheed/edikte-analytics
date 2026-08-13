WITH latest_snapshot AS (
    SELECT *
    FROM {{ ref('stg_listing_snapshots') }}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY source_url ORDER BY scraped_at DESC) = 1
),

parcel_info AS (
    SELECT
        snapshot_id,
        ez,
        blnr,
        vadium,
        objektgroesse_m2,
        grundstuecksgroesse_m2
    FROM {{ ref('stg_listing_parcels') }}
),

flag_counts AS (
    SELECT
        snapshot_id,
        COUNT(*) AS total_flags,
        COUNT(DISTINCT category) AS distinct_flag_categories
    FROM {{ ref('stg_listing_flags') }}
    GROUP BY snapshot_id
)

SELECT
    s.snapshot_id,
    s.aktenzeichen,
    s.source_url,
    s.status_title,
    s.kategorie,
    s.ort,
    s.plz,
    s.dienststelle,
    s.scraped_at,
    s.bekannt_gemacht_am,
    s.schaetzwert,
    s.geringstes_gebot,
    s.meistbot,
    p.ez,
    p.blnr,
    p.objektgroesse_m2,
    p.grundstuecksgroesse_m2,
    c.latitude,
    c.longitude,
    COALESCE(f.total_flags, 0) AS total_flags,
    COALESCE(f.distinct_flag_categories, 0) AS distinct_flag_categories,
    CASE
        WHEN s.schaetzwert IS NOT NULL AND p.objektgroesse_m2 > 0
        THEN ROUND(s.schaetzwert / p.objektgroesse_m2, 2)
        ELSE NULL
    END AS price_per_sqm
FROM latest_snapshot s
LEFT JOIN parcel_info p ON p.snapshot_id = s.snapshot_id
LEFT JOIN {{ ref('stg_listing_coordinates') }} c ON c.source_url = s.source_url
LEFT JOIN flag_counts f ON f.snapshot_id = s.snapshot_id