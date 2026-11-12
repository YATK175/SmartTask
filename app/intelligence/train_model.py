
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    fbeta_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    classification_report,
    precision_recall_curve,
)
from sklearn.model_selection import train_test_split


BASE_DIR = Path(__file__).resolve().parents[2]

DATA_PATH = BASE_DIR / "ml_data" / "training_data.csv"

ARTIFACT_DIR = (
    BASE_DIR / "app" / "intelligence" / "artifacts"
)

MODEL_PATH = ARTIFACT_DIR / "task_risk_model.joblib"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"

MODEL_VERSION = "rf-synthetic-v2"

FEATURE_COLUMNS = [
    "priority_level",
    "days_until_deadline",
    "estimated_duration_hours",
    "active_tasks_count",
    "on_time_completion_rate",
    "task_age_days",
]

TARGET_COLUMN = "will_be_overdue"


def select_threshold(y_true, probabilities):
    """Підбирає поріг класифікації за максимальним F2-score."""

    precision, recall, thresholds = precision_recall_curve(
        y_true,
        probabilities
    )

    if len(thresholds) == 0:
        raise ValueError(
            "Недостатньо даних для підбору порогу."
        )

    # F2 більше враховує повноту виявлення прострочень.
    beta_squared = 4

    f2_scores = (
        (1 + beta_squared)
        * precision[:-1]
        * recall[:-1]
        / (
            beta_squared * precision[:-1]
            + recall[:-1]
            + 1e-12
        )
    )

    best_index = int(f2_scores.argmax())

    return (
        float(thresholds[best_index]),
        float(f2_scores[best_index])
    )


def train_model():
    """Навчає та оцінює модель Random Forest."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Датасет не знайдено: {DATA_PATH}"
        )

    dataset = pd.read_csv(DATA_PATH)

    required_columns = FEATURE_COLUMNS + [TARGET_COLUMN]

    missing_columns = (
        set(required_columns) - set(dataset.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Відсутні колонки: {missing_columns}"
        )

    if dataset[required_columns].isnull().any().any():
        raise ValueError(
            "Датасет містить порожні значення."
        )

    X = dataset[FEATURE_COLUMNS]
    y = dataset[TARGET_COLUMN].astype(int)

    if set(y.unique()) != {0, 1}:
        raise ValueError(
            "Цільова змінна повинна містити класи 0 та 1."
        )

    # 20% відразу відкладаємо для фінального тестування.
    X_train_val, X_test, y_train_val, y_test = (
        train_test_split(
            X,
            y,
            test_size=0.20,
            random_state=42,
            stratify=y
        )
    )

    # Із решти 80% виділяємо 25% для validation.
    # У результаті: train 60%, validation 20%, test 20%.
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val,
        y_train_val,
        test_size=0.25,
        random_state=42,
        stratify=y_train_val
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=3,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1
    )

    # Навчання тільки на train.
    model.fit(X_train, y_train)

    # Підбір порогу на validation.
    overdue_index = list(model.classes_).index(1)

    val_probabilities = model.predict_proba(
        X_val
    )[:, overdue_index]

    best_threshold, validation_f2 = select_threshold(
        y_val,
        val_probabilities
    )

    # Фінальне тестування на невикористаних test-даних.
    test_probabilities = model.predict_proba(
        X_test
    )[:, overdue_index]

    predictions = (
        test_probabilities >= best_threshold
    ).astype(int)

    # Основні метрики.
    metrics = {
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "dataset_type": "synthetic",
        "dataset_records": int(len(dataset)),
        "training_records": int(len(X_train)),
        "validation_records": int(len(X_val)),
        "test_records": int(len(X_test)),
        "classification_threshold": round(
            best_threshold,
            4
        ),
        "validation_f2_score": round(
            validation_f2,
            4
        ),
        "accuracy": round(
            accuracy_score(y_test, predictions),
            4
        ),
        "precision": round(
            precision_score(
                y_test,
                predictions,
                zero_division=0
            ),
            4
        ),
        "recall": round(
            recall_score(
                y_test,
                predictions,
                zero_division=0
            ),
            4
        ),
        "f1_score": round(
            f1_score(
                y_test,
                predictions,
                zero_division=0
            ),
            4
        ),
        "f2_score": round(
            fbeta_score(
                y_test,
                predictions,
                beta=2,
                zero_division=0
            ),
            4
        ),
        "roc_auc": round(
            roc_auc_score(
                y_test,
                test_probabilities
            ),
            4
        ),
        "average_precision": round(
            average_precision_score(
                y_test,
                test_probabilities
            ),
            4
        ),
        "confusion_matrix": confusion_matrix(
            y_test,
            predictions,
            labels=[0, 1]
        ).tolist(),
        "feature_importance": {
            feature: round(
                float(importance),
                4
            )
            for feature, importance in zip(
                FEATURE_COLUMNS,
                model.feature_importances_
            )
        }
    }

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Зберігаємо модель разом із порогом класифікації.
    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "threshold": best_threshold,
            "model_version": MODEL_VERSION,
            "dataset_type": "synthetic"
        },
        MODEL_PATH
    )

    with open(
        METRICS_PATH,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            metrics,
            file,
            ensure_ascii=False,
            indent=4
        )

    print("\n=== SMARTTASK RANDOM FOREST V2 ===")
    print(f"Dataset records: {len(dataset)}")
    print(f"Train: {len(X_train)}")
    print(f"Validation: {len(X_val)}")
    print(f"Test: {len(X_test)}")

    print("\n=== CLASSIFICATION THRESHOLD ===")
    print(f"Selected threshold: {best_threshold:.4f}")
    print(f"Validation F2-score: {validation_f2:.4f}")

    print("\n=== FINAL TEST METRICS ===")
    print(f"Accuracy:           {metrics['accuracy']:.4f}")
    print(f"Precision:          {metrics['precision']:.4f}")
    print(f"Recall:             {metrics['recall']:.4f}")
    print(f"F1-score:           {metrics['f1_score']:.4f}")
    print(f"F2-score:           {metrics['f2_score']:.4f}")
    print(f"ROC-AUC:            {metrics['roc_auc']:.4f}")
    print(f"Average Precision:  {metrics['average_precision']:.4f}")

    print("\n=== CONFUSION MATRIX ===")
    print("[[TN, FP], [FN, TP]]")
    print(metrics["confusion_matrix"])

    print("\n=== CLASSIFICATION REPORT ===")
    print(
        classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["On-time", "Overdue"],
            zero_division=0
        )
    )

    print("\n=== FEATURE IMPORTANCE ===")

    for feature, importance in metrics[
        "feature_importance"
    ].items():
        print(f"{feature}: {importance:.4f}")

    print(f"\nModel saved: {MODEL_PATH}")
    print(f"Metrics saved: {METRICS_PATH}")
    print("\nModel training completed!")


if __name__ == "__main__":
    train_model()
