#!/bin/bash

echo "Going to pull chnages from gitbuh repo.."
git pull origin main

echo "ALL CHANGES PULLED"

echo "Starting the bot..."
python3 bot.py
