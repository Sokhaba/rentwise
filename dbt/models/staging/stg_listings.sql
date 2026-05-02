{{
    config(
        materialized     = 'incremental',
        unique_key       = 'listing_id',
        on_schema_change = 'sync_all_columns'
    )
}}

with source as (
    select * from {{ source('raw', 'LISTINGS_RAW') }}

    {% if is_incremental() %}
        where scraped_at > (select max(scraped_at) from {{ this }})
    {% endif %}
),

cleaned as (
    select
        platform,
        listing_id,
        listing_number,
        property_type,
        try_to_date(listing_date)          as listing_date,
        initcap(trim(title))               as title,
        try_to_number(price)               as price,
        currency,
        initcap(trim(suburb))              as suburb,
        trim(address)                      as address,
        city,
        try_to_double(latitude)            as latitude,
        try_to_double(longitude)           as longitude,
        lower(trim(geo_source))            as geo_source,
        try_to_number(bedrooms)            as bedrooms,
        try_to_number(bathrooms)           as bathrooms,
        try_to_number(parking)             as parking,
        erf_size,
        agent,
        url,
        source_page,
        scraped_at,
        _loaded_at
    from source
    where listing_id is not null
      and price      is not null
      and price      > 0
),

deduped as (
    select *,
        row_number() over (
            partition by listing_id
            order by scraped_at desc
        ) as _row_num
    from cleaned
)

select * exclude (_row_num)
from deduped
where _row_num = 1
