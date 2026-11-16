"""Generate SYNTHETIC raw game sales + player engagement data (not real Nintendo data)."""
import numpy as np, pandas as pd, sys
def generate(seed=7, n_sales=20000, out='data'):
    r=np.random.default_rng(seed)
    games=pd.DataFrame({'game_id':range(1,13),
      'title':['Kart Racers','Brawl Arena','Puzzle Quest','Farm Life','Sky Pilots','Dungeon Crawl','Party Blast','Speed Run','Cozy Town','Hero Saga','Beat Rhythm','Block World'],
      'genre':['Racing','Fighting','Puzzle','Simulation','Action','RPG','Party','Racing','Simulation','RPG','Music','Sandbox'],
      'release_date':pd.date_range('2023-01-01',periods=12,freq='60D').strftime('%Y-%m-%d'),
      'list_price':[59.99,59.99,29.99,39.99,49.99,59.99,49.99,39.99,39.99,59.99,29.99,29.99]})
    regions=['NA','EU','JP','OTHER']; channels=['digital','retail']
    days=pd.date_range('2024-01-01','2024-12-31')
    rows=pd.DataFrame({'sale_id':range(1,n_sales+1),
      'game_id':r.integers(1,13,n_sales),'sale_date':r.choice(days.strftime('%Y-%m-%d'),n_sales),
      'region':r.choice(regions,n_sales,p=[.4,.3,.2,.1]),'channel':r.choice(channels,n_sales,p=[.6,.4]),
      'units':r.integers(1,4,n_sales)})
    rows['revenue']=(rows.units*rows.game_id.map(games.set_index('game_id').list_price)*r.choice([1,.85,.7],n_sales,p=[.7,.2,.1])).round(2)
    # inject realistic dirt for the quality checks to catch
    dup=rows.sample(40,random_state=1); rows=pd.concat([rows,dup],ignore_index=True)
    rows.loc[rows.sample(25,random_state=2).index,'revenue']=-1.0
    rows.loc[rows.sample(15,random_state=3).index,'game_id']=999
    eng=pd.DataFrame({'game_id':r.integers(1,13,6000),'play_date':r.choice(days.strftime('%Y-%m-%d'),6000),
      'region':r.choice(regions,6000),'active_players':r.integers(50,5000,6000),'avg_session_min':r.normal(48,12,6000).clip(5,180).round(1)})
    games.to_csv(f'{out}/raw_games.csv',index=False); rows.to_csv(f'{out}/raw_sales.csv',index=False); eng.to_csv(f'{out}/raw_engagement.csv',index=False)
if __name__=='__main__': generate()
