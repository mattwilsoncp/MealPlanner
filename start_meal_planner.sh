#!/bin/bash
# Meal Planner App v2 - Startup Script

APP_DIR="$HOME/source/meal_planner_app_v2"
VENV_DIR="$APP_DIR/.venv"
HOST="192.168.4.28"
PORT="8000"

cd "$APP_DIR" || exit 1
source "$VENV_DIR/bin/activate"
exec python manage.py runserver "$HOST:$PORT"
