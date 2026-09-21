import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)


for i in range(1, 4):
    y = np.sin(x * i)

    fig, ax = plt.subplots(clear=True, num=i, figsize=(5, 5), dpi=100)
    ax.plot(x, y, label="sin(x)")

    plt.show()
