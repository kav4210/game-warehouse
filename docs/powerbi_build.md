# Power BI dashboard (about 20 minutes)
1. Power BI Desktop > Get Data > Text/CSV. Load data/mart_game_quarterly.csv, mart_region_channel.csv, mart_engagement.csv.
2. No relationships needed. Each mart is already aggregated, which is the point of a mart.
3. New measures (Modeling > New measure), on mart_game_quarterly:
   Total Revenue = SUM(mart_game_quarterly[revenue])
   Total Units = SUM(mart_game_quarterly[units])
   Revenue Prior Quarter = CALCULATE([Total Revenue], PREVIOUSQUARTER_PROXY)  -- see step 4
   QoQ Revenue % = DIVIDE([Total Revenue] - [Revenue Prior Quarter], [Revenue Prior Quarter])
4. Prior quarter without a date table, use this instead:
   Revenue Prior Quarter = CALCULATE([Total Revenue], FILTER(ALL(mart_game_quarterly[quarter]), mart_game_quarterly[quarter] = MAX(mart_game_quarterly[quarter]) - 1))
5. Visuals
   - Clustered column: axis = quarter, values = Total Revenue, legend = genre
   - Table: title, quarter, Total Revenue, QoQ Revenue %. Conditional formatting: red when QoQ Revenue % < -0.15 (matches the alert rule)
   - Matrix: rows = region, columns = channel, values = Total Revenue (from mart_region_channel)
   - Bar: title by avg_active_players (from mart_engagement)
   - Card: Total Revenue
6. Save as game_warehouse.pbix, screenshot the page, add both to the repo.
Say the data is synthetic in the page title.
