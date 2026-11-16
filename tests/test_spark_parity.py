import sys,os; sys.path.insert(0,'src'); os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, pytest, sqlite3
import generate_raw, pipeline
pyspark=pytest.importorskip("pyspark")
import spark_pipeline as sp

@pytest.fixture(scope="module")
def spark():
    generate_raw.generate(); pipeline.run()
    s=sp.get_spark(); yield s; s.stop()

def _marts(spark):
    sales,games,eng=sp.read_raw(spark); cs=sp.clean(sales,games); return sp.build_marts(cs,games,eng),sales,games,cs

def test_quality_counts_match_pandas(spark):
    _,sales,games,_=_marts(spark)
    s=pd.read_csv('data/raw_sales.csv',keep_default_na=False); g=pd.read_csv('data/raw_games.csv',keep_default_na=False)
    assert sp.quality_checks(sales,games)==pipeline.quality_checks(s,g)

def test_na_region_not_read_as_null(spark):
    _,sales,_,cs=_marts(spark)
    assert cs.filter("region IS NULL").count()==0 and cs.filter("region='NA'").count()>0

@pytest.mark.parametrize("name,keys",[("mart_game_quarterly",["title","quarter"]),("mart_region_channel",["region","channel"]),("mart_engagement",["title","region"])])
def test_mart_matches_sqlite(spark,name,keys):
    m,*_=_marts(spark); a=m[name].toPandas().sort_values(keys).reset_index(drop=True)
    b=pd.read_sql(f"SELECT * FROM {name}",sqlite3.connect('data/warehouse.db'),).sort_values(keys).reset_index(drop=True)
    assert len(a)==len(b)>0
    pd.testing.assert_frame_equal(a[b.columns],b,check_dtype=False,atol=0.011)

def test_alerts_match(spark):
    m,*_=_marts(spark); a=sp.alerts(m["mart_game_quarterly"])
    b=pipeline.alerts(sqlite3.connect('data/warehouse.db'))
    key=lambda x:(x['title'],x['quarter'])
    assert sorted(a,key=key)==sorted(b,key=key)
