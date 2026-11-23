"""
IPL data analysis, 2008-2026, from ball-by-ball data.

Inputs (data/):
  Match_Info.csv                     one row per match (1,243 matches)
  Ball_By_Ball_Match_Data.csv.gz     one row per delivery (295,732 deliveries)

Outputs (outputs/): one CSV per table, five charts and summary.json.

Cricket rules used in the calculations
  - Legal ball: not a wide and not a no-ball.
  - Balls faced by a batter: every delivery except wides.
  - Runs conceded by a bowler: batter runs + wides + no-ball extras (byes and leg byes are not the bowler's).
  - Bowler wickets: every dismissal except run out, retired hurt, retired out and obstructing the field.
  - Phases: powerplay = overs 1-6, middle = overs 7-15, death = overs 16-20.
  - Franchises that changed name are counted as one team (e.g. Delhi Daredevils -> Delhi Capitals).
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).parent
DATA = HERE / "data"
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)
BLUE, GOLD, GREY = "#1F3B73", "#E0A526", "#8A8A8A"

TEAM = {
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Rising Pune Supergiants": "Rising Pune Supergiant",
}
VENUE = {
    "Feroz Shah Kotla": "Arun Jaitley Stadium",
    "M.Chinnaswamy Stadium": "M Chinnaswamy Stadium",
    "Punjab Cricket Association IS Bindra Stadium": "Punjab Cricket Association Stadium",
    "Sardar Patel Stadium": "Narendra Modi Stadium",
    "Zayed Cricket Stadium": "Sheikh Zayed Stadium",
}
NOT_BOWLER = {"run out", "retired hurt", "retired out", "obstructing the field"}


def load():
    m = pd.read_csv(DATA / "Match_Info.csv", parse_dates=["match_date"])
    b = pd.read_csv(DATA / "Ball_By_Ball_Match_Data.csv.gz")
    for col in ["team1", "team2", "toss_winner", "winner"]:
        m[col] = m[col].replace(TEAM)
    b["BattingTeam"] = b["BattingTeam"].replace(TEAM)
    m["season"] = m["match_date"].dt.year
    m["venue_name"] = m["venue"].str.split(",").str[0].str.strip().replace(VENUE)
    b = b.merge(m[["match_number", "season"]], left_on="ID", right_on="match_number")
    extra = b["ExtraType"].fillna("")
    b["is_wide"] = extra.str.contains("wides")
    b["is_noball"] = extra.str.contains("noballs")
    b["legal"] = ~(b["is_wide"] | b["is_noball"])
    b["faced"] = ~b["is_wide"]
    b["bowler_runs"] = b["BatsmanRun"] + b["ExtrasRun"].where(b["is_wide"] | b["is_noball"], 0)
    b["bowler_wkt"] = (b["IsWicketDelivery"] == 1) & ~b["Kind"].isin(NOT_BOWLER)
    b["phase"] = pd.cut(b["Overs"], [-1, 5, 14, 19], labels=["Powerplay (1-6)", "Middle (7-15)", "Death (16-20)"])
    return m, b


def season_trends(m, b):
    inn = b.groupby(["ID", "Innings", "season"]).agg(runs=("TotalRun", "sum"), legal=("legal", "sum")).reset_index()
    first = inn[inn["Innings"] == 1].groupby("season")["runs"].agg(avg_first_innings="mean", highest="max")
    six = b[b["BatsmanRun"] == 6].groupby("season").size() / m.groupby("season").size()
    four = b[b["BatsmanRun"] == 4].groupby("season").size() / m.groupby("season").size()
    rr = b.groupby("season").apply(lambda g: 6 * g["TotalRun"].sum() / g["legal"].sum(), include_groups=False)
    t = pd.DataFrame({"matches": m.groupby("season").size(), "avg_first_innings": first["avg_first_innings"],
                      "highest_total": first["highest"], "run_rate": rr,
                      "sixes_per_match": six, "fours_per_match": four}).round(2)
    t["200_plus_totals"] = inn[inn["runs"] >= 200].groupby("season").size().reindex(t.index, fill_value=0)
    return t.reset_index()


def phase_rates(b):
    p = b.groupby(["season", "phase"], observed=True).apply(
        lambda g: 6 * g["TotalRun"].sum() / g["legal"].sum(), include_groups=False).unstack().round(2)
    return p.reset_index()


def toss_and_chasing(m):
    played = m[m["result"] == "Win"].copy()
    played["toss_winner_won"] = played["toss_winner"] == played["winner"]
    played["chose_field"] = played["toss_decision"] == "field"
    bat_first = played.apply(lambda r: r["toss_winner"] if r["toss_decision"] == "bat"
                             else (r["team2"] if r["toss_winner"] == r["team1"] else r["team1"]), axis=1)
    played["chasing_won"] = played["winner"] != bat_first
    t = played.groupby("season").agg(matches=("winner", "size"),
                                     toss_winner_won_pct=("toss_winner_won", "mean"),
                                     chose_to_field_pct=("chose_field", "mean"),
                                     chasing_team_won_pct=("chasing_won", "mean"))
    t[["toss_winner_won_pct", "chose_to_field_pct", "chasing_team_won_pct"]] *= 100
    overall = {"toss_winner_won_pct": round(100 * played["toss_winner_won"].mean(), 1),
               "chasing_team_won_pct": round(100 * played["chasing_won"].mean(), 1),
               "chose_to_field_pct": round(100 * played["chose_field"].mean(), 1),
               "matches_with_result": len(played)}
    return t.round(1).reset_index(), overall


def teams(m):
    finals = m.sort_values("match_date").groupby("season").tail(1)[["season", "team1", "team2", "winner", "venue_name"]]
    titles = finals["winner"].value_counts().rename("titles")
    long = pd.concat([m[["season", "team1", "winner", "result"]].rename(columns={"team1": "team"}),
                      m[["season", "team2", "winner", "result"]].rename(columns={"team2": "team"})])
    long["won"] = long["team"] == long["winner"]
    t = long.groupby("team").agg(seasons=("season", "nunique"), matches=("won", "size"), wins=("won", "sum"))
    t["win_pct"] = (100 * t["wins"] / t["matches"]).round(1)
    t = t.join(titles).fillna({"titles": 0}).astype({"titles": int})
    return t.sort_values(["titles", "win_pct"], ascending=False).reset_index(), finals.reset_index(drop=True)


def batting(b):
    g = b.groupby("Batter").agg(runs=("BatsmanRun", "sum"), balls=("faced", "sum"),
                                fours=("BatsmanRun", lambda s: (s == 4).sum()),
                                sixes=("BatsmanRun", lambda s: (s == 6).sum()),
                                seasons=("season", "nunique"))
    outs = b[b["IsWicketDelivery"] == 1].groupby("PlayerOut").size()
    g["dismissals"] = outs.reindex(g.index, fill_value=0)
    g["average"] = (g["runs"] / g["dismissals"].where(g["dismissals"] > 0)).round(2)
    g["strike_rate"] = (100 * g["runs"] / g["balls"]).round(2)
    top_runs = g.sort_values("runs", ascending=False).head(10).reset_index()
    fastest = g[g["balls"] >= 1500].sort_values("strike_rate", ascending=False).head(10).reset_index()
    return top_runs, fastest


def bowling(b):
    g = b.groupby("Bowler").agg(wickets=("bowler_wkt", "sum"), legal_balls=("legal", "sum"),
                                runs_conceded=("bowler_runs", "sum"))
    g["economy"] = (6 * g["runs_conceded"] / g["legal_balls"]).round(2)
    g["average"] = (g["runs_conceded"] / g["wickets"].where(g["wickets"] > 0)).round(2)
    death = b[b["phase"] == "Death (16-20)"].groupby("Bowler").agg(death_balls=("legal", "sum"),
                                                                   death_runs=("bowler_runs", "sum"))
    g = g.join(death)
    g["death_economy"] = (6 * g["death_runs"] / g["death_balls"]).round(2)
    top_wkts = g.sort_values("wickets", ascending=False).head(10).reset_index()
    tight = g[g["legal_balls"] >= 1500].sort_values("economy").head(10).reset_index()
    return top_wkts, tight


def venues(m, b):
    first = b[b["Innings"] == 1].groupby("ID")["TotalRun"].sum().rename("first_innings")
    v = m.set_index("match_number").join(first)
    v["defended"] = v.apply(lambda r: r["result"] == "Win" and r["winner"] == (
        r["toss_winner"] if r["toss_decision"] == "bat" else (r["team2"] if r["toss_winner"] == r["team1"] else r["team1"])), axis=1)
    t = v.groupby("venue_name").agg(matches=("season", "size"), avg_first_innings=("first_innings", "mean"),
                                    bat_first_won_pct=("defended", "mean"))
    t["bat_first_won_pct"] *= 100
    return t[t["matches"] >= 30].round(1).sort_values("avg_first_innings", ascending=False).reset_index()


def charts(trend, phase, toss, top_runs):
    def style(ax):
        ax.spines[["top", "right"]].set_visible(False)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(trend["season"], trend["avg_first_innings"], color=BLUE, marker="o", label="Average first-innings score")
    ax.set(ylabel="Runs", title="Average first-innings score by season")
    ax.axvline(2023 - 0.5, color=GREY, ls="--", lw=1)
    ax.text(2022.3, trend["avg_first_innings"].max() - 8, "Impact Player rule\nfrom 2023", ha="right", fontsize=9, color=GREY)
    ax.set_xticks(trend["season"], trend["season"], rotation=45)
    style(ax)
    fig.savefig(OUT / "chart_scoring_by_season.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(trend["season"], trend["sixes_per_match"], color=GOLD)
    ax.set(ylabel="Sixes per match", title="Sixes per match by season")
    ax.set_xticks(trend["season"], trend["season"], rotation=45)
    style(ax)
    fig.savefig(OUT / "chart_sixes_by_season.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    for col, c in zip(phase.columns[1:], [BLUE, GREY, GOLD]):
        ax.plot(phase["season"], phase[col], marker="o", color=c, label=col)
    ax.set(ylabel="Runs per over", title="Run rate by phase of the innings")
    ax.set_xticks(phase["season"], phase["season"], rotation=45)
    ax.legend(frameon=False)
    style(ax)
    fig.savefig(OUT / "chart_phase_run_rate.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(toss["season"], toss["chose_to_field_pct"], marker="o", color=BLUE, label="Toss winner chose to field")
    ax.plot(toss["season"], toss["chasing_team_won_pct"], marker="o", color=GOLD, label="Chasing team won")
    ax.axhline(50, color=GREY, lw=1, ls=":")
    ax.set(ylabel="% of matches", title="Toss decisions and chasing success")
    ax.set_xticks(toss["season"], toss["season"], rotation=45)
    ax.legend(frameon=False)
    style(ax)
    fig.savefig(OUT / "chart_toss_and_chasing.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(top_runs["Batter"][::-1], top_runs["runs"][::-1], color=BLUE)
    for y, (r, sr) in enumerate(zip(top_runs["runs"][::-1], top_runs["strike_rate"][::-1])):
        ax.text(r + 50, y, f"{r:,}  (SR {sr:.0f})", va="center", fontsize=9)
    ax.set(xlabel="Runs", title="Top 10 run scorers, 2008-2026", xlim=(0, top_runs["runs"].max() * 1.25))
    style(ax)
    fig.savefig(OUT / "chart_top_run_scorers.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    m, b = load()
    trend = season_trends(m, b)
    phase = phase_rates(b)
    toss, toss_all = toss_and_chasing(m)
    team_table, finals = teams(m)
    top_runs, fastest = batting(b)
    top_wkts, tight = bowling(b)
    venue_table = venues(m, b)
    pom = m["player_of_match"].value_counts().head(10).rename_axis("player").reset_index(name="awards")

    tables = {"season_trends": trend, "phase_run_rate": phase, "toss_and_chasing": toss, "teams": team_table,
              "finals": finals, "top_run_scorers": top_runs, "fastest_scorers": fastest,
              "top_wicket_takers": top_wkts, "most_economical": tight, "venues": venue_table,
              "player_of_match": pom}
    for name, df in tables.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
    charts(trend, phase, toss, top_runs)

    t = trend.set_index("season")
    first_inn = b[b["Innings"] == 1].groupby(["ID", "season"])["TotalRun"].sum().rename("runs").reset_index()
    summary = {
        "matches": len(m), "deliveries": len(b), "seasons": int(m["season"].nunique()),
        "first_season": int(m["season"].min()), "last_season": int(m["season"].max()),
        "avg_first_innings_2008_2022": round(first_inn[first_inn["season"] <= 2022]["runs"].mean(), 1),
        "avg_first_innings_2023_2026": round(first_inn[first_inn["season"] >= 2023]["runs"].mean(), 1),
        "sixes_per_match_2008": float(t.loc[2008, "sixes_per_match"]),
        "sixes_per_match_last": float(t.iloc[-1]["sixes_per_match"]),
        "200_plus_2008_2022": int(t.loc[2008:2022, "200_plus_totals"].sum()),
        "200_plus_2023_2026": int(t.loc[2023:2026, "200_plus_totals"].sum()),
        "toss": toss_all,
        "titles": team_table[team_table["titles"] > 0][["team", "titles"]].to_dict(orient="records"),
        "top_run_scorer": top_runs.iloc[0][["Batter", "runs", "strike_rate"]].to_dict(),
        "top_wicket_taker": top_wkts.iloc[0][["Bowler", "wickets", "economy"]].to_dict(),
        "phase_first_last": {"first": phase.iloc[0].to_dict(), "last": phase.iloc[-1].to_dict()},
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
