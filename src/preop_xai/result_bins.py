"""Descriptive calibration bins from saved, aligned probabilities."""

import numpy as np

from preop_xai.result_io import Json, Row


def calibration_bins(
    y: np.ndarray, probability: np.ndarray, identity: Row
) -> tuple[list[Row], list[Row], dict[str, Json]]:
    """Retain protocol fixed bins and separately request ten quantile bins."""
    fixed_edges = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    quantile_edges = np.unique(np.quantile(probability, np.linspace(0, 1, 11)))
    constant = len(quantile_edges) == 1
    quantile_count = max(1, len(quantile_edges) - 1)
    fixed_index = np.minimum(np.searchsorted(fixed_edges, probability, side="right") - 1, 4)
    quantile_index = np.searchsorted(quantile_edges[1:-1], probability, side="left")
    base = {key: value for key, value in identity.items() if key != "calibration_status"}

    def rows(edges: np.ndarray, membership: np.ndarray, count: int) -> list[Row]:
        result: list[Row] = []
        for index in range(count):
            mask = membership == index
            n = int(mask.sum())
            events = int(y[mask].sum())
            result.append(
                {
                    **base,
                    "bin_id": index,
                    "lower": float(edges[index]),
                    "upper": float(edges[index + 1] if len(edges) > 1 else edges[0]),
                    "n": n,
                    "events": events,
                    "nonevents": n - events,
                    "mean_predicted": float(probability[mask].mean()) if n else None,
                    "observed_fraction": events / n if n else None,
                    "empty": n == 0,
                    "calibration_status": identity["calibration_status"],
                }
            )
        return result

    fixed = rows(fixed_edges, fixed_index, 5)
    quantile = rows(quantile_edges, quantile_index, quantile_count)
    metadata: dict[str, Json] = {
        "strategy": "probability-quantile",
        "quantile_method": "linear",
        "requested_bin_count": 10,
        "effective_bin_count": quantile_count,
        "edges": [float(edge) for edge in quantile_edges],
        "collapsed_edge_count": 11 - len(quantile_edges),
        "closure": "[minimum, first upper]; subsequent (lower, upper]",
        "ties": "equal probabilities remain together",
        "constant": constant,
    }
    return fixed, quantile, metadata
