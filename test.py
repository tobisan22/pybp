import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)


for i in range(1, 4):
    y = np.sin(x * i)

    fig, ax = plt.subplots(clear=True, num=i)
    fig.set_size_inches(8, 6)

    ax.plot(x, y, label="sin(x)")

    plt.show()
