import pandas as pd
import polars as pl
import io
import sys
import traceback

# Simulation of DataProcessingService._to_polars
def _to_polars(X):
    if isinstance(X, pl.DataFrame):
        return X
    if isinstance(X, pd.DataFrame):
        return pl.from_pandas(X)
    return pl.DataFrame(X)

def test_json_export():
    print("--- Testing JSON Export ---")
    
    # Create a dummy DataFrame with common types
    data = {
        "A": [1, 2, 3],
        "B": ["foo", "bar", "baz"],
        "C": [1.1, 2.2, 3.3],
        "D": [True, False, True]
    }
    df_pd = pd.DataFrame(data)
    df_pl = _to_polars(df_pd)
    
    try:
        print("Exporting to JSON...")
        output = io.BytesIO()
        df_pl.write_json(output)
        json_str = output.getvalue().decode('utf-8')
        print(f"Success! JSON content: {json_str}")
    except Exception as e:
        print("FAILED to export to JSON with Polars!")
        traceback.print_exc()

if __name__ == "__main__":
    test_json_export()
