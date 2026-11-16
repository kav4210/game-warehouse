import sys,os; sys.path.insert(0,'src'); os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, pipeline, generate_raw
def setup_module(): generate_raw.generate()
def test_quality_checks_catch_injected_dirt():
    s=pd.read_csv('data/raw_sales.csv',keep_default_na=False); g=pd.read_csv('data/raw_games.csv',keep_default_na=False); i=pipeline.quality_checks(s,g)
    assert i['duplicate_sale_ids']==40 and i['negative_revenue']==25 and i['orphan_game_ids']>=1
def test_clean_removes_all_issues():
    s=pd.read_csv('data/raw_sales.csv',keep_default_na=False); g=pd.read_csv('data/raw_games.csv',keep_default_na=False); c=pipeline.clean(s,g)
    assert c.sale_id.is_unique and (c.revenue>=0).all() and c.game_id.isin(g.game_id).all()
def test_fact_revenue_reconciles_with_marts():
    pipeline.run(); import sqlite3; c=sqlite3.connect('data/warehouse.db')
    f=c.execute('SELECT ROUND(SUM(revenue),2) FROM fact_sales').fetchone()[0]
    m=c.execute('SELECT ROUND(SUM(revenue),2) FROM mart_game_quarterly').fetchone()[0]
    assert abs(f-m)<0.05
def test_no_orphan_foreign_keys():
    import sqlite3; c=sqlite3.connect('data/warehouse.db')
    for col,dim in [('game_key','dim_game'),('region_key','dim_region'),('channel_key','dim_channel'),('date_key','dim_date')]:
        n=c.execute(f'SELECT COUNT(*) FROM fact_sales f LEFT JOIN {dim} d ON f.{col}=d.{col} WHERE d.{col} IS NULL').fetchone()[0]
        assert n==0
def test_alert_fires_on_revenue_drop():
    import sqlite3; c=sqlite3.connect(':memory:')
    c.execute('CREATE TABLE mart_game_quarterly(title,genre,quarter,units,revenue)')
    c.executemany('INSERT INTO mart_game_quarterly VALUES(?,?,?,?,?)',[('A','X',1,1,1000),('A','X',2,1,600),('B','X',1,1,1000),('B','X',2,1,950)])
    a=pipeline.alerts(c,0.15); assert len(a)==1 and a[0]['title']=='A' and a[0]['change_pct']==-40.0
def test_lambda_handler_uploads_marts_to_s3(monkeypatch):
    import boto3; from moto import mock_aws; import lambda_handler
    with mock_aws():
        monkeypatch.setenv('AWS_DEFAULT_REGION','us-east-1'); monkeypatch.setenv('MART_BUCKET','test-bucket')
        monkeypatch.setenv('AWS_ACCESS_KEY_ID','x'); monkeypatch.setenv('AWS_SECRET_ACCESS_KEY','x')
        boto3.client('s3').create_bucket(Bucket='test-bucket')
        r=lambda_handler.handler({},None)
        assert len(r['uploaded'])==4
        got=[o['Key'] for o in boto3.client('s3').list_objects_v2(Bucket='test-bucket')['Contents']]
        assert sorted(got)==sorted(r['uploaded'])
