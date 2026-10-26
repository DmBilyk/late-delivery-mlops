import pytest

from src.metrics import business_cost, evaluate

# Predicted late at 0.5: rows 0 and 2 -> 1 TP, 1 FP (row 2), 1 FN (row 1)
Y = [1, 1, 0, 0]
P = [0.9, 0.3, 0.6, 0.1]


def test_evaluate_known_values():
    m = evaluate(Y, P, threshold=0.5)
    assert m['recall_late'] == 0.5
    assert m['precision_late'] == 0.5
    assert m['pr_auc'] == pytest.approx(5 / 6)
    assert m['threshold'] == 0.5


def test_business_cost_known_values():
    cost = business_cost(Y, P, prices=[100, 100, 100, 100], threshold=0.5)
    assert cost['cost_fp'] == pytest.approx(1.5)
    assert cost['cost_fn'] == pytest.approx(20.0)
    assert cost['total'] == pytest.approx(21.5)
