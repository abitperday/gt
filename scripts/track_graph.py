import pandas as pd


TRACK_FOLDER = 'track_layouts/nurburgring/gp'
SAMPLE_RATE = 2 # means take one line per SAMPLE_RATE


for border in ['left', 'right']:
    df = pd.read_csv(f'{TRACK_FOLDER}/source/{border}.csv')
    new_df = df[['x', 'y', 'z']][::SAMPLE_RATE]
    new_df.to_csv(f"{TRACK_FOLDER}/{border}.csv", index=False)