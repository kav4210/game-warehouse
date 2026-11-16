import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "src", "flights"))
import pytest
pd = pytest.importorskip("pandas"); pytest.importorskip("pyspark"); nf = pytest.importorskip("nycflights13")
import ingest, flights_spark as fs

@pytest.fixture(scope="module")
def built():
    ingest.export(); spark = fs.get_spark(); t = fs.read(spark)
    s = fs.build_star(t); m = fs.build_marts(s); yield t, s, m; spark.stop()

def test_quality_report_matches_independent_pandas(built):
    t, *_ = built; f, a, p = nf.flights, nf.airports, nf.planes; q = fs.quality_report(t)
    assert q["total_flights"] == len(f)
    assert q["cancelled_no_dep_time"] == int(f.dep_time.isna().sum())
    assert q["diverted_or_unknown_no_arr_time"] == int((f.dep_time.notna() & f.arr_time.isna()).sum())
    assert q["missing_tailnum"] == int(f.tailnum.isna().sum())
    assert q["dest_not_in_airports"] == int((~f.dest.isin(a.faa)).sum())
    assert q["tailnum_not_in_planes"] == int((f.tailnum.notna() & ~f.tailnum.isin(p.tailnum)).sum())

def test_no_flights_dropped_and_status_partitions(built):
    _, s, _ = built; fact = s["fact_flights"].toPandas()
    assert len(fact) == len(nf.flights)
    assert fact.flight_id.is_unique
    assert fact.status.value_counts().to_dict() == {"completed": len(nf.flights) - 8255 - 458, "cancelled": 8255, "diverted": 458}

def test_every_foreign_key_resolves(built):
    _, s, _ = built; fact = s["fact_flights"].toPandas()
    keys = {"carrier_key": ("dim_carrier", "carrier_key"), "origin_key": ("dim_airport", "airport_key"),
            "dest_key": ("dim_airport", "airport_key"), "plane_key": ("dim_plane", "plane_key"), "date_key": ("dim_date", "date_key")}
    for col, (dim, k) in keys.items():
        dk = set(s[dim].toPandas()[k]); assert fact[col].notna().all(); assert set(fact[col]) <= dk, col

def test_unlisted_airports_kept_not_dropped(built):
    _, s, _ = built; da = s["dim_airport"].toPandas().set_index("airport_key")
    for code in ["SJU", "BQN", "PSE", "STT"]: assert da.loc[code, "name"] == "Unlisted airport"
    fact = s["fact_flights"].toPandas(); assert (fact.dest_key == "SJU").sum() == (nf.flights.dest == "SJU").sum()

def test_carrier_mart_matches_pandas(built):
    _, _, m = built; got = m["mart_carrier_performance"].toPandas().set_index("carrier_key")
    f = nf.flights; done = f[f.dep_time.notna() & f.arr_time.notna()]
    exp_delay = done.groupby("carrier").dep_delay.mean().round(2)
    exp_ontime = (done.assign(ok=done.arr_delay <= 15).groupby("carrier").ok.mean() * 100).round(2)
    exp_cancel = (f.assign(c=f.dep_time.isna()).groupby("carrier").c.mean() * 100).round(2)
    for c in exp_delay.index:
        assert got.loc[c, "avg_dep_delay"] == pytest.approx(exp_delay[c], abs=0.011)
        assert got.loc[c, "on_time_arrival_pct"] == pytest.approx(exp_ontime[c], abs=0.011)
        assert got.loc[c, "cancel_pct"] == pytest.approx(exp_cancel[c], abs=0.011)
    assert got.flights.sum() == len(f)

def test_hourly_mart_and_rolling_window(built):
    _, _, m = built; h = m["mart_hourly_delay"].toPandas().set_index("hour")
    f = nf.flights; done = f[f.dep_time.notna() & f.arr_time.notna()]
    assert h.loc[6, "avg_dep_delay"] == pytest.approx(done[done.hour == 6].dep_delay.mean(), abs=0.011)
    om = m["mart_origin_monthly"].toPandas().sort_values(["origin_key", "month"])
    jfk = om[om.origin_key == "JFK"].reset_index(drop=True)
    assert jfk.loc[5, "rolling_3mo_avg_dep_delay"] == pytest.approx(jfk.avg_dep_delay[3:6].mean(), abs=0.011)
    assert jfk.loc[0, "rolling_3mo_avg_dep_delay"] == pytest.approx(jfk.avg_dep_delay[0], abs=0.011)
