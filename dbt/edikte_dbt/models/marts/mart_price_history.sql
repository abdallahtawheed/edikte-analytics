-- NOTE: operates at source_url (page) grain, not BLNr. Bundled-BLNr pages
-- (e.g. an apartment sold with several parking spaces) show one combined
-- price across multiple units, since the source site does not publish
-- per-unit pricing for bundles. Rather than split rows (which would
-- duplicate an unsplittable price and degrade model quality), bundling is
-- surfaced as explicit features (is_bundled, unit_count) so a model can
-- learn from it honestly. See DECISIONS.md for full reasoning.

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
),

parcel_info AS (
    SELECT
        aktenzeichen,
        STRING_AGG(DISTINCT blnr, ' | ') AS blnr,
        SUM(objektgroesse_m2) AS total_objektgroesse_m2,
        MAX(CASE
            WHEN REGEXP_CONTAINS(blnr, r'^\d+\s*(,|-|und|u\.?|;)\s*\d+')
                 AND NOT REGEXP_CONTAINS(blnr, r'Anteil|Hälfteanteil|entspricht')
                THEN TRUE
            ELSE FALSE
        END) AS is_bundled,
        COUNT(DISTINCT blnr) AS unit_count
    FROM {{ ref('stg_listing_parcels') }}
    GROUP BY aktenzeichen
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
    pc.blnr,
    pc.total_objektgroesse_m2,
    pc.is_bundled,
    pc.unit_count,
    ROUND(o.meistbot - p.schaetzwert, 2) AS meistbot_vs_schaetzwert,
    ROUND(SAFE_DIVIDE(o.meistbot, p.schaetzwert), 4) AS meistbot_to_schaetzwert_ratio,
    ROUND(SAFE_DIVIDE(o.meistbot, p.geringstes_gebot), 4) AS meistbot_to_gebot_ratio,
    ROUND(
        CASE WHEN pc.is_bundled THEN SAFE_DIVIDE(o.meistbot, pc.unit_count) ELSE o.meistbot END,
        2
    ) AS meistbot_per_unit_estimate
FROM outcomes o
INNER JOIN pre_auction p ON p.aktenzeichen = o.aktenzeichen
LEFT JOIN parcel_info pc ON pc.aktenzeichen = o.aktenzeichen