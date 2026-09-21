# -*- coding: utf-8 -*-
"""
plot_firo_space.py

One figure for the FIRO concept at Green Peter: how high the pool could be
allowed to ride, and what decides it.

THE IDEA IN ONE PARAGRAPH
    The rule curve tells Green Peter to empty itself every autumn and stay
    empty until February, because a winter storm has to land somewhere. FIRO
    - Forecast Informed Reservoir Operations - says that emptying is only
    needed when a storm is actually coming. The rest of the time the pool
    could ride above the conservation rule curve and below full pool, and the
    water it holds there is water the basin gets to keep.

    The catch is the part this figure is really about. The space that has to
    stay empty is not a fixed number of feet. It is a STORAGE VOLUME MEASURED
    DOWN FROM FULL POOL, big enough to swallow the storm the forecast is
    calling for - and how big that is depends on three things:

        - the volume of the incoming storm
        - the lead time, because lead time is pre-release, and every day of
          warning is another day of outlet capacity you get to spend before
          the water arrives
        - the confidence in the forecast, because a forecast you half believe
          has to be carried at more than face value

    Everything above that reserved volume, down to the rule curve, is the
    allowable encroachment. That is the number a FIRO proposal has to defend.

WHAT THE THREE PANELS DO
    A   the seasonal picture. Rule curve, full pool, and the band between
        them, cut by the ceiling that one example storm imposes. The arrow on
        the right is the required flood space, drawn where it is defined -
        hanging down from full pool.
    B   required flood space against storm volume, one line per lead time.
        The lines are parallel and offset downward: lead time does not change
        how much water is coming, it buys you a head start on getting rid of
        it. Where a line hits zero, pre-release alone handles the storm.
    C   the same requirement against forecast confidence. This is the panel
        that says why FIRO is a forecasting problem and not a reservoir
        problem - at low confidence the reserved space swamps everything the
        lead time bought back.

THE MODEL IS DELIBERATELY CRUDE
    required space = storm volume x confidence factor - pre-release volume

    with confidence factor = 1 + (1 - confidence), so a forecast believed at
    50% is carried at 1.5x face value, and a perfect forecast at face value.
    Pre-release is the safe outlet release held for the whole lead time.

    That is a concept diagram, not an operating rule. It has no routing, no
    inflow shape, no downstream constraint that varies with stage, no
    ramp-down limits, and no rain-on-snow. It is here to make the SHAPE of
    the dependence visible and to give the three axes a place to live. Real
    numbers come out of a routing model.

INPUTS
    data/RuleCurves.csv                      the GREEN PETER column
    data/firo/ratings/GPR.csv                elevation-storage, from
                                             parse_stor_ratings.py
    data/firo/GREEN_PETER_POOL_LEVELS.csv    full pool, and the two
                                             conservation bookends

    Full pool in that last file is a PLACEHOLDER until the stats tab is
    parsed into it. The script says so on every run, loudly, because every
    volume on the figure is measured down from it.

OUTPUT
    out/firo/firo_space_concept.png

USAGE
    cd src\firo ; python parse_stor_ratings.py ; if ($?) { python plot_firo_space.py }
"""

import os

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
RULE_CURVES_CSV = os.path.join("data", "RuleCurves.csv")
RATING_CSV = os.path.join("data", "firo", "ratings", "GPR.csv")
LEVELS_CSV = os.path.join("data", "firo", "GREEN_PETER_POOL_LEVELS.csv")
OUT_PNG = os.path.join("out", "firo", "firo_space_concept.png")

PROJECT = "GREEN PETER"

# Model assumptions. Every one of these is a number someone should argue with,
# which is why they are here at the top rather than buried in the maths.
#
# SAFE_RELEASE_CFS is the rate the project can pre-release at without causing
# the downstream problem it is trying to prevent. At Green Peter that is set
# below by Foster and the South Santiam, not by the outlet works.
SAFE_RELEASE_CFS = 5000.0
AF_PER_CFS_DAY = 1.98347

# The storm drawn on panel A, and the point the other two panels hold fixed.
EXAMPLE_STORM_AF = 80000.0
EXAMPLE_LEAD_DAYS = 3.0
EXAMPLE_CONFIDENCE = 0.70

LEAD_TIMES_DAYS = (1.0, 3.0, 5.0)
STORM_RANGE_AF = (0.0, 200000.0)
CONFIDENCE_RANGE = (0.40, 1.00)

# Water year, so the flood season reads left to right instead of wrapping.
WATER_YEAR_START = (10, 1)

# ---------------------------------------------------------------------------
# Palette. Three categorical slots, validated all-pairs in light mode; aqua
# sits under 3:1 on this surface, so every line is directly labelled.
# ---------------------------------------------------------------------------
C_SURFACE = "#fcfcfb"
C_TEXT = "#0b0b0b"
C_TEXT_2 = "#52514e"
C_MUTED = "#8a8881"
C_GRID = "#e8e7e3"

C_SERIES = ("#2a78d6", "#eb6834", "#1baf7a")   # blue, orange, aqua
C_BLUE, C_ORANGE, C_AQUA = C_SERIES

C_CONSERVATION = "#dcdad3"    # water already stored - recessive on purpose
C_FIRO = "#cde2fb"            # the space FIRO is asking for
C_RESERVED = "#f7d7cc"        # the space the storm takes back
C_RULE = "#184f95"
C_FULL = "#0b0b0b"


# ---------------------------------------------------------------------------
def repo_root():
    """Recognise the repository root by its contents, not by a fixed "..\"."""
    here = os.path.dirname(os.path.abspath(__file__))
    while True:
        if all(os.path.isdir(os.path.join(here, d)) for d in ("data", "src")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            raise SystemExit("Cannot find the repository root above %s"
                             % os.path.dirname(os.path.abspath(__file__)))
        here = parent


def resolve_path(path):
    return path if os.path.isabs(path) else os.path.normpath(
        os.path.join(repo_root(), path))


# ---------------------------------------------------------------------------
# The rating, and the two directions through it
# ---------------------------------------------------------------------------
def load_rating():
    path = resolve_path(RATING_CSV)
    if not os.path.isfile(path):
        raise SystemExit(
            "No rating at %s\nRun parse_stor_ratings.py first." % path)
    rating = pd.read_csv(path).sort_values("elev_ft")
    return rating["elev_ft"].to_numpy(), rating["stor_af"].to_numpy()


def storage_at(elev, elev_pts, stor_pts):
    """Elevation -> storage. Outside the rating this clamps, which is right:
    the plot should flatten at the ends rather than extrapolate a lake."""
    return np.interp(elev, elev_pts, stor_pts)


def elevation_at(stor, elev_pts, stor_pts):
    """Storage -> elevation. np.interp needs an increasing x, and storage is
    monotonic in elevation, so the rating serves both directions unchanged."""
    return np.interp(stor, stor_pts, elev_pts)


def load_levels(elev_pts, stor_pts):
    """The named pool levels, with the stored storage checked against the
    rating rather than trusted - a datum mismatch shows up here or nowhere."""
    levels = pd.read_csv(resolve_path(LEVELS_CSV)).set_index("level")

    for name, row in levels.iterrows():
        from_rating = storage_at(row["elev_ft"], elev_pts, stor_pts)
        gap = abs(from_rating - row["stor_af"])
        if gap > max(500.0, 0.005 * from_rating):
            print("  WARNING  %s: table says %.0f ac-ft at %.2f ft, the "
                  "rating says %.0f (%.0f apart)"
                  % (name, row["stor_af"], row["elev_ft"], from_rating, gap))
        if "PLACEHOLDER" in str(row["source"]).upper():
            print("  WARNING  %s is a PLACEHOLDER (%.2f ft). Every volume on "
                  "the figure is measured down from full pool, so replace it "
                  "with the stats tab value before quoting anything."
                  % (name, row["elev_ft"]))

    return levels


def load_rule_curve():
    """The generic-year curve for Green Peter, re-indexed to a water year."""
    frame = pd.read_csv(resolve_path(RULE_CURVES_CSV), encoding="utf-8-sig")
    dates = pd.to_datetime(frame[frame.columns[0]], format="%d%b%Y")

    curve = pd.DataFrame({
        "month": dates.dt.month,
        "day": dates.dt.day,
        "elev_ft": frame[PROJECT].astype(float),
    })

    # Day 0 of the water year is 01 Oct. Sorting on that key puts the autumn
    # drawdown, the winter floor and the spring refill in reading order.
    start_month, start_day = WATER_YEAR_START
    after_start = ((curve["month"] > start_month)
                   | ((curve["month"] == start_month)
                      & (curve["day"] >= start_day)))
    curve["sort_key"] = np.where(after_start, 0, 1)
    curve = curve.sort_values(["sort_key", "month", "day"]).reset_index(drop=True)
    curve["wy_day"] = np.arange(len(curve))
    return curve


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------
def confidence_factor(confidence):
    """A forecast believed at C is carried at 1 + (1 - C) times face value.

    Linear because nothing here justifies a curve. The shape that matters is
    that it is 1.0 at perfect confidence and grows without a cliff as
    confidence falls - the reserved space degrades, it does not switch off.
    """
    return 1.0 + (1.0 - np.asarray(confidence, dtype=float))


def prerelease_volume_af(lead_days):
    """What the outlets can move before the storm arrives."""
    return SAFE_RELEASE_CFS * AF_PER_CFS_DAY * np.asarray(lead_days, dtype=float)


def required_space_af(storm_af, lead_days, confidence):
    """Storage that has to be empty below full pool, in acre-feet.

    Floored at zero: once pre-release can absorb the whole storm there is
    nothing left to reserve, and a negative reservation is not a credit.
    """
    demand = np.asarray(storm_af, dtype=float) * confidence_factor(confidence)
    return np.maximum(demand - prerelease_volume_af(lead_days), 0.0)


# ---------------------------------------------------------------------------
# Figure furniture
# ---------------------------------------------------------------------------
def style_axes(ax):
    ax.set_facecolor(C_SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C_GRID)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=C_TEXT_2, labelsize=9, length=3, width=1.0)
    ax.grid(True, color=C_GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def month_ticks(curve):
    """First of each month, as (wy_day, label)."""
    firsts = curve.index[curve["day"] == 1]
    labels = ["JFMAMJJASOND"[curve.loc[i, "month"] - 1] for i in firsts]
    return curve.loc[firsts, "wy_day"].to_numpy(), labels


def thousands(af):
    return af / 1000.0


# ---------------------------------------------------------------------------
# Panel A - the seasonal picture
# ---------------------------------------------------------------------------
def panel_season(ax, curve, levels, elev_pts, stor_pts):
    full_elev = float(levels.loc["full_pool", "elev_ft"])
    full_stor = storage_at(full_elev, elev_pts, stor_pts)

    reserved = required_space_af(
        EXAMPLE_STORM_AF, EXAMPLE_LEAD_DAYS, EXAMPLE_CONFIDENCE)
    ceiling_elev = float(elevation_at(full_stor - reserved, elev_pts, stor_pts))

    x = curve["wy_day"].to_numpy()
    rule = curve["elev_ft"].to_numpy()
    ceiling = np.full_like(rule, ceiling_elev)
    floor = rule.min() - 8.0

    # Where the ceiling sits below the rule curve the conservation schedule is
    # the binding constraint, not the storm. Clipping keeps the FIRO band from
    # being drawn upside down through the summer.
    firo_top = np.maximum(ceiling, rule)

    ax.fill_between(x, floor, rule, color=C_CONSERVATION, zorder=1)
    ax.fill_between(x, rule, firo_top, where=ceiling > rule,
                    color=C_FIRO, zorder=1, interpolate=True)
    ax.fill_between(x, firo_top, full_elev, where=ceiling > rule,
                    color=C_RESERVED, zorder=1, interpolate=True)

    # Where the storm needs more space than the gap between the rule curve and
    # full pool, there is no FIRO space to offer. Hatching it says so in place
    # rather than in a caption with a leader line across the panel.
    ax.fill_between(x, rule, full_elev, where=ceiling <= rule,
                    facecolor="none", hatch="////", edgecolor=C_MUTED,
                    linewidth=0.0, zorder=1, interpolate=True)

    # A 2px surface underlay under each boundary so the fills never touch.
    for series, color, dash in ((rule, C_RULE, None),
                                (ceiling, C_ORANGE, (5, 3))):
        ax.plot(x, series, color=C_SURFACE, linewidth=4.0, zorder=2)
        ax.plot(x, series, color=color, linewidth=2.0, zorder=3,
                dashes=dash if dash else (None, None), solid_capstyle="round")

    ax.axhline(full_elev, color=C_SURFACE, linewidth=4.0, zorder=2)
    ax.axhline(full_elev, color=C_FULL, linewidth=2.0, zorder=3)

    # The arrow is the whole point of the panel: the reserved space is a
    # volume, and it hangs down from full pool.
    x_arrow = x[int(len(x) * 0.52)]
    ax.annotate("", xy=(x_arrow, ceiling_elev), xytext=(x_arrow, full_elev),
                arrowprops=dict(arrowstyle="<->", color=C_ORANGE, linewidth=1.8,
                                shrinkA=0, shrinkB=0), zorder=5)
    ax.text(x_arrow - 6, (full_elev + ceiling_elev) / 2.0,
            "required flood space\n%.0f ft  =  %s ac-ft\nkept empty below full pool"
            % (full_elev - ceiling_elev, format(int(round(reserved)), ",")),
            color=C_TEXT, fontsize=9.5, va="center", ha="right", zorder=6)

    # And the encroachment it leaves behind. Measured at the winter floor,
    # because that is where the rule curve is deepest and the gap is the whole
    # argument - anywhere on the refill ramp undersells it.
    x_gain = x[int(len(x) * 0.33)]
    gain_bottom = float(np.interp(x_gain, x, rule))
    gain_af = (storage_at(ceiling_elev, elev_pts, stor_pts)
               - storage_at(gain_bottom, elev_pts, stor_pts))
    ax.annotate("", xy=(x_gain, ceiling_elev), xytext=(x_gain, gain_bottom),
                arrowprops=dict(arrowstyle="<->", color=C_RULE, linewidth=1.8,
                                shrinkA=0, shrinkB=0), zorder=5)
    ax.text(x_gain - 8, ceiling_elev - 0.30 * (ceiling_elev - gain_bottom),
            "allowable encroachment\n%.0f ft  =  %s ac-ft"
            % (ceiling_elev - gain_bottom, format(int(round(gain_af)), ",")),
            color=C_TEXT, fontsize=9.5, va="center", ha="right", zorder=6)

    ax.text(x[2], full_elev + 1.0, "full pool  %.1f ft" % full_elev,
            color=C_TEXT, fontsize=9.5, ha="left", va="bottom", weight="bold")
    ax.text(x[int(len(x) * 0.72)], rule[int(len(x) * 0.72)] - 2.0,
            "conservation rule curve", color=C_RULE, fontsize=9.5,
            ha="center", va="top", weight="bold")
    ax.text(x[int(len(x) * 0.055)], ceiling_elev + 1.0, "FIRO ceiling",
            color=C_ORANGE, fontsize=9.5, ha="center", va="bottom",
            weight="bold")

    ticks, labels = month_ticks(curve)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.set_xlim(x[0], x[-1])
    ax.set_ylim(floor, full_elev + 5.0)
    ax.set_ylabel("pool elevation (ft, NGVD29)", color=C_TEXT_2, fontsize=9.5)
    ax.set_title("A   The FIRO space at Green Peter, through the water year",
                 color=C_TEXT, fontsize=12.5, weight="bold", loc="left", pad=24)
    ax.text(0, 1.012,
            "example storm: %s ac-ft forecast, %.0f-day lead, %.0f%% confidence"
            % (format(int(EXAMPLE_STORM_AF), ","), EXAMPLE_LEAD_DAYS,
               EXAMPLE_CONFIDENCE * 100),
            transform=ax.transAxes, color=C_TEXT_2, fontsize=10, va="bottom")

    # Legend below the panel: the top-left corner of this one is data.
    ax.legend(handles=[
        Patch(facecolor=C_CONSERVATION, edgecolor="none",
              label="conservation pool - water already stored"),
        Patch(facecolor=C_FIRO, edgecolor="none",
              label="FIRO space - the encroachment a forecast can authorise"),
        Patch(facecolor=C_RESERVED, edgecolor="none",
              label="required flood space - reserved for the forecast storm"),
        Patch(facecolor="none", edgecolor=C_MUTED, hatch="////",
              label="no FIRO space - this storm needs more than the gap holds"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, frameon=False,
        fontsize=9.5, labelcolor=C_TEXT_2, handlelength=1.8, borderpad=0.2,
        columnspacing=2.4)


# ---------------------------------------------------------------------------
# Panels B and C - what moves the ceiling
# ---------------------------------------------------------------------------
def label_end(ax, x, y, text, color):
    """Direct label at the right end of a line, with a surface halo so it
    survives crossing a grid line."""
    ax.annotate(text, xy=(x, y), xytext=(6, 0), textcoords="offset points",
                color=color, fontsize=9, va="center", ha="left", weight="bold",
                path_effects=None, zorder=6)


def panel_storm_volume(ax):
    storms = np.linspace(*STORM_RANGE_AF, 400)

    for lead, color in zip(LEAD_TIMES_DAYS, C_SERIES):
        need = required_space_af(storms, lead, EXAMPLE_CONFIDENCE)
        ax.plot(thousands(storms), thousands(need), color=C_SURFACE,
                linewidth=4.0, zorder=2)
        ax.plot(thousands(storms), thousands(need), color=color, linewidth=2.0,
                zorder=3, solid_capstyle="round",
                label="%.0f-day lead" % lead)
        label_end(ax, thousands(storms[-1]), thousands(need[-1]),
                  "%.0fd" % lead, color)

    ax.set_xlabel("forecast storm volume (1,000 ac-ft)", color=C_TEXT_2,
                  fontsize=9.5)
    ax.set_ylabel("required flood space below\nfull pool (1,000 ac-ft)",
                  color=C_TEXT_2, fontsize=9.5)
    ax.set_xlim(thousands(STORM_RANGE_AF[0]), thousands(STORM_RANGE_AF[1]) * 1.06)
    ax.set_ylim(bottom=0)
    ax.set_title("B   Bigger storm, more space",
                 color=C_TEXT, fontsize=11.5, weight="bold", loc="left", pad=22)
    ax.text(0, 1.015, "confidence held at %.0f%%" % (EXAMPLE_CONFIDENCE * 100),
            transform=ax.transAxes, color=C_TEXT_2, fontsize=9, va="bottom")
    ax.legend(loc="upper left", frameon=False, fontsize=9,
              labelcolor=C_TEXT_2, handlelength=1.6, borderpad=0.2)


def panel_confidence(ax):
    confidence = np.linspace(*CONFIDENCE_RANGE, 400)

    for lead, color in zip(LEAD_TIMES_DAYS, C_SERIES):
        need = required_space_af(EXAMPLE_STORM_AF, lead, confidence)
        ax.plot(confidence * 100, thousands(need), color=C_SURFACE,
                linewidth=4.0, zorder=2)
        ax.plot(confidence * 100, thousands(need), color=color, linewidth=2.0,
                zorder=3, solid_capstyle="round",
                label="%.0f-day lead" % lead)
        label_end(ax, confidence[-1] * 100, thousands(need[-1]),
                  "%.0fd" % lead, color)

    ax.set_xlabel("confidence in the forecast (%)", color=C_TEXT_2, fontsize=9.5)
    ax.set_ylabel("required flood space below\nfull pool (1,000 ac-ft)",
                  color=C_TEXT_2, fontsize=9.5)
    ax.set_xlim(CONFIDENCE_RANGE[0] * 100, CONFIDENCE_RANGE[1] * 100 + 3)
    ax.set_ylim(bottom=0)
    ax.set_title("C   Less confidence, more space",
                 color=C_TEXT, fontsize=11.5, weight="bold", loc="left", pad=22)
    ax.text(0, 1.015, "storm held at %s ac-ft"
            % format(int(EXAMPLE_STORM_AF), ","),
            transform=ax.transAxes, color=C_TEXT_2, fontsize=9, va="bottom")
    ax.legend(loc="lower left", frameon=False, fontsize=9,
              labelcolor=C_TEXT_2, handlelength=1.6, borderpad=0.2)


# ---------------------------------------------------------------------------
def main():
    print("Green Peter FIRO space\n")
    elev_pts, stor_pts = load_rating()
    levels = load_levels(elev_pts, stor_pts)
    curve = load_rule_curve()

    reserved = required_space_af(
        EXAMPLE_STORM_AF, EXAMPLE_LEAD_DAYS, EXAMPLE_CONFIDENCE)
    print("\n  example: %s ac-ft storm, %.0f-day lead, %.0f%% confidence"
          % (format(int(EXAMPLE_STORM_AF), ","), EXAMPLE_LEAD_DAYS,
             EXAMPLE_CONFIDENCE * 100))
    print("  pre-release at %.0f cfs for %.0f days  =  %s ac-ft"
          % (SAFE_RELEASE_CFS, EXAMPLE_LEAD_DAYS,
             format(int(round(prerelease_volume_af(EXAMPLE_LEAD_DAYS))), ",")))
    print("  required flood space below full pool =  %s ac-ft"
          % format(int(round(reserved)), ","))

    fig = plt.figure(figsize=(14, 12), facecolor=C_SURFACE)
    grid = fig.add_gridspec(2, 2, height_ratios=(1.5, 1.0),
                            hspace=0.42, wspace=0.28,
                            left=0.075, right=0.965, top=0.875, bottom=0.105)

    ax_season = fig.add_subplot(grid[0, :])
    ax_storm = fig.add_subplot(grid[1, 0])
    ax_conf = fig.add_subplot(grid[1, 1])
    for ax in (ax_season, ax_storm, ax_conf):
        style_axes(ax)

    panel_season(ax_season, curve, levels, elev_pts, stor_pts)
    panel_storm_volume(ax_storm)
    panel_confidence(ax_conf)

    fig.suptitle("How much space does Green Peter actually have to keep empty?",
                 color=C_TEXT, fontsize=17, weight="bold", x=0.075, ha="left",
                 y=0.975)
    fig.text(0.075, 0.945,
             "The allowable encroachment is a storage volume measured down "
             "from full pool, and it is a function of the storm, the lead "
             "time, and how much the forecast is believed.",
             color=C_TEXT_2, fontsize=11, ha="left", va="top")
    fig.text(0.075, 0.014,
             "Concept diagram, not an operating rule. Required space = storm "
             "volume x (2 - confidence) - safe pre-release x lead time, safe "
             "release at %.0f cfs.\nNo routing, no inflow shape, no "
             "stage-dependent downstream limit. Rule curve: "
             "data/RuleCurves.csv. Elevation-storage: the CWMS rating for GPR."
             % SAFE_RELEASE_CFS,
             color=C_MUTED, fontsize=9, ha="left", va="bottom", linespacing=1.5)

    out = resolve_path(OUT_PNG)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=160, facecolor=C_SURFACE)
    plt.close(fig)
    print("\nWrote %s" % os.path.relpath(out, repo_root()))


if __name__ == "__main__":
    main()
