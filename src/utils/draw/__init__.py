import matplotlib.pyplot as plt
import pandas as pd


def draw_track(name: str):
    track_folder = f"tracks/{name}"

    inner = pd.read_csv(f"{track_folder}/left.csv")
    outer = pd.read_csv(f"{track_folder}/right.csv")

    # if name == 'interlagos':
    #     plt.figure(figsize=(8, 10))

    # elif name == 'spa':
    #     plt.figure(figsize=(10, 20))

    plt.plot(inner["x"], inner["y"], color="black")
    plt.plot(outer["x"], outer["y"], color="black")

    x_min, x_max, y_min, y_max = plt.axis()

    delta_x = x_max - x_min
    delta_y = y_max - y_min

    figsize_x = 10
    figsize_y = int(figsize_x * (delta_y / delta_x))

    plt.figure(figsize=(figsize_x, figsize_y))

    plt.plot(inner["x"], inner["y"], color="black")
    plt.plot(outer["x"], outer["y"], color="black")
