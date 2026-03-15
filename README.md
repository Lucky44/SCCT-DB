# SCCT — Star Citizen Component Tracker Database
         by Tripp Robbins — v0.71

A local web app for tracking your Star Citizen fleet, loadouts, and inventory. Runs entirely on your machine — no account, no cloud, no fees. This is a lite version, similar to SC Ship Performance Viewer or Erkul.games, and it's made to be personal for one user.

![Dashboard](app/static/images/readme-screenshot.png)

## Features

- **My Hangar** — track your ships, assign nicknames and notes, drag to reorder ships in the hangar
- **Loadouts** — see each ship's default component slots; equip components and weapons from the database
- **In Storage** — track components and weapons you have stored off ships
- **Power Allocation** — visualize and adjust power distribution across ship systems
- **Browse Data** — searchable/filterable database of all ships, components, and weapons

## Quick Start (Windows)

1. Download `SCCT.exe` from [Releases](../../releases)
2. Double-click to run — your browser will open automatically
3. On first launch, click **Update Game Data** on the Dashboard to import ships and components

> Windows may show a SmartScreen warning. Click **More info → Run anyway**.

## Running from Source

Requires Python 3.10+.

```bash
git clone https://github.com/Lucky44/SCCT-DB.git
cd SCCT-DB
python -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python run.py
```

Then open `http://127.0.0.1:5000` in your browser.

On first run, click **Update Game Data** on the Dashboard.

## Data

Ship/component data is sourced from [scunpacked-data](https://github.com/StarCitizenTools/scunpacked-data). Your fleet and inventory are stored locally in `%APPDATA%\SCCT\scct.db` and are never affected by game data updates.

## Stack

Flask · SQLAlchemy · SQLite · Bootstrap 5
