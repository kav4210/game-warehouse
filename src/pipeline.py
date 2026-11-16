"""Raw CSV -> data-quality gate -> star schema (SQLite) -> data marts -> alerts."""
import sqlite3, pandas as pd, json, os, sys
DB='data/warehouse.db'
def quality_checks(sales, games):
    issues={}
    issues['duplicate_sale_ids']=int(sales.sale_id.duplicated().sum())
    issues['negative_revenue']=int((sales.revenue<0).sum())
    issues['orphan_game_ids']=int((~sales.game_id.isin(games.game_id)).sum())
    return issues
def clean(sales, games):
    s=sales.drop_duplicates('sale_id')
    s=s[s.revenue>=0]; s=s[s.game_id.isin(games.game_id)]
    return s.reset_index(drop=True)
def build_warehouse(sales, games, eng, db=DB):
    if os.path.exists(db): os.remove(db)
    c=sqlite3.connect(db)
    dates=pd.date_range('2024-01-01','2024-12-31')
    dim_date=pd.DataFrame({'date_key':dates.strftime('%Y%m%d').astype(int),'full_date':dates.strftime('%Y-%m-%d'),
        'month':dates.month,'quarter':dates.quarter,'weekday':dates.day_name()})
    dim_game=games.rename(columns={'game_id':'game_key'})
    dim_region=pd.DataFrame({'region_key':[1,2,3,4],'region':['NA','EU','JP','OTHER']})
    dim_channel=pd.DataFrame({'channel_key':[1,2],'channel':['digital','retail']})
    rk=dict(zip(dim_region.region,dim_region.region_key)); ck=dict(zip(dim_channel.channel,dim_channel.channel_key))
    fact=pd.DataFrame({'sale_id':sales.sale_id,'date_key':pd.to_datetime(sales.sale_date).dt.strftime('%Y%m%d').astype(int),
        'game_key':sales.game_id,'region_key':sales.region.map(rk),'channel_key':sales.channel.map(ck),'units':sales.units,'revenue':sales.revenue})
    feng=pd.DataFrame({'date_key':pd.to_datetime(eng.play_date).dt.strftime('%Y%m%d').astype(int),'game_key':eng.game_id,
        'region_key':eng.region.map(rk),'active_players':eng.active_players,'avg_session_min':eng.avg_session_min})
    for n,df in [('dim_date',dim_date),('dim_game',dim_game),('dim_region',dim_region),('dim_channel',dim_channel),('fact_sales',fact),('fact_engagement',feng)]:
        df.to_sql(n,c,index=False)
    c.executescript(open('src/marts.sql').read()); c.commit(); return c
def alerts(c, drop_threshold=0.15):
    """Flag any game whose revenue fell >15% quarter over quarter."""
    q=pd.read_sql("SELECT title,quarter,revenue FROM mart_game_quarterly",c)
    out=[]
    for t,g in q.groupby('title'):
        g=g.sort_values('quarter').reset_index(drop=True)
        for i in range(1,len(g)):
            prev,cur=g.revenue[i-1],g.revenue[i]
            if prev>0 and (cur-prev)/prev<-drop_threshold:
                out.append({'title':t,'quarter':int(g.quarter[i]),'change_pct':round(100*(cur-prev)/prev,1)})
    return out
def run():
    games=pd.read_csv('data/raw_games.csv',keep_default_na=False); sales=pd.read_csv('data/raw_sales.csv',keep_default_na=False); eng=pd.read_csv('data/raw_engagement.csv',keep_default_na=False)
    issues=quality_checks(sales,games); print('data quality issues found:',issues)
    cleaned=clean(sales,games); print(f'rows in {len(sales)} -> rows loaded {len(cleaned)}')
    c=build_warehouse(cleaned,games,eng)
    for name in ['mart_game_quarterly','mart_region_channel','mart_engagement']:
        pd.read_sql(f'SELECT * FROM {name}',c).to_csv(f'data/{name}.csv',index=False)
    a=alerts(c); json.dump({'quality':issues,'alerts':a},open('data/alerts.json','w'),indent=2)
    print(f'{len(a)} QoQ revenue-drop alerts written to data/alerts.json')
if __name__=='__main__': run()
