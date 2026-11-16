# Data dictionary (all data is SYNTHETIC)
| Table | Grain | Key columns |
|---|---|---|
| fact_sales | one row per sale | sale_id, date_key, game_key, region_key, channel_key, units, revenue (USD) |
| fact_engagement | one row per game/region/day | date_key, game_key, region_key, active_players, avg_session_min |
| dim_date | one row per day of 2024 | date_key (YYYYMMDD), month, quarter, weekday |
| dim_game | one row per game | game_key, title, genre, release_date, list_price |
| dim_region | NA, EU, JP, OTHER | region_key |
| dim_channel | digital, retail | channel_key |
| mart_game_quarterly | game x quarter | units, revenue |
| mart_region_channel | region x channel | units, revenue |
| mart_engagement | game x region | avg_active_players, avg_session_min |
## Definitions
- revenue = units x list_price x discount factor, in USD, never negative after cleaning
- Alert rule: a game's quarter-over-quarter revenue drop larger than 15 percent
