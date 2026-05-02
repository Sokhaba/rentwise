{{
    config(
        materialized = 'incremental',
        unique_key   = 'listing_id'
    )
}}

with incoming as (
    select * from {{ ref('int_listings_geo') }}
    {% if is_incremental() %}
        where scraped_at > (select max(scraped_at) from {{ this }})
    {% endif %}
),

existing as (
    {% if is_incremental() %}
        select * from {{ this }}
    {% else %}
        select
            null::varchar       as listing_id,
            null::timestamp_tz  as first_seen_at,
            null::number        as first_price,
            null::number        as scrape_count
        where 1 = 0
    {% endif %}
),

current_run as (
    select max(scraped_at) as run_at
    from incoming
),

merged as (
    select
        i.listing_id,
        i.platform,
        i.url,
        i.property_type,
        i.listing_date,
        i.title,
        i.price,
        i.currency,
        coalesce(e.first_price, i.price)            as first_price,
        i.price - coalesce(e.first_price, i.price)  as price_change,
        i.suburb,
        i.city,
        i.address,
        i.resolved_latitude                         as latitude,
        i.resolved_longitude                        as longitude,
        i.resolved_geo_source                       as geo_source,
        i.bedrooms,
        i.bathrooms,
        i.parking,
        i.erf_size,
        case
            when i.bedrooms > 0
            then round(i.price / i.bedrooms, 0)
            else null
        end                                         as price_per_bedroom,
        coalesce(e.first_seen_at, i.scraped_at)     as first_seen_at,
        i.scraped_at                                as last_seen_at,
        datediff('day',
            coalesce(e.first_seen_at, i.scraped_at),
            i.scraped_at)                           as days_on_market,
        (i.scraped_at = cr.run_at)                  as is_active,
        coalesce(e.scrape_count, 0) + 1             as scrape_count,
        i.agent,
        i.scraped_at
    from incoming i
    cross join current_run cr
    left join existing e using (listing_id)
    where i.price    between 1000 and 200000
      and i.bedrooms between 0   and 20
)

select * from merged
