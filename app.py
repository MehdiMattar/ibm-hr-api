import pandas as pd
from fastapi import FastAPI, Query, HTTPException
from enum import Enum

app = FastAPI(
    title="IBM HR API",
    description="An API for exploring IBM HR data.",
    version="1.0.0",
)

DATA_URL = (
    "https://full-stack-assets.s3.eu-west-3.amazonaws.com/"
    "Deployment/ibm_hr_attrition.xlsx"
)

df = pd.read_excel(DATA_URL)
ColumnName = Enum(
    "ColumnName",
    {column: column for column in df.columns},
    type=str,
)

@app.get("/", tags=["Introduction"])
def home():
    """Check that the API is running."""
    return {"message": "Welcome to the IBM HR API"}


@app.get("/preview", tags=["Data exploration"])
def preview(rows: int = Query(default=5, ge=1, le=100)):
    """Return the first rows of the dataset, between 1 and 100."""
    # Convert to JSON-compatible records, including null for missing values.
    import json
    return json.loads(df.head(rows).to_json(orient="records"))

@app.get("/unique-values", tags=["Data exploration"])
def unique_values(column: ColumnName):
    """Select a column to retrieve its distinct values."""
    import json

    selected_column = column.value
    values = df[selected_column].drop_duplicates()

    return {
        "column": selected_column,
        "values": json.loads(values.to_json(orient="values")),
    }

class Aggregation(str, Enum):
    mean = "mean"
    sum = "sum"
    min = "min"
    max = "max"


@app.get("/groupby", tags=["Data exploration"])
def groupby(
    column: ColumnName,
    value_column: ColumnName,
    metric: Aggregation = Aggregation.mean,
):
    """Group by a column and aggregate a chosen numeric column."""
    import json

    group_column = column.value
    numeric_column = value_column.value

    if group_column == numeric_column:
        raise HTTPException(
            status_code=400,
            detail="Choose different grouping and value columns.",
        )

    if not pd.api.types.is_numeric_dtype(df[numeric_column]):
        raise HTTPException(
            status_code=400,
            detail="The value column must be numeric.",
        )

    result = (
        df.groupby(group_column, dropna=False)[numeric_column]
        .agg(metric.value)
        .reset_index()
    )

    return json.loads(result.to_json(orient="records"))

@app.get("/filter-by", tags=["Data exploration"])
def filter_by(
    column: ColumnName,
    categories: list[str] = Query(...),
):
    """Return rows matching any of the supplied categories in one column."""
    import json

    selected_column = column.value

    mask = df[selected_column].astype(str).isin(categories)
    result = df.loc[mask]

    return json.loads(result.to_json(orient="records"))

class Direction(str, Enum):
    top = "top"
    bottom = "bottom"


@app.get("/quantile", tags=["Data exploration"])
def quantile(
    column: ColumnName,
    percentage: float = Query(default=10, gt=0, le=100),
    direction: Direction = Direction.top,
):
    """Return rows at or beyond the chosen percentile threshold."""
    import json

    selected_column = column.value
    values = df[selected_column]

    if not pd.api.types.is_numeric_dtype(values):
        raise HTTPException(
            status_code=400,
            detail="Choose a numeric column.",
        )

    fraction = percentage / 100

    if direction == Direction.top:
        threshold = values.quantile(1 - fraction)
        result = df.loc[values >= threshold]
    else:
        threshold = values.quantile(fraction)
        result = df.loc[values <= threshold]

    return json.loads(result.to_json(orient="records"))