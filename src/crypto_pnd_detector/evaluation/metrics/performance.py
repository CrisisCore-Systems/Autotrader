"""Performance metric utilities used across backtesting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class ClassificationReport:
    precision: float
    recall: float
    f1: float


def classification_report(*, predictions: Sequence[int], labels: Sequence[int]) -> ClassificationReport:
    if len(predictions) != len(labels):
        raise ValueError("Predictions and labels must have equal length")
    true_positive = 0
    false_positive = 0
    false_negative = 0
    for prediction, label in zip(predictions, labels):
        if prediction == 1 and label == 1:
            true_positive += 1
        elif prediction == 1 and label == 0:
            false_positive += 1
        elif prediction == 0 and label == 1:
            false_negative += 1

    precision_denominator = true_positive + false_positive or 1
    recall_denominator = true_positive + false_negative or 1
    precision = true_positive / precision_denominator
    recall = true_positive / recall_denominator
    f1_denominator = precision + recall or 1
    f1 = 2 * precision * recall / f1_denominator
    return ClassificationReport(precision=float(precision), recall=float(recall), f1=float(f1))
