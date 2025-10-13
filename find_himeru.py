import pandas as pd
import glob
import os

base = r'F:\Code\Trae\projects\es'
files = sorted(glob.glob(os.path.join(base, 'es2 卡面名称及技能一览2025*.xlsx')))

print('Found files:')
for f in files:
    print(f'  {os.path.basename(f)}')

print()

for f in files:
    try:
        df = pd.read_excel(f)
        himeru_rows = df[df['卡面名称'].str.contains('HiMERU', na=False)]
        if len(himeru_rows) > 0:
            print(f'File {os.path.basename(f)} has HiMERU cards:')
            for _, row in himeru_rows.iterrows():
                print(f'  {row["卡面名称"]}')
                print(f'    center技能名称: {row["center技能名称"]}')
                print(f'    MV衣装: {row["MV衣装"]}')
                print(f'    房间衣装: {row["房间衣装"]}')
                print(f'    spp对应乐曲: {row["spp对应乐曲"]}')
                print()
    except Exception as e:
        print(f'Error reading {os.path.basename(f)}: {e}')