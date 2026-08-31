import numpy as np


def dist_between(
    pt1_x: float, pt1_y: float, pt1_z: float, pt2_x: float, pt2_y: float, pt2_z: float
) -> float:
    return np.sqrt(
        np.square(pt2_x - pt1_x) + np.square(pt2_y - pt1_y) + np.square(pt2_z - pt1_z)
    )
