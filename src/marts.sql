CREATE TABLE mart_game_quarterly AS
SELECT g.title,g.genre,d.quarter,SUM(f.units) units,ROUND(SUM(f.revenue),2) revenue
FROM fact_sales f JOIN dim_game g ON f.game_key=g.game_key JOIN dim_date d ON f.date_key=d.date_key
GROUP BY g.title,g.genre,d.quarter;
CREATE TABLE mart_region_channel AS
SELECT r.region,c.channel,SUM(f.units) units,ROUND(SUM(f.revenue),2) revenue
FROM fact_sales f JOIN dim_region r ON f.region_key=r.region_key JOIN dim_channel c ON f.channel_key=c.channel_key
GROUP BY r.region,c.channel;
CREATE TABLE mart_engagement AS
SELECT g.title,r.region,ROUND(AVG(e.active_players),1) avg_active_players,ROUND(AVG(e.avg_session_min),1) avg_session_min
FROM fact_engagement e JOIN dim_game g ON e.game_key=g.game_key JOIN dim_region r ON e.region_key=r.region_key
GROUP BY g.title,r.region;
