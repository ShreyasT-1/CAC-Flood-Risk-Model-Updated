import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from pathlib import Path
from pandas.api.types import is_numeric_dtype, is_string_dtype
from sklearn.metrics import average_precision_score
from sklearn.metrics import (
    precision_score,
    recall_score,
    confusion_matrix
)

DATA_DIR = Path(r"C:\Flood Data Set\floodlens_final_dataset\ml_full_table")
files = sorted(DATA_DIR.rglob("*.parquet"))
print(f"Found {len(files)} parquet files.")

array = []
for file in files:
    df = pd.read_parquet(file)
    array.append(df)
data = pd.concat(array, ignore_index=True)

data.dropna(axis=0, subset=["exceed_next_6h"],inplace=True)
y = data["exceed_next_6h"]
X = data.drop(columns=[
            "exceed_next_1h",
            "exceed_next_2h",
            "exceed_next_3h",
            "exceed_next_4h",
            "exceed_next_5h",
            "exceed_next_6h",
            "exceed_next_7h",
            "exceed_next_8h",
            "exceed_next_9h",
            "exceed_next_10h",
            "exceed_next_11h",
            "exceed_next_12h",    
            "proxy_exceed_next_12h",
            "obs_stage_ft",
            "obs_q_cfs",
            "flood_stage_ft",
            "is_exceed_now",
            "split",
            "cv_fold",
            "event_id",
            "time_utc",
            "usgs_id",
            "feature_id",
        ])
X_train_full = X[(data["split"] == "trainval")&(data["cv_fold"] != 0)]
y_train = y.loc[X_train_full.index]

X_valid_full = X[(data["split"] == "trainval")&(data["cv_fold"] == 0)]
y_valid = y.loc[X_valid_full.index]

X_test_full = X[(data["split"] == "test")]
y_test = y.loc[X_test_full.index]

X_unseen_full = X[data["split"] == "unseen"]
y_unseen = y.loc[X_unseen_full.index]

#categorical_cols = [cname for cname in X_train_full.columns if is_string_dtype(X_train_full[cname])]
#numerical_cols = [cname for cname in X_train_full.columns if is_numeric_dtype(X_train_full[cname])]
my_cols = [
    "nwm_flow",
    "nwm_lag_1h",
    "nwm_lag_3h",
    "nwm_lag_6h",
    "nwm_lag_12h",
    "nwm_lag_24h",
    "nwm_chg_1h",
    "nwm_chg_3h",
    "nwm_chg_6h",
    "nwm_chg_12h",
    "nwm_chg_24h",
    "stream_order",
    "month",
]
categorical_cols = []
numerical_cols = my_cols.copy()

X_train = X_train_full[my_cols].copy()
X_valid = X_valid_full[my_cols].copy()
X_test = X_test_full[my_cols].copy()

#print(X_train.head())
# print(X_train_full.dtypes)
# print(my_cols)

numerical_transformer = SimpleImputer(strategy="mean")
categorical_transformer = Pipeline(steps=[
    ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
    ("onehot", OneHotEncoder(handle_unknown="ignore"))
])
preprocessor = ColumnTransformer(
    transformers=[
        ("num", numerical_transformer, numerical_cols),
        ("cat", categorical_transformer, categorical_cols)
    ]
)
model = XGBRegressor(
    n_estimators=200,
    learning_rate=0.1,
    random_state=0
)

pipeline = Pipeline(steps=[
    ("preprocessor", preprocessor),
    ("model", model)
])

pipeline.fit(X_train, y_train)


# --------------------------------------------------
# 6. Evaluate validation performance
# --------------------------------------------------

valid_predictions = pipeline.predict(X_valid)
for threshold in [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5]:
    predicted_classes = (valid_predictions >= threshold).astype(int)

    precision = precision_score(
        y_valid, predicted_classes, zero_division=0
    )
    recall = recall_score(
        y_valid, predicted_classes, zero_division=0
    )

    print(
        f"Threshold={threshold:.2f}, "
        f"Precision={precision:.4f}, "
        f"Recall={recall:.4f}"
    )

valid_mae = mean_absolute_error(
    y_valid, valid_predictions
)

valid_pr_auc = average_precision_score(
    y_valid, valid_predictions
)

print("\n--- Validation Results ---")
print(f"MAE: {valid_mae:.6f}")
print(f"PR-AUC: {valid_pr_auc:.6f}")
print(f"Flood rate: {y_valid.mean():.6f}")


# --------------------------------------------------
# 7. Evaluate precision, recall, and confusion matrix
# --------------------------------------------------

threshold = 0.5

valid_classes = (
    valid_predictions >= threshold
).astype(int)

precision = precision_score(
    y_valid, valid_classes, zero_division=0
)

recall = recall_score(
    y_valid, valid_classes, zero_division=0
)

tn, fp, fn, tp = confusion_matrix(
    y_valid,
    valid_classes,
    labels=[0, 1]
).ravel()

print("\n--- Validation Classification Results ---")
print(f"Threshold: {threshold}")
print(f"Precision: {precision:.6f}")
print(f"Recall: {recall:.6f}")
print(f"True negatives: {tn:,}")
print(f"False positives: {fp:,}")
print(f"False negatives: {fn:,}")
print(f"True positives: {tp:,}")