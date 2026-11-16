# Game Sales and Engagement Warehouse

A synthetic star-schema warehouse built two ways (pandas + SQLite, and PySpark), with a data-quality gate, three marts, QoQ revenue-drop alerts, an R statistics layer, a Plotly Dash dashboard, an AWS Lambda handler, and container/Kubernetes manifests. **All data is generated, not real.**

![dashboard](docs/dashboard.png)

## Layout
| Path | What it does |
|---|---|
| `src/generate_raw.py` | Generates raw sales/games/engagement CSVs with injected dirt (40 duplicate IDs, 25 negative revenues, orphan keys) |
| `src/pipeline.py` | pandas + SQLite pipeline: quality gate, star schema, marts, alerts |
| `src/spark_pipeline.py` | PySpark version of the same logic (window functions for dedupe and QoQ lag) |
| `tests/test_spark_parity.py` | Proves Spark marts and alerts match the SQLite marts |
| `analysis/revenue_stats.R` | Base R: Welch t-test, ANOVA + Tukey, linear model with game fixed effects, chi-square on counts |
| `dashboard/app.py` | Plotly Dash dashboard over the marts |
| `src/lambda_handler.py` | Lambda that runs the pipeline and uploads marts to S3 (tested with moto) |
| `src/flights/` | Real-data PySpark star schema on NYC flights 2013 (see section below) |
| `dbt_project/` | dbt models and tests over the marts |
| `agent/` | Tool-calling analytics agent (SQL + doc search); evaluation needs your own API key |
| `Dockerfile`, `k8s/cronjob.yaml` | Container image, nightly CronJob, dashboard Deployment |

## Run it
```
pip install -r requirements.txt
python src/generate_raw.py && python src/pipeline.py      # pandas + SQLite
python src/spark_pipeline.py                              # PySpark (needs Java 17+; tested on 21)
Rscript analysis/revenue_stats.R                          # stats
python dashboard/app.py                                   # http://localhost:8050
pytest tests
```

Docker and Kubernetes (verified on Windows with Docker Desktop):
```
docker build -t game-warehouse:latest .
docker run --rm game-warehouse:latest                                          # PySpark pipeline
docker run --rm -p 8050:8050 game-warehouse:latest python dashboard/app.py     # dashboard
```

## Findings from the R analysis (synthetic data, so read as a demo of method)
- Revenue per unit does not differ by channel (Welch t-test p = 0.63).
- Genre explains quarterly revenue (ANOVA p < 1e-12); Tukey shows RPG and Fighting at the top.
- Quarterly trend is not significant after game fixed effects (slope 462 per quarter, p = 0.09).
- Channel mix is independent of region (chi-square on transaction counts, p = 0.42). A first version ran chi-square on revenue dollars and reported p < 2e-16, which is wrong because it treats each dollar as an observation. Fixed to use counts.

## Real-data pipeline: NYC flights (src/flights/)
The synthetic warehouse above is a method demo. This is the same approach on **real data**: all 336,776 flights out of EWR, JFK and LGA in 2013 (US Bureau of Transportation Statistics, via the `nycflights13` package), built as a PySpark star schema with 5 tables (fact_flights, dim_carrier, dim_airport, dim_plane, dim_date) and 4 marts.

```
python src/flights/ingest.py          # exports the real dataset to data/flights_raw/ (not committed)
python src/flights/flights_spark.py   # quality report, star schema, marts -> data/flights_out/
pytest tests/test_flights.py          # 6 tests, verified against independently computed pandas numbers
```

**Real data quality problems found and how they were handled** (measured, then rows kept, not dropped):
| Issue | Rows | Handling |
|---|---|---|
| Cancelled flights (no departure time) | 8,255 | `status = cancelled`, excluded from delay metrics, included in cancel rate |
| Diverted or unknown (departed, no arrival time) | 458 | `status = diverted` |
| Missing tail number | 2,512 | mapped to an `UNKNOWN` plane member |
| Destination not in the airports table (SJU, BQN, PSE, STT) | 7,602 | added as explicit "Unlisted airport" dimension members instead of dropping real flights |
| Tail number not in the planes table | 50,094 | mapped to the `UNKNOWN` plane member |

**What the marts show** (completed flights, 2013):
- Delays build through the day: average departure delay is 0.7 min for 5am flights and 24.7 min for 7pm flights.
- Regional carriers cancel the most: Endeavor Air 5.7%, ExpressJet 5.2%, Envoy 4.7% of flights, versus 0.7% for Delta. (SkyWest and Mesa show higher rates on tiny samples of 32 and 601 flights.)
- On-time arrival among carriers with over 1,000 flights: best is US Airways at 82.0%, then Virgin America 81.8% and Delta 81.6%. Worst is ExpressJet at 68.5%.
- EWR monthly delays peak in June and July (about 22 min) and bottom out in November (6.7 min); the mart includes a 3-month rolling average via a window function.

Caveat: this is one year (2013) from three airports, and on-time means arrival within 15 minutes of schedule (the BTS definition). It is a descriptive analysis, not a causal one.

## Bugs found while building
- pandas and Spark both treat the region code `NA` (North America) as missing by default. In pandas this broke 7,960 foreign keys. Fixed with `keep_default_na=False` in pandas and a sentinel `nullValue` in Spark, covered by tests.
- Spark's `dropDuplicates` keeps an arbitrary row, which would not match pandas. Replaced with `row_number()` over file order.

## Honest status
- Verified (cloud sandbox): pandas pipeline, PySpark pipeline and parity (local mode), R script, dashboard renders, Lambda handler against moto, YAML parses.
- Verified in Docker Desktop (Windows): the image builds, `docker run` executes the PySpark pipeline with the expected output (20,040 rows in, 19,960 loaded), and the dashboard container serves the charts at localhost:8050.
- Verified on a local Kubernetes cluster (Docker Desktop): the manifests in `k8s/` applied, the nightly CronJob was triggered manually and ran the PySpark pipeline, and the dashboard Deployment served the charts via `kubectl port-forward`. Debugged an `ImagePullBackOff` caused by a missing `imagePullPolicy: IfNotPresent` on the Deployment (`:latest` tags default to Always-pull). **Not run on a managed cloud cluster (EKS/GKE).**
- Not deployed to real AWS. Not run on Snowflake. The agent evaluation has not been run with a real API key.
