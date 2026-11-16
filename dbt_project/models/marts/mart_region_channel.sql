select r.region, c.channel, sum(f.units) as units, round(sum(f.revenue),2) as revenue
from {{ source('raw','fact_sales') }} f
join {{ source('raw','dim_region') }} r on f.region_key = r.region_key
join {{ source('raw','dim_channel') }} c on f.channel_key = c.channel_key
group by 1,2
