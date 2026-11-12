
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "training_data.csv"

SAMPLE_COUNT = 4000
RANDOM_SEED = 42


def generate_dataset():
    """Генерує синтетичний набір даних для навчання Random Forest."""

    rng = np.random.default_rng(RANDOM_SEED)

    # Рівень пріоритету:
    # LOW=1, MEDIUM=2, HIGH=3, CRITICAL=4
    priority_level = rng.choice(
        [1, 2, 3, 4],
        size=SAMPLE_COUNT,
        p=[0.18, 0.37, 0.30, 0.15]
    )

    days_until_deadline = rng.uniform(
        0.25, 21, SAMPLE_COUNT
    )

    estimated_duration_hours = np.clip(
        rng.gamma(2.2, 2.0, SAMPLE_COUNT),
        0.25,
        24
    )

    active_tasks_count = np.clip(
        rng.poisson(4, SAMPLE_COUNT),
        0,
        18
    )

    on_time_completion_rate = rng.beta(
        5, 3, SAMPLE_COUNT
    )

    task_age_days = rng.uniform(
        0, 14, SAMPLE_COUNT
    )

    # Симуляційна модель формування ймовірності прострочення.
    # Це правило генерації навчальних міток, не готова ML-модель.
    logit = (
        -1.7
        + 0.17 * estimated_duration_hours
        - 0.15 * days_until_deadline
        + 0.11 * active_tasks_count
        + 2.4 * (0.65 - on_time_completion_rate)
        + 0.06 * task_age_days
        - 0.10 * (priority_level - 2)
    )

    overdue_probability = 1 / (1 + np.exp(-logit))

    # Випадкова симуляція фактичного результату виконання.
    will_be_overdue = rng.binomial(
        1,
        overdue_probability
    )

    dataset = pd.DataFrame({
        "priority_level": priority_level,
        "days_until_deadline": days_until_deadline,
        "estimated_duration_hours": estimated_duration_hours,
        "active_tasks_count": active_tasks_count,
        "on_time_completion_rate": on_time_completion_rate,
        "task_age_days": task_age_days,
        "will_be_overdue": will_be_overdue
    })

    # Округлення числових ознак.
    numeric_columns = [
        "days_until_deadline",
        "estimated_duration_hours",
        "on_time_completion_rate",
        "task_age_days"
    ]

    dataset[numeric_columns] = dataset[numeric_columns].round(3)

    dataset.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8"
    )

    print("=== SMARTTASK TRAINING DATA ===")
    print(f"Dataset: {OUTPUT_PATH}")
    print(f"Total records: {len(dataset)}")

    print("\nTarget distribution:")
    print(dataset["will_be_overdue"].value_counts())

    print("\nTarget percentages:")
    print(
        dataset["will_be_overdue"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )

    print("\nMissing values:")
    print(dataset.isnull().sum())

    print("\nDataset generated successfully!")


if __name__ == "__main__":
    generate_dataset()
