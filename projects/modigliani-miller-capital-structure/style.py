"""Shared chart style (burgundy palette used across the portfolio)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

WINE, ROSE, PALE, DARK, GREY = "#701A3D", "#C77B9B", "#E5B5C7", "#2A0E1B", "#8A8A8A"
plt.rcParams.update({
    "figure.dpi": 130, "savefig.bbox": "tight", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "font.size": 10, "axes.titleweight": "bold",
    "axes.prop_cycle": matplotlib.cycler(color=[WINE, ROSE, DARK, GREY, "#B5476F", "#5A1530"]),
})


def save(fig, path):
    fig.savefig(path)
    plt.close(fig)
