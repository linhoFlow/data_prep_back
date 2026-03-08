import traceback, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app.services.data_processing_service import DataProcessingService

service = DataProcessingService()

files = [
    r"C:\Users\NDOUR\Desktop\data\property data.csv",
    r"C:\Users\NDOUR\Desktop\data\revenu.csv",
    r"C:\Users\NDOUR\Desktop\data\test_data_voluminous.json",
    r"C:\Users\NDOUR\Desktop\data\test_data_voluminous.xml",
]

for fp in files:
    fn = os.path.basename(fp)
    print(f"\n{'='*60}")
    print(f"  {fn}")
    print(f"{'='*60}")
    with open(fp, 'rb') as f:
        content = f.read()
    df, err = service.parse_file(content, fn)
    if err:
        print(f"  PARSE ERROR: {err}")
        continue
    print(f"  Shape: {df.shape}")
    print(f"  Dtypes: {dict(df.dtypes)}")

    # MCAR
    try:
        m = service.analyze_missing_data(df)
        print(f"  MCAR: {len(m)} cols with missing -> {[(k,v['type']) for k,v in m.items()]}")
    except Exception:
        traceback.print_exc()

    # Individual transforms
    nc = df.select_dtypes(include=['number']).columns.tolist()
    cc = df.select_dtypes(exclude=['number']).columns.tolist()
    if nc:

        c = nc[0]
        try:
            d = service.apply_transformation(df.copy(), 'min_max_scale', {'column': c})
            print(f"  MinMaxScaler({c}): OK min={d[c].min():.3f} max={d[c].max():.3f}")
        except Exception:
            traceback.print_exc()
    if cc:
        c = cc[0]
        try:
            d = service.apply_transformation(df.copy(), 'encode_onehot', {'column': c})
            print(f"  OneHotEncoder({c}): OK {len(df.columns)}->{len(d.columns)} cols")
        except Exception:
            traceback.print_exc()

    # Auto-Pilot
    try:
        df2, t = service.auto_pilot(df.copy())
        print(f"  AUTO-PILOT: OK {df.shape} -> {df2.shape}")
        for x in t:
            print(f"    {x}")
    except Exception:
        print(f"  AUTO-PILOT: FAILED")
        traceback.print_exc()

print("\nDONE")
