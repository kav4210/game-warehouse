select g.title, g.genre, d.quarter, sum(f.units) as units, round(sum(f.revenue),2) as revenue
from {{ source('raw','fact_sales') }} f
join {{ source('raw','dim_game') }} g on f.game_key = g.game_key
join {{ source('raw','dim_date') }} d on f.date_key = d.date_key
group by 1,2,3
