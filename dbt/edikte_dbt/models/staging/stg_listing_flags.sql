SELECT
    flag_id,
    aktenzeichen,
    snapshot_id,
    category,
    flag_type,
    matched_keyword
FROM {{ source('raw', 'raw_listing_flags') }}