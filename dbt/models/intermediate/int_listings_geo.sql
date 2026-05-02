{{
    config(materialized = 'view')
}}

with listings as (
    select * from {{ ref('stg_listings') }}
),

-- Deduplicate centroids before joining — keeps one row per suburb+city
-- so the join never multiplies listing rows
centroids as (
    select distinct
        lower(trim(suburb)) as suburb_key,
        lower(trim(city))   as city_key,
        latitude            as centroid_lat,
        longitude           as centroid_lon
    from {{ ref('sa_suburb_centroids') }}
    qualify row_number() over (
        partition by lower(trim(suburb)), lower(trim(city))
        order by latitude
    ) = 1
),

enriched as (
    select
        l.*,
        coalesce(l.latitude,  c.centroid_lat) as resolved_latitude,
        coalesce(l.longitude, c.centroid_lon) as resolved_longitude,
        case
            when l.latitude  is not null and l.longitude is not null then 'direct'
            when c.centroid_lat is not null                          then 'centroid'
            else 'unknown'
        end as resolved_geo_source
    from listings l
    left join centroids c
        on  lower(trim(l.suburb)) = c.suburb_key
        and lower(trim(l.city))   = c.city_key
)

select * from enriched