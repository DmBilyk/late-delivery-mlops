-- One row per attempt to score a monthly batch (reruns and backfills add rows).
CREATE TABLE IF NOT EXISTS batch_runs (
    run_id         SERIAL PRIMARY KEY,
    month          DATE NOT NULL,                 -- first day of the batch month
    model_name     TEXT NOT NULL,
    model_version  INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'success', 'failed')),
    n_rows         INTEGER,
    error          TEXT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_batch_runs_month ON batch_runs (month);

-- One row per scored order, from a batch run or from the API.
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id   BIGSERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('batch', 'api')),
    batch_run_id    INTEGER REFERENCES batch_runs (run_id),
    purchase_month  DATE,                         -- first day of the purchase month
    model_version   INTEGER NOT NULL,
    p_late          DOUBLE PRECISION NOT NULL CHECK (p_late BETWEEN 0 AND 1),
    predicted_late  BOOLEAN NOT NULL,
    threshold       DOUBLE PRECISION NOT NULL,
    predicted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- batch rows must have a run, api rows must not
    CHECK ((source = 'batch') = (batch_run_id IS NOT NULL)),
    -- a retry cannot insert the same order twice into one run (NULL run ids never clash)
    UNIQUE (batch_run_id, order_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_order_id ON predictions (order_id);
CREATE INDEX IF NOT EXISTS idx_predictions_month ON predictions (purchase_month);

-- True outcomes, loaded when the labels file arrives.
CREATE TABLE IF NOT EXISTS actuals (
    order_id        TEXT PRIMARY KEY,
    purchase_month  DATE NOT NULL,
    is_late         BOOLEAN NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
