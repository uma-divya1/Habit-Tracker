# Habit Tracker

A full-stack habit tracking web app built with **Flask** (Python) and vanilla **HTML/CSS**. Track daily habits, build streaks, and visualize your consistency with a GitHub-style contribution heatmap.

## Features
- Add and delete habits
- Mark a habit "done" for today with one click
- Automatic current streak and longest streak calculation
- 90-day contribution-style heatmap per habit (like GitHub's calendar)
- Simple JSON REST API endpoint (`/api/habits`) alongside the server-rendered pages
- SQLite database — zero external setup

## Tech Stack
- **Backend:** Python, Flask, sqlite3 (standard library)
- **Frontend:** HTML, CSS, Jinja2 templates
- **Database:** SQLite

## Setup

1. Create a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:
   ```bash
   python app.py
   ```

4. Open your browser to `http://127.0.0.1:5000`

The SQLite database file (`habits.db`) is created automatically on first run.

## Project Structure
```
habit-tracker/
├── app.py                    # Flask app, routes, streak logic, database
├── requirements.txt
├── Procfile                  # For deployment (Render/Railway/Heroku)
├── templates/
│   ├── base.html              # Shared layout/navbar
│   ├── index.html             # Dashboard: habit list + toggle + add form
│   └── habit_detail.html      # Single habit: stats + 90-day heatmap
└── static/
    └── style.css               # App styling, including heatmap grid
```

## How the Streak Logic Works
- **Current streak**: counts consecutive days ending today (or yesterday, if today isn't marked done yet) that the habit was completed.
- **Longest streak**: scans the full completion history for the longest run of consecutive days.
- Both are recalculated live from the `habit_log` table — no stored/cached streak values, so the data never goes stale.

## Deploying (Render example)
This repo already includes a `Procfile` and `gunicorn` in requirements.txt, so it's ready to deploy:
1. Push to GitHub
2. On Render: New → Web Service → connect your repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`

Note: Free-tier hosts often reset the filesystem on redeploy, which would wipe the SQLite file. Fine for a demo; for persistence, migrate to a hosted Postgres database.

## Possible Extensions
- User accounts so multiple people can track their own habits
- Reminders/notifications
- Weekly/monthly goal targets (e.g. "4x per week" instead of daily)
- Export history to CSV
- Habit categories or tags

## Resume Bullet Ideas
- "Built a full-stack habit tracker with Flask and SQLite, implementing custom streak-calculation logic and a GitHub-style contribution heatmap rendered with server-side templating."
- "Designed a relational schema (habits + logs) and REST API endpoint, with all statistics computed live from raw log data rather than cached values."
