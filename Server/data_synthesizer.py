import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(page_title="FRC Scouting Dashboard", layout="wide")

# -------------------------------
# LOAD DATA
# -------------------------------
csv_url = "http://localhost:5000/api/export/csv"
df = pd.read_csv(csv_url)

# Balls numeric
df["Auto Balls"] = pd.to_numeric(df["Auto Balls"], errors="coerce").fillna(0)
df["Teleop Balls"] = pd.to_numeric(df["Teleop Balls"], errors="coerce").fillna(0)

# -------------------------------
# PARSE CLIMB LEVELS
# -------------------------------
def parse_climb(value):
    if pd.isna(value):
        return 0
    value = str(value).lower()
    if "3" in value:
        return 3
    if "2" in value:
        return 2
    if "1" in value:
        return 1
    if value in ["yes", "true"]:
        return 1
    return 0

df["Auto Climb Level"] = df["Auto Climb"].apply(parse_climb)
df["Teleop Climb Level"] = df["Endgame Climb"].apply(parse_climb)

# -------------------------------
# CLEAN MATCH OUTCOME
# -------------------------------
df["Match Outcome Clean"] = df["Match Outcome"].astype(str).str.strip().str.lower()

# -------------------------------
# SCORING HELPERS
# -------------------------------
def auto_climb_points(level):
    return 15 if level in [1, 2, 3] else 0

def teleop_climb_points(level):
    return {1: 10, 2: 20, 3: 30}.get(level, 0)

# -------------------------------
# SIDEBAR FILTERS (NON-INTERSECTING)
# -------------------------------
st.sidebar.title("Filters")

# Base filter
base_filter = st.sidebar.radio(
    "Base Category (choose one)",
    ["All", "Autonomous", "Teleop", "Climb", "Shoot"]
)

# Sub filter depends on base
sub_filter_options = []
if base_filter == "Autonomous":
    sub_filter_options = ["Balls", "Climb"]
elif base_filter == "Teleop":
    sub_filter_options = ["Balls", "Climb"]
elif base_filter == "Climb":
    sub_filter_options = ["Auto", "Teleop"]
elif base_filter == "Shoot":
    sub_filter_options = ["Auto", "Teleop"]

sub_filter = st.sidebar.selectbox(
    "Sub Filter (optional)",
    ["None"] + sub_filter_options
)

# -------------------------------
# SCORE CALCULATION
# -------------------------------
def calculate_score(row):
    auto_balls = row["Auto Balls"]
    teleop_balls = row["Teleop Balls"]
    auto_climb = auto_climb_points(row["Auto Climb Level"])
    teleop_climb = teleop_climb_points(row["Teleop Climb Level"])

    # Default: sum everything
    if base_filter == "All":
        return auto_balls + teleop_balls + auto_climb + teleop_climb

    score = 0
    if base_filter == "Autonomous":
        if sub_filter == "Balls":
            score += auto_balls
        elif sub_filter == "Climb":
            score += auto_climb
        else:
            score += auto_balls + auto_climb

    elif base_filter == "Teleop":
        if sub_filter == "Balls":
            score += teleop_balls
        elif sub_filter == "Climb":
            score += teleop_climb
        else:
            score += teleop_balls + teleop_climb

    elif base_filter == "Climb":
        if sub_filter == "Auto":
            score += auto_climb
        elif sub_filter == "Teleop":
            score += teleop_climb
        else:
            score += auto_climb + teleop_climb

    elif base_filter == "Shoot":
        if sub_filter == "Auto":
            score += auto_balls
        elif sub_filter == "Teleop":
            score += teleop_balls
        else:
            score += auto_balls + teleop_balls

    return score

df["Score"] = df.apply(calculate_score, axis=1)

# -------------------------------
# WINS/LOSSES HELPER
# -------------------------------
def get_wins_losses(team_number):
    t_str = str(team_number).strip().split('.')[0]
    team_rows = df[df["Team"].astype(str).str.contains(rf"^{t_str}$", na=False)]

    outcomes = team_rows["Match Outcome Clean"].astype(str).str.lower()

    wins = outcomes.str.startswith("w", na=False).sum()
    losses = outcomes.str.startswith("l", na=False).sum()

    total = len(team_rows)
    return wins, losses, total

# -------------------------------
# AVERAGE BY TEAM
# -------------------------------
team_avg = (
    df.groupby("Team")["Score"]
    .mean()
    .reset_index()
    .sort_values("Score", ascending=False)
    .reset_index(drop=True)
)

team_avg.index += 1

# -------------------------------
# UI HEADER
# -------------------------------
st.title("🤖 FRC Team Ranking Dashboard")
st.caption("Rankings update dynamically based on selected filters")

# -------------------------------
# SEARCH TEAM
# -------------------------------
team_search = st.text_input("🔍 Search for a Team Number")

if team_search:
    team_data = team_avg[team_avg["Team"].astype(str) == team_search]

    if not team_data.empty:
        st.subheader(f"Team {team_search}")
        st.metric("Average Score", round(team_data.iloc[0]["Score"], 2))

        wins, losses, total_matches = get_wins_losses(team_search)
        win_rate = wins / total_matches * 100 if total_matches > 0 else 0
        st.write(f"Matches Played: {total_matches}  |  Wins: {wins}  |  Losses: {losses}  |  Win Rate: {win_rate:.1f}%")

    else:
        st.warning("Team not found")

else:
    top_team = team_avg.iloc[0]
    st.subheader(f"🏆 Top Team: {int(top_team['Team'])}")
    st.metric("Average Score", round(top_team["Score"], 2))

    wins, losses, total_matches = get_wins_losses(top_team["Team"])
    win_rate = wins / total_matches * 100 if total_matches > 0 else 0
    st.write(f"Matches Played: {total_matches}  |  Wins: {wins}  |  Losses: {losses}  |  Win Rate: {win_rate:.1f}%")

# -------------------------------
# FULL TEAM RANKINGS
# -------------------------------
st.divider()
st.subheader("📊 Team Rankings")
st.dataframe(team_avg, width="stretch")

# -------------------------------
# TOP 10 BAR CHART
# -------------------------------
st.divider()
st.subheader("Top 10 Teams")
top10 = team_avg.head(10)

fig, ax = plt.subplots()
ax.bar(top10["Team"].astype(str), top10["Score"], color="dodgerblue")
ax.set_ylabel("Average Score")
ax.set_xlabel("Team")
plt.xticks(rotation=45)
st.pyplot(fig)

