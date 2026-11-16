"""PySpark version of the warehouse pipeline: raw CSV -> quality gate -> star schema -> marts.
Same business logic as src/pipeline.py (pandas + SQLite). tests/test_spark_parity.py proves the marts match."""
import json, sys
from pyspark.sql import SparkSession, Window, functions as F

def get_spark(master="local[2]"):
    return (SparkSession.builder.master(master).appName("game-warehouse")
            .config("spark.sql.shuffle.partitions", "4").config("spark.ui.enabled", "false").getOrCreate())

def read_raw(spark, d="data"):
    # nullValue is set to a sentinel so region code "NA" (North America) is never read as missing
    opts = dict(header=True, inferSchema=True, nullValue="__NULL__")
    return (spark.read.csv(f"{d}/raw_sales.csv", **opts), spark.read.csv(f"{d}/raw_games.csv", **opts),
            spark.read.csv(f"{d}/raw_engagement.csv", **opts))

def quality_checks(sales, games):
    dup = sales.count() - sales.dropDuplicates(["sale_id"]).count()
    neg = sales.filter(F.col("revenue") < 0).count()
    orphan = sales.join(games.select(F.col("game_id").alias("g")), sales.game_id == F.col("g"), "left_anti").count()
    return {"duplicate_sale_ids": dup, "negative_revenue": neg, "orphan_game_ids": orphan}

def clean(sales, games):
    # keep the FIRST occurrence of each sale_id in file order, matching pandas drop_duplicates
    w = Window.partitionBy("sale_id").orderBy("_ord")
    s = sales.withColumn("_ord", F.monotonically_increasing_id())
    s = s.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn", "_ord")
    s = s.filter(F.col("revenue") >= 0)
    return s.join(games.select(F.col("game_id").alias("_g")), s.game_id == F.col("_g"), "left_semi")

def build_marts(sales_clean, games, eng):
    q = F.quarter(F.to_date("sale_date"))
    game_q = (sales_clean.join(games, "game_id").withColumn("quarter", q)
              .groupBy("title", "genre", "quarter")
              .agg(F.sum("units").alias("units"), F.round(F.sum("revenue"), 2).alias("revenue")))
    reg_ch = (sales_clean.groupBy("region", "channel")
              .agg(F.sum("units").alias("units"), F.round(F.sum("revenue"), 2).alias("revenue")))
    engm = (eng.join(games, "game_id")
            .groupBy("title", "region")
            .agg(F.round(F.avg("active_players"), 1).alias("avg_active_players"),
                 F.round(F.avg("avg_session_min"), 1).alias("avg_session_min")))
    return {"mart_game_quarterly": game_q, "mart_region_channel": reg_ch, "mart_engagement": engm}

def alerts(game_q, drop=0.15):
    w = Window.partitionBy("title").orderBy("quarter")
    d = game_q.withColumn("prev", F.lag("revenue").over(w))
    d = d.withColumn("chg", (F.col("revenue") - F.col("prev")) / F.col("prev"))
    rows = d.filter((F.col("prev") > 0) & (F.col("chg") < -drop)).collect()
    return [{"title": r.title, "quarter": int(r.quarter), "change_pct": round(100 * r.chg, 1)} for r in rows]

def run(d="data", out="data/spark_out"):
    spark = get_spark()
    sales, games, eng = read_raw(spark, d)
    issues = quality_checks(sales, games); print("data quality issues found:", issues)
    cs = clean(sales, games).cache(); print(f"rows in {sales.count()} -> rows loaded {cs.count()}")
    marts = build_marts(cs, games, eng)
    for n, df in marts.items():
        df.coalesce(1).write.mode("overwrite").option("header", True).csv(f"{out}/{n}")
    a = alerts(marts["mart_game_quarterly"])
    json.dump({"quality": issues, "alerts": a}, open(f"{out}/alerts.json", "w"), indent=2)
    print(f"{len(a)} QoQ revenue-drop alerts"); spark.stop()

if __name__ == "__main__": run()
