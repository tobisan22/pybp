"""
メモ
vsixの際build
vsce package --target win32-x64
vsce publish 0.4.0

"""

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["axes.grid"] = True

x = np.linspace(0, 10, 100)

# %%
for i in range(1, 3):
    y = np.sin(x * i)

    fig, ax = plt.subplots(clear=True, num=i)
    fig.set_size_inches(8, 6)

    ax.plot(x, y, label="sin(x)")

    plt.show()

    time.sleep(3)

# %%
