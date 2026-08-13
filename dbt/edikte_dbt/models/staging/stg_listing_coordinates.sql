SELECT
    source_url,
    latitude,
    longitude
FROM {{ source('raw', 'raw_listing_coordinates') }}