"""Calibrate track XY against surveyed metric east/north landmarks, not map display rotation."""

import math
import numpy as np


def align_metric_landmarks(
    track_xy_m, east_north_m, *, survey_error_m=3, max_residual_m=10
):
    x = np.asarray(track_xy_m, dtype=float)
    y = np.asarray(east_north_m, dtype=float)
    if (
        x.shape != y.shape
        or x.ndim != 2
        or x.shape[1] != 2
        or len(x) < 3
        or len(x) > 1000
        or not np.all(np.isfinite(x))
        or not np.all(np.isfinite(y))
    ):
        raise ValueError(
            "Supply 3-1000 finite corresponding XY and metric east/north landmarks"
        )
    if not 0 < survey_error_m <= 50 or not 0 < max_residual_m <= 50:
        raise ValueError("Invalid survey error bounds")
    centre_x = x.mean(axis=0)
    centre_y = y.mean(axis=0)
    a = x - centre_x
    b = y - centre_y
    if np.linalg.matrix_rank(a) < 2 or np.linalg.matrix_rank(b) < 2:
        raise ValueError("Landmarks must not be collinear")
    u, singular, vt = np.linalg.svd(a.T @ b)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        raise ValueError(
            "Reflected or inconsistent coordinate frame; verify landmark pairing and axes"
        )
    scale = float(np.sum(singular) / np.sum(a * a))
    if not 0.98 <= scale <= 1.02:
        raise ValueError("Metric frame scale mismatch exceeds two percent")
    offset = centre_y - scale * (rotation @ centre_x)
    residual = np.linalg.norm(scale * (x @ rotation.T) + offset - y, axis=1)
    rmse = float(np.sqrt(np.mean(residual**2)))
    if float(np.max(residual)) > max_residual_m:
        raise ValueError("Landmark residual exceeds configured survey tolerance")
    north = rotation.T @ np.array([0.0, 1.0])
    north_angle = math.degrees(math.atan2(north[1], north[0])) % 360
    baseline = float(np.sqrt(np.mean(np.sum(a * a, axis=1))))
    angle_error = math.degrees(math.atan2(3 * max(rmse, survey_error_m), baseline))
    return dict(
        north_angle_xy_deg=north_angle,
        alignment_error_deg=angle_error,
        scale=scale,
        rotation_track_to_enu=rotation.tolist(),
        translation_enu_m=offset.tolist(),
        residual_rmse_m=rmse,
        residual_max_m=float(np.max(residual)),
        landmark_count=len(x),
        position_error_m=max(15, 3 * max(rmse, survey_error_m)),
        error_interpretation="conservative_survey_sensitivity_not_calibrated_probability",
    )
