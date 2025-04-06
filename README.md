# Elderly Care Companion

## Overview
A web-based app to monitor and support elderly health using Python and Flask.

## Features
- Tracks heart rate, blood pressure, and glucose.
- Provides health submission feedback.
- Sets customizable reminders.
- Includes a chatbot with gender greetings.
- Detects falls and inactivity with alerts.
- Supports English and Hindi with voice.
- Responsive design with Tailwind CSS.

## Technologies
- Backend: Python, Flask
- Frontend: HTML, Tailwind CSS, JavaScript
- Libraries: gTTS, pygame, schedule

## Installation
1. git clone https://github.com/pragya-agg/ELDERLY-CARE.git
2. cd Elderly-Care
3. python -m venv venv and activate (source venv/bin/activate or venv\Scripts\activate)
4. pip install flask gtts pygame schedule
5. Create templates and logs folders, add dashboard.html to templates
6. Run: python app.py and visit http://localhost:5000

## Usage
- Submit health data for feedback.
- Set reminders with time and message.
- Chat with the companion.
- Receive alerts for safety issues.

## File Structure

elderly-care-companion/
├── templates/dashboard.html
├── logs/
│   ├── health_log.json
│   ├── activity_log.json
│   ├── schedule.json
│   └── custom_reminders.json
├── app.py
└── README.md
