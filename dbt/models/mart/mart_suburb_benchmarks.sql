{{
    config(materialized = 'table')
}}

with base as (
    select *
    from {{ ref('mart_rental_prices') }}
    where geo_source  != 'unknown'
      and bedrooms     is not null
      and price        is not null
),

benchmarks as (
    select
        suburb,
        city,
        bedrooms,
        count(*)                                            as listing_count,
        sum(case when is_active then 1 else 0 end)         as active_listing_count,
        round(median(price), 0)                            as median_price,
        round(avg(price), 0)                               as avg_price,
        round(percentile_cont(0.25)
            within group (order by price), 0)              as p25_price,
        round(percentile_cont(0.75)
            within group (order by price), 0)              as p75_price,
        round(min(price), 0)                               as min_price,
        round(max(price), 0)                               as max_price,
        round(median(price_per_bedroom), 0)                as median_price_per_bedroom,
        round(median(days_on_market), 0)                   as median_days_on_market,
        round(avg(days_on_market), 0)                      as avg_days_on_market,
        round(avg(latitude),  6)                           as avg_latitude,
        round(avg(longitude), 6)                           as avg_longitude,
        max(last_seen_at)                                  as last_seen_at
    from base
    group by suburb, city, bedrooms
    having count(*) >= 3
)

select * from benchmarks
