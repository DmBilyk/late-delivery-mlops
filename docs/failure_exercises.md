# Failure exercises

Four things I broke on purpose on the AWS stack (EC2 + RDS + S3, eu-north-1), all on 2026-11-10. For each: what I did, what it looked like, why, and how I fixed it.

## 1. Bad model promoted, then rolled back

**What I did**

Trained a model with class weighting switched off (`scale_pos_weight: 1` instead of 17.57), promoted it to champion and scored August with it.

```bash
# laptop, MLflow on EC2 through the SSH tunnel
export MLFLOW_TRACKING_URI=http://127.0.0.1:5001
python train.py --config config_bad.yaml   # -> version 4
python -m src.registry promote 4           # champion v1 -> v4

# EC2
docker compose exec airflow airflow dags trigger score_monthly_batch -c '{"month": "2018-08"}'
docker compose restart api
```

**What happened**

| | v1 | v4 (bad) | After rollback |
|---|---|---|---|
| Recall, August | 0.796 | **0.008** | 0.796 |
| Precision, August | 0.092 | 0.188 | 0.092 |
| Alert "Recall dropped" | inactive | **firing** within a minute | inactive |
| API `/model-info` | v1 | v4 | v1 |

On the dashboard the recall bar for 2018-08 fell to almost zero.

**Why**

Only ~6% of orders are late. Without class weighting the model almost never scores above the 0.405 threshold. MLflow already showed it before promotion: val recall 0.012 against 0.80 for v1. I just didn't look.

**Fix**

```bash
python -m src.registry rollback   # champion v4 -> v1
# then rescore August and restart the API, same commands as above
```

Rollback is one alias change, and v4 stays in the registry for analysis. The alert resolved on its next evaluation.

**Takeaways**

- Moving the alias doesn't touch past predictions. The month has to be rescored, and the API restarted, because it loads the champion only at startup.
- `promote` should compare the candidate's val recall with the champion's and refuse a big drop.

## 2. Batch with a renamed column

**What I did**

Overwrote the July batch with `distance_km` renamed to `dist_km` and scored July again.

```bash
docker compose exec airflow bash -c "cd /opt/project && /opt/ml-venv/bin/python -m src.simulate batch 2018-07 --force --rename distance_km=dist_km"
docker compose exec airflow airflow dags trigger score_monthly_batch -c '{"month": "2018-07"}'
```

**What happened**

- `validate` failed on the first try, everything after it was `upstream_failed`.
- `batch_runs` got a failed run with `Missing columns: ['distance_km']`.
- In Grafana, "Failed / stuck batch runs" went from 0 to 1 and the "Batch failures" table showed the error.

Nothing bad got written: the latest successful July run, the 6156 July predictions in RDS and the July file in S3 all stayed as they were.

**Why**

The upstream file changed its schema. `validate` checks the columns before scoring, records the failed run and stops the DAG. It has no retries on purpose: a broken file won't fix itself, and retrying would only delay the alert.

**Fix**

```bash
docker compose exec airflow bash -c "cd /opt/project && /opt/ml-venv/bin/python -m src.simulate batch 2018-07 --force"
docker compose exec airflow airflow dags trigger score_monthly_batch -c '{"month": "2018-07"}'
```

The new run succeeded with the same 6156 predictions and replaced the S3 file.

**Takeaways**

- `predictions` keeps every run, so July now has two runs' worth of rows. The views read only the latest successful run per month, so metrics aren't doubled.
- The failure counter in Grafana stays at 1 after the fix. It's an incident history, not a "currently broken" flag.

## 3. Database outage

One RDS instance holds all three databases: `ml`, `airflow` and `mlflow`. If I stop RDS, Airflow can't record task states either, so retries can't be observed that way. So I did it in two parts.

### Part 1: only the `ml` database down

**What I did**

```sql
-- as the RDS master user, from the `postgres` database
ALTER DATABASE ml ALLOW_CONNECTIONS false;
```

Then triggered June.

**What happened**

- API: `/health` returned 503 `{"status":"unavailable","database":"down"}`; `/model-info` still returned 200, since the model is in memory.
- Airflow: `validate` passed (it doesn't need the database), `score` failed with `DatabaseUnavailable` and went to `up_for_retry`. Two attempts failed, one minute apart.

**Fix**

```sql
ALTER DATABASE ml ALLOW_CONNECTIONS true;
```

The third attempt of `score` succeeded by itself and the DAG finished. The failed attempts left no rows behind, because `score` fails on connect before it creates the batch run. `/health` went back to 200.

### Part 2: RDS stopped

**What I did**

```bash
aws rds stop-db-instance  --region eu-north-1 --db-instance-identifier late-delivery-db
aws rds start-db-instance --region eu-north-1 --db-instance-identifier late-delivery-db
```

**What happened** while RDS was down:

| Endpoint | Response |
|---|---|
| `/health` | 503 in 3.0 s |
| `/predict` | 503 `{"detail":"Database unavailable"}` in 3.1 s |
| `/model-info` | 200 |

The API process kept running, with no crash or restart loop; 3 s is the `connect_timeout` in `src/db.py`. Docker marked `airflow` and `api` as unhealthy. `mlflow` stayed "healthy" because its `/health` doesn't check the database, but registry calls hung.

**Why**

The API maps `psycopg.OperationalError` to `DatabaseUnavailable` and returns a clean 503 instead of a 500 with a stack trace.

**Fix**

Just start RDS. About 4 minutes after it was available, every container was healthy again, without restarting anything.

**Takeaways**

- Airflow, MLflow and my data share one RDS instance, which makes it a single point of failure. Fine here; in production Airflow metadata would usually get its own database.
- Don't restart the API while MLflow's database is down: it loads the champion at startup and won't come up until RDS is back.
- While RDS is stopped, scheduled DAG runs can't start.

## 4. EC2 destroyed and rebuilt

**What I did**

```bash
cd terraform
terraform plan -destroy -target=aws_instance.app   # check: only the instance
terraform destroy -target=aws_instance.app
terraform apply                                    # 1 to add
```

**What happened**

The machine and its IP were gone, the tunnel dropped, nothing was reachable. RDS stayed available and S3 kept all objects.

**Why**

On purpose: the EC2 instance is disposable. Data and Airflow/MLflow metadata are in RDS, artifacts and predictions in S3, secrets in SSM, code on GitHub.

**Fix**

`terraform apply` created a new instance, and the startup script did the rest:

| After instance creation | |
|---|---|
| ~1 min | SSH works |
| ~5 min | API healthy, champion v1 loaded from MLflow + S3, no retraining |
| ~6 min | Airflow healthy |

Everything checked before and after was identical: batch runs, predictions and labels in RDS; per-month recall for v1 (0.827, 0.601, 0.521, 0.688, 0.796); MLflow runs, versions and aliases; Airflow DAG run history; artifacts and prediction files in S3. `/predict` returned the same `p_late` (0.0920) for the same order as before the rebuild. Grafana came up with its datasource, dashboard and both alerts, and the DAG was still unpaused.

**Takeaways**

- Lost on purpose: batch and label input files on the EC2 disk (the simulator regenerates them) and local Docker volumes such as Grafana's alert history.
- The new instance has a new IP: take it from `terraform output tunnel` and remove the old host key with `ssh-keygen -R <old-ip>`.
- The rebuild clones `main`, so a fix that exists only on the old machine is lost. That's why the S3 endpoint fix had to be pushed before this exercise.