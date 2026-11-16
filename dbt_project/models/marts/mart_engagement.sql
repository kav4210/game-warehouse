select g.title, r.region, round(avg(e.active_players),1) as avg_active_players, round(avg(e.avg_session_min),1) as avg_session_min
from {{ source('raw','fact_engagement') }} e
join {{ source('raw','dim_game') }} g on e.game_key = g.game_key
join {{ source('raw','dim_region') }} r on e.region_key = r.region_key
group by 1,2
