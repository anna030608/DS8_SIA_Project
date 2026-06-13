import pandas as pd

df = pd.read_csv(r"C:\Users\user\DS8_SIA_Project\dashboard_exp\project\01_data\processed\gridsearch_exp_results.csv")
print(df.head(10))
print(f"\nw_geo 고유값: {sorted(df['w_geo'].unique())}")
print(f"w_mentions 고유값: {sorted(df['w_mentions'].unique())}")
print(f"F1 범위: {df['f1'].min():.3f} ~ {df['f1'].max():.3f}")

df2 = pd.read_csv(r"C:\Users\user\DS8_SIA_Project\dashboard_exp\project\01_data\processed\filter_weight_results.csv")
print(f"\nfilter_weight_results 샘플:")
print(df2.head(5))