import numpy as np
from sklearn.metrics import average_precision_score, precision_score, recall_score


# Positive class is "late".
# FP: predicted late, actually on time -> unnecessary alert, 1.5% of order price.
# FN: predicted on time, actually late -> missed late order, 20% of order price.
COST_FP = 0.015
COST_FN = 0.20


def evaluate(y_late, p_late, threshold):
    y_late = np.asarray(y_late)
    p_late = np.asarray(p_late)
    y_pred = (p_late >= threshold).astype(int)
    return {
        'pr_auc': float(average_precision_score(y_late, p_late)),
        'recall_late': float(recall_score(y_late, y_pred, zero_division=0)),
        'precision_late': float(precision_score(y_late, y_pred, zero_division=0)),
        'threshold': float(threshold),
    }


def business_cost(y_late, p_late, prices, threshold):
    y_late = np.asarray(y_late)
    prices = np.asarray(prices)
    y_pred = (np.asarray(p_late) >= threshold).astype(int)

    cost_fp = (prices[(y_late == 0) & (y_pred == 1)] * COST_FP).sum()
    cost_fn = (prices[(y_late == 1) & (y_pred == 0)] * COST_FN).sum()
    return {'cost_fp': float(cost_fp), 'cost_fn': float(cost_fn), 'total': float(cost_fp + cost_fn)}


def find_cost_threshold(y_late, p_late, prices, grid=np.arange(0.01, 0.99, 0.005)):
    costs = [business_cost(y_late, p_late, prices, t)['total'] for t in grid]
    return float(grid[int(np.argmin(costs))])
