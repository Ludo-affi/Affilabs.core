from pathlib import Path

import numpy as np

p = Path("training_data/used_current/20251023_010403_channel_A_p_mode.npz")
d = np.load(p)
print("Keys:", list(d.keys()))
for k in d.files:
    arr = d[k]
    try:
        print(k, arr.shape, arr.dtype)
    except Exception:
        print(k, type(arr))
