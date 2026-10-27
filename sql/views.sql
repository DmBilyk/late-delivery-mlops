-- Latest successful run per batch month. Reruns and backfills replace older runs here.
CREATE OR REPLACE VIEW v_latest_batch_runs AS
SELECT DISTINCT ON (month)
       run_id, month, model_name, model_version, n_rows, finished_at
FROM batch_runs
WHERE status = 'success'
ORDER BY month, run_id DESC;

-- Monthly quality of the latest run, measured on orders whose labels have arrived.
-- recall and precision are NULL until the labels of the month are loaded.
CREATE OR REPLACE VIEW v_monthly_metrics AS
WITH joined AS (
    SELECT r.month,
           r.run_id,
           r.model_version,
           p.predicted_late,
           a.order_id IS NOT NULL AS has_actual,
           a.is_late
    FROM v_latest_batch_runs r
    JOIN predictions p ON p.batch_run_id = r.run_id
    LEFT JOIN actuals a ON a.order_id = p.order_id
),
counts AS (
    SELECT month,
           run_id,
           model_version,
           count(*)                                                  AS n_predictions,
           count(*) FILTER (WHERE has_actual)                        AS n_with_actuals,
           count(*) FILTER (WHERE is_late)                           AS n_late,
           count(*) FILTER (WHERE has_actual AND predicted_late)     AS n_predicted_late,
           count(*) FILTER (WHERE is_late AND predicted_late)        AS n_true_positive
    FROM joined
    GROUP BY month, run_id, model_version
)
SELECT month,
       run_id,
       model_version,
       n_predictions,
       n_with_actuals,
       n_late,
       n_predicted_late,
       n_true_positive,
       round(n_true_positive::numeric / NULLIF(n_late, 0), 4)           AS recall_late,
       round(n_true_positive::numeric / NULLIF(n_predicted_late, 0), 4) AS precision_late,
       round(n_late::numeric / NULLIF(n_with_actuals, 0), 4)            AS actual_late_rate
FROM counts;

-- Histogram of p_late (10 buckets of width 0.1) per month, latest run only.
-- bucket 1 = [0.0, 0.1), ..., bucket 10 = [0.9, 1.0].
CREATE OR REPLACE VIEW v_prediction_distribution AS
SELECT r.month,
       LEAST(width_bucket(p.p_late, 0, 1, 10), 10) AS bucket,
       (LEAST(width_bucket(p.p_late, 0, 1, 10), 10) - 1) / 10.0 AS bucket_from,
       count(*) AS n_predictions
FROM v_latest_batch_runs r
JOIN predictions p ON p.batch_run_id = r.run_id
GROUP BY r.month, bucket
ORDER BY r.month, bucket;

-- Failed runs, and runs stuck in 'running' for more than an hour.
CREATE OR REPLACE VIEW v_batch_failures AS
SELECT run_id,
       month,
       model_version,
       status,
       error,
       started_at,
       finished_at
FROM batch_runs
WHERE status = 'failed'
   OR (status = 'running' AND started_at < now() - interval '1 hour')
ORDER BY started_at DESC;
