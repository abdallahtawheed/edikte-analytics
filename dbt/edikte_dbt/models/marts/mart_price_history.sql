-- NOTE: operates at source_url (page) grain, not BLNr. Bundled-BLNr pages
-- (see DECISIONS.md open item) will show one shared meistbot across what may
-- be multiple distinct units. Revisit once BLNr-level modeling is resolved.
WITH pre_auction AS (
    SELECT
        aktenzeichen,
        kategorie,
        ort,
        plz,
        schaetzwert,
        geringstes_gebot,
        source_url AS pre_auction_source_url,
        scraped_at AS estimate_scraped_at
    FROM {{ ref('stg_listing_snapshots') }}
    WHERE schaetzwert IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY aktenzeichen ORDER BY scraped_at ASC) = 1
),

outcomes AS (
    SELECT
        aktenzeichen,
        source_url AS outcome_source_url,
        status_title,
        meistbot,
        scraped_at AS outcome_scraped_at,
        bekannt_gemacht_am AS outcome_announced_at
    FROM {{ ref('stg_listing_snapshots') }}
    WHERE status_title LIKE 'Zuschlag ohne Überbot%'
      AND meistbot IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY aktenzeichen ORDER BY scraped_at DESC) = 1
)

SELECT
    o.outcome_source_url,
    o.aktenzeichen,
    p.kategorie,
    p.ort,
    p.plz,
    p.schaetzwert,
    p.geringstes_gebot,
    o.meistbot,
    o.outcome_announced_at,
    ROUND(o.meistbot - p.schaetzwert, 2) AS meistbot_vs_schaetzwert,
    ROUND(SAFE_DIVIDE(o.meistbot, p.schaetzwert), 4) AS meistbot_to_schaetzwert_ratio,
    ROUND(SAFE_DIVIDE(o.meistbot, p.geringstes_gebot), 4) AS meistbot_to_gebot_ratio
FROM outcomes o
INNER JOIN pre_auction p ON p.aktenzeichen = o.aktenzeichen