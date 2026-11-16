"""PySpark star-schema pipeline on REAL data (nycflights13, 336,776 flights).
Quality issues are measured and reported, and rows are KEPT: bad dimension keys map to 'unknown' members
(Kimball style) so no legitimate flight is silently dropped. Status column separates completed/cancelled/diverted."""
import json, os, sys
from pyspark.sql import SparkSession, Window, functions as F
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW, OUT = os.path.join(ROOT, "data", "flights_raw"), os.path.join(ROOT, "data", "flights_out")
UNKNOWN_PLANE = "UNKNOWN"

def get_spark():
    return (SparkSession.builder.master("local[2]").appName("flights-warehouse")
            .config("spark.sql.shuffle.partitions", "4").config("spark.ui.enabled", "false").getOrCreate())

def read(spark, raw=RAW):
    r = lambda n: spark.read.csv(os.path.join(raw, f"{n}.csv"), header=True, inferSchema=True, nullValue="")
    return {n: r(n) for n in ["flights", "airlines", "airports", "planes"]}

def quality_report(t):
    f, a, p = t["flights"], t["airports"], t["planes"]
    return {
        "total_flights": f.count(),
        "cancelled_no_dep_time": f.filter("dep_time IS NULL").count(),
        "diverted_or_unknown_no_arr_time": f.filter("dep_time IS NOT NULL AND arr_time IS NULL").count(),
        "missing_tailnum": f.filter("tailnum IS NULL").count(),
        "dest_not_in_airports": f.join(a.select(F.col("faa").alias("k")), f.dest == F.col("k"), "left_anti").count(),
        "tailnum_not_in_planes": f.filter("tailnum IS NOT NULL").join(p.select(F.col("tailnum").alias("k")), f.tailnum == F.col("k"), "left_anti").count(),
    }

def build_star(t):
    f, a, p, al = t["flights"], t["airports"], t["planes"], t["airlines"]
    status = (F.when(F.col("dep_time").isNull(), "cancelled")
               .when(F.col("arr_time").isNull(), "diverted").otherwise("completed"))
    # airports seen in flights but absent from the airports table become explicit 'unlisted' members
    seen = f.select(F.col("origin").alias("faa")).union(f.select(F.col("dest").alias("faa"))).distinct()
    missing = seen.join(a.select("faa"), "faa", "left_anti").withColumn("name", F.lit("Unlisted airport"))
    dim_airport = (a.select("faa", "name", "lat", "lon", "tzone").unionByName(missing, allowMissingColumns=True)
                   .withColumnRenamed("faa", "airport_key"))
    dim_carrier = al.withColumnRenamed("carrier", "carrier_key").withColumnRenamed("name", "carrier_name")
    dim_plane = (p.select("tailnum", "manufacturer", "model", "seats", F.col("year").alias("year_built"))
                 .withColumnRenamed("tailnum", "plane_key")
                 .unionByName(p.sparkSession.createDataFrame(
                     [(UNKNOWN_PLANE, "Unknown", "Unknown", None, None)], "plane_key string, manufacturer string, model string, seats int, year_built int")))
    fp = f.join(p.select(F.col("tailnum").alias("pk")), f.tailnum == F.col("pk"), "left")
    fp = fp.withColumn("plane_key", F.when(F.col("pk").isNotNull(), F.col("tailnum")).otherwise(F.lit(UNKNOWN_PLANE)))
    d = F.to_date(F.concat_ws("-", F.col("year"), F.lpad("month", 2, "0"), F.lpad("day", 2, "0")))
    fact = (fp.withColumn("flight_date", d).withColumn("status", status)
              .select(F.monotonically_increasing_id().alias("flight_id"),
                      F.date_format("flight_date", "yyyyMMdd").cast("int").alias("date_key"),
                      F.col("carrier").alias("carrier_key"), F.col("origin").alias("origin_key"),
                      F.col("dest").alias("dest_key"), "plane_key", "hour", "dep_delay", "arr_delay",
                      "air_time", "distance", "status"))
    dates = fact.select("date_key").distinct().withColumn("full_date", F.to_date(F.col("date_key").cast("string"), "yyyyMMdd"))
    dim_date = dates.select("date_key", "full_date", F.month("full_date").alias("month"),
                            F.quarter("full_date").alias("quarter"), F.date_format("full_date", "E").alias("weekday"))
    return {"dim_airport": dim_airport, "dim_carrier": dim_carrier, "dim_plane": dim_plane, "dim_date": dim_date, "fact_flights": fact}

def build_marts(s):
    fact, carrier, date = s["fact_flights"], s["dim_carrier"], s["dim_date"]
    done = fact.filter("status = 'completed'")
    carrier_perf = (fact.groupBy("carrier_key").agg(
        F.count("*").alias("flights"),
        F.round(F.avg(F.when(F.col("status") == "cancelled", 1.0).otherwise(0.0)) * 100, 2).alias("cancel_pct"),
        F.round(F.avg(F.when(F.col("status") == "completed", F.col("dep_delay"))), 2).alias("avg_dep_delay"),
        F.round(F.avg(F.when(F.col("status") == "completed", F.when(F.col("arr_delay") <= 15, 1.0).otherwise(0.0))) * 100, 2).alias("on_time_arrival_pct"))
        .join(carrier, "carrier_key").orderBy("avg_dep_delay"))
    om = (done.join(date, "date_key").groupBy("origin_key", "month")
          .agg(F.count("*").alias("flights"), F.round(F.avg("dep_delay"), 2).alias("avg_dep_delay")))
    w = Window.partitionBy("origin_key").orderBy("month").rowsBetween(-2, 0)
    origin_monthly = om.withColumn("rolling_3mo_avg_dep_delay", F.round(F.avg("avg_dep_delay").over(w), 2))
    route = (done.groupBy("origin_key", "dest_key").agg(F.count("*").alias("flights"), F.round(F.avg("arr_delay"), 2).alias("avg_arr_delay"))
             .filter("flights >= 500"))
    rw = Window.partitionBy("origin_key").orderBy(F.col("avg_arr_delay").desc())
    route_rank = route.withColumn("delay_rank_in_origin", F.dense_rank().over(rw))
    hour = (done.groupBy("hour").agg(F.count("*").alias("flights"), F.round(F.avg("dep_delay"), 2).alias("avg_dep_delay")).orderBy("hour"))
    return {"mart_carrier_performance": carrier_perf, "mart_origin_monthly": origin_monthly,
            "mart_route_delay": route_rank, "mart_hourly_delay": hour}

def run(raw=RAW, out=OUT):
    spark = get_spark(); t = read(spark, raw)
    q = quality_report(t); print("quality report:", json.dumps(q))
    s = build_star(t); m = build_marts(s)
    os.makedirs(out, exist_ok=True)
    for name, df in {**s, **m}.items():
        df.coalesce(1).write.mode("overwrite").option("header", True).csv(os.path.join(out, name))
    json.dump(q, open(os.path.join(out, "quality.json"), "w"), indent=2)
    print("fact rows:", s["fact_flights"].count()); spark.stop()

if __name__ == "__main__": run()
