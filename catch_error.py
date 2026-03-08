import pandas as pd
from app.services.data_processing_service import DataProcessingService
import traceback

def run():
    try:
        csv_path = r'C:\Users\NDOUR\Desktop\data\property data.csv'
        df = pd.read_csv(csv_path)
        svc = DataProcessingService()
        df_pl, _ = svc.parse_file(open(csv_path, 'rb').read(), 'property data.csv')
        svc.auto_pilot(df_pl, objective='classification', algorithm=['auto'], nlp_mode='', is_guest=False)
        print("SUCCESS")
    except Exception as e:
        with open("error_trace.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
            
if __name__ == '__main__':
    run()
