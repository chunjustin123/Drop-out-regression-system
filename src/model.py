from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import argparse
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

from .ingestion import load_inputs, fuse_student_level_dataset


MODEL_PATH = Path("artifacts/model.pkl")
FEATURES = [
    "attendance_rate",
    "avg_score",
    "balance_outstanding",
]


@dataclass
class TrainConfig:
    inputs_dir: Path
    label_column: str = "dropout_risk"  # expected in a labels.csv per student_id


def _ensure_dirs():
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_labels(inputs_dir: Path, label_column: str) -> pd.DataFrame:
    labels_path = inputs_dir / "labels.csv"
    if not labels_path.exists():
        # Synthesize a simple label if none exists: higher risk with low attendance, low score, high balance
        df = fuse_student_level_dataset(load_inputs(inputs_dir))
        df[label_column] = (
            (1 - df["attendance_rate"]) * 0.5 + (100 - df["avg_score"]) / 100 * 0.3 + (df["balance_outstanding"] > 0).astype(int) * 0.2
        )
        return df[["student_id", label_column]].copy()
    lab = pd.read_csv(labels_path)
    return lab[["student_id", label_column]].copy()


def train(inputs_dir: Path, label_column: str = "dropout_risk") -> float:
    _ensure_dirs()
    inputs = load_inputs(inputs_dir)
    X = fuse_student_level_dataset(inputs)
    y = load_labels(inputs_dir, label_column)

    df = X.merge(y, on="student_id", how="inner").copy()
    X_train, X_test, y_train, y_test = train_test_split(
        df[FEATURES], df[label_column], test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)

    joblib.dump(model, MODEL_PATH)
    return mae


def predict(inputs_dir: Path) -> pd.DataFrame:
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Model not trained. Run training first.")

    model = joblib.load(MODEL_PATH)
    inputs = load_inputs(inputs_dir)
    X = fuse_student_level_dataset(inputs)
    risk_score = model.predict(X[FEATURES])
    out = X[["student_id"]].copy()
    out["model_risk_score"] = risk_score
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=str, help="Path to inputs directory to train.")
    parser.add_argument("--predict", type=str, help="Path to inputs directory to predict.")
    parser.add_argument("--label", type=str, default="dropout_risk", help="Label column name.")
    args = parser.parse_args()

    if args.train:
        mae = train(Path(args.train), label_column=args.label)
        print(f"Trained. MAE={mae:.4f}")
    if args.predict:
        df = predict(Path(args.predict))
        print(df.head().to_string(index=False))
