import time
import random
import json
import os
import pygame
import schedule
from flask import Flask, render_template, jsonify, request, session
import threading
from datetime import datetime, timedelta
from gtts import gTTS

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# File paths for logging
HEALTH_LOG_FILE = "logs/health_log.json"
ACTIVITY_LOG_FILE = "logs/activity_log.json"
SCHEDULE_FILE = "logs/schedule.json"
CUSTOM_REMINDERS_FILE = "logs/custom_reminders.json"

# Initialize logs if they don't exist
for file in [HEALTH_LOG_FILE, ACTIVITY_LOG_FILE, SCHEDULE_FILE, CUSTOM_REMINDERS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)

# Global flag to manage audio playback
playing = False
audio_lock = threading.Lock()

# Initialize pygame mixer for audio
try:
    pygame.mixer.init()
except Exception as e:
    print(f"Failed to initialize pygame.mixer: {e}")

# Health Monitoring Agent
class HealthMonitoringAgent:
    def __init__(self):
        self.heart_rate = None
        self.blood_pressure = (None, None)
        self.glucose = None
        self.hr_threshold = 100
        self.bp_threshold = (140, 90)
        self.bp_low_threshold = (90, 60)
        self.glucose_threshold = 130
        self.glucose_low_threshold = 70
        self.last_activity_time = time.time()
        self.health_status = "Normal"
        self.last_health_status = "Normal"
        self.last_user_input_time = time.time()

    def monitor_health(self, heart_rate=None, blood_pressure=None, glucose=None, is_sensor=False):
        if heart_rate is not None and blood_pressure is not None and glucose is not None:
            self.heart_rate = heart_rate
            self.blood_pressure = blood_pressure
            self.glucose = glucose
            self.last_user_input_time = time.time()
            source = "User Input" if not is_sensor else "Sensor Input"
        else:
            return False, "No new data to monitor."

        log_entry = {
            "timestamp": time.ctime(),
            "heart_rate": self.heart_rate,
            "blood_pressure": f"{self.blood_pressure[0]}/{self.blood_pressure[1]}",
            "glucose": self.glucose,
            "event": None,
            "source": source
        }
        self._log_data(HEALTH_LOG_FILE, log_entry)

        hr_risk = self.heart_rate > self.hr_threshold
        bp_high_risk = self.blood_pressure[0] > self.bp_threshold[0] or self.blood_pressure[1] > self.bp_threshold[1]
        bp_low_risk = self.blood_pressure[0] < self.bp_low_threshold[0] or self.blood_pressure[1] < self.bp_low_threshold[1]
        glucose_high_risk = self.glucose > self.glucose_threshold
        glucose_low_risk = self.glucose < self.glucose_low_threshold

        risk_message = ""
        if hr_risk or bp_high_risk or bp_low_risk or glucose_high_risk or glucose_low_risk:
            risk_message = "At Risk"
        else:
            risk_message = "Healthy"

        self.last_health_status = self.health_status
        self.health_status = "At Risk" if risk_message == "At Risk" else "Normal"
        return True, risk_message

    def detect_unusual_behavior(self):
        current_time = time.time()
        if (current_time - self.last_activity_time) > 1800:
            return True, "Inactivity detected: No movement for 30 minutes."
        return False, "Activity normal."

    def detect_fall(self):
        if random.random() < 0.1:
            log_entry = {
                "timestamp": time.ctime(),
                "heart_rate": self.heart_rate,
                "blood_pressure": f"{self.blood_pressure[0]}/{self.blood_pressure[1]}",
                "glucose": self.glucose,
                "event": "Fall detected"
            }
            self._log_data(HEALTH_LOG_FILE, log_entry)
            return True, "Fall detected!"
        return False, "No fall detected."

    def _log_data(self, file, entry):
        with open(file, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
        data.append(entry)
        with open(file, "w") as f:
            json.dump(data, f)

    def _play_voice(self, message, language):
        global playing, audio_lock
        with audio_lock:
            if playing:
                print("Audio already playing, skipping new request.")
                return
            playing = True

        def play_audio():
            global playing
            try:
                audio_file = f"temp_{int(time.time() * 1000)}.mp3"
                print(f"Generating audio for: {message} in language: {language}")
                lang_code = "hi" if language == "hi" else "en"
                tts = gTTS(text=message, lang=lang_code)
                tts.save(audio_file)
                print(f"Audio file saved as: {audio_file}")
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                os.remove(audio_file)
                print(f"Audio playback completed and file {audio_file} removed.")
            except Exception as e:
                print(f"Error in audio playback: {e}")
                self._log_activity(f"Voice playback failed for '{message}' in {language}: {e}")
            finally:
                with audio_lock:
                    playing = False

        threading.Thread(target=play_audio, daemon=True).start()

# Health Suggestions Agent
class HealthSuggestionsAgent(HealthMonitoringAgent):
    def __init__(self):
        super().__init__()
        self.suggestions = {
            "high_heart_rate": "Your heart rate is high. Please try to rest and breathe deeply.",
            "high_bp": "Your blood pressure is high. Please sit down and avoid stress.",
            "low_bp": "Your blood pressure is low. Please have some water or a snack.",
            "high_glucose": "Your glucose is high. Avoid sweets and consult your doctor.",
            "low_glucose": "Your glucose is low. Please eat a small piece of fruit."
        }

    def get_suggestions(self, heart_rate, blood_pressure, glucose, hr_threshold, bp_threshold, bp_low_threshold, glucose_threshold, glucose_low_threshold):
        suggestions = []
        if heart_rate > hr_threshold:
            suggestions.append(self.suggestions["high_heart_rate"])
        if blood_pressure[0] > bp_threshold[0] or blood_pressure[1] > bp_threshold[1]:
            suggestions.append(self.suggestions["high_bp"])
        if blood_pressure[0] < bp_low_threshold[0] or blood_pressure[1] < bp_low_threshold[1]:
            suggestions.append(self.suggestions["low_bp"])
        if glucose > glucose_threshold:
            suggestions.append(self.suggestions["high_glucose"])
        if glucose < glucose_low_threshold:
            suggestions.append(self.suggestions["low_glucose"])
        return suggestions

# Reminder Agent
class ReminderAgent:
    def __init__(self):
        self.schedule = [
            {"task": "Take your morning medication", "language": "en", "critical": True, "time": None, "category": "medicine", "triggered": False},
            {"task": "सुबह की दवा लें", "language": "hi", "critical": True, "time": None, "category": "medicine", "triggered": False},
            {"task": "Go for a short walk", "language": "en", "critical": False, "time": None, "category": "other", "triggered": False},
            {"task": "डॉक्टर के पास जाएं", "language": "hi", "critical": True, "time": None, "category": "doctor", "triggered": False}
        ]
        self.custom_reminders = []
        self._load_schedule()
        self._load_custom_reminders()
        self.job = None

    def _load_schedule(self):
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, "r") as f:
                try:
                    self.schedule = json.load(f)
                except json.JSONDecodeError:
                    pass

    def _load_custom_reminders(self):
        if os.path.exists(CUSTOM_REMINDERS_FILE):
            with open(CUSTOM_REMINDERS_FILE, "r") as f:
                try:
                    self.custom_reminders = json.load(f)
                except json.JSONDecodeError:
                    pass

    def adjust_schedule(self, health_status, unusual_behavior=False, delay_minutes=10):
        if health_status or unusual_behavior:
            for task in self.schedule:
                if task["critical"]:
                    task["time"] = datetime.now() + timedelta(minutes=delay_minutes)
                    self._log_activity(f"Delaying task '{task['task']}' due to {'health risk' if health_status else 'unusual behavior'}")
                    self._play_voice(f"Delaying your task '{task['task']}'. Please rest for now.", task["language"])
                else:
                    task["time"] = "Skipped"
                    self._log_activity(f"Skipping task '{task['task']}' due to {'health risk' if health_status else 'unusual behavior'}")
                    self._play_voice(f"Skipping your task '{task['task']}'. Please rest.", task["language"])
                task["triggered"] = False
            for reminder in self.custom_reminders:
                if reminder.get("critical", False):
                    reminder["time"] = datetime.now() + timedelta(minutes=delay_minutes)
                    self._log_activity(f"Delaying custom reminder '{reminder['message']}'")
                    self._play_voice(f"Delaying your reminder '{reminder['message']}'. Please rest.", "en")
                else:
                    reminder["time"] = "Skipped"
                    self._log_activity(f"Skipping custom reminder '{reminder['message']}'")
                    self._play_voice(f"Skipping your reminder '{reminder['message']}. Please rest.", "en")
            self._save_schedule()
            self._save_custom_reminders()
            self._play_voice("Adjusting your schedule due to health or behavior. Please rest.", session.get("language", "en"))
        else:
            for task in self.schedule:
                if task.get("time") and isinstance(task.get("time"), datetime) and task["time"] < datetime.now():
                    task["time"] = None
                task["triggered"] = False
            for reminder in self.custom_reminders:
                if reminder.get("time") and isinstance(reminder.get("time"), datetime) and reminder["time"] < datetime.now():
                    reminder["time"] = None
            self._save_schedule()
            self._save_custom_reminders()
            self._play_voice("Your health has improved. Schedule restored.", session.get("language", "en"))

    def schedule_reminder(self, task):
        if task.get("time") and isinstance(task.get("time"), datetime):
            task_time = task["time"].strftime("%H:%M")
            schedule.every().day.at(task_time).do(self._trigger_reminder, task)
            self._log_activity(f"Scheduled reminder: {task['task']} at {task_time}")

    def _trigger_reminder(self, task):
        if not task.get("triggered", False):
            category_message = {
                "medicine": "Time to take your medicine",
                "doctor": "Time to visit the doctor",
                "other": "Time for your activity"
            }.get(task["category"], "Time for your task")
            message = f"{category_message}: {task['task']}"
            self._log_activity(message)
            self._play_voice(message, task["language"])
            self._play_voice("Have you completed this? (Simulated: Yes)", task["language"])
            self._log_activity("User confirmed: Yes")
            task["triggered"] = True
            self._save_schedule()

    def schedule_custom_reminder(self, reminder):
        if reminder.get("time") and isinstance(reminder.get("time"), datetime):
            reminder_time = reminder["time"].strftime("%H:%M")
            schedule.every().day.at(reminder_time).do(self._trigger_custom_reminder, reminder)
            self._log_activity(f"Scheduled custom reminder: {reminder['message']} at {reminder_time}")

    def _trigger_custom_reminder(self, reminder):
        if "triggered" not in reminder:
            category_message = {
                "medicine": "Time to take your medicine",
                "doctor": "Time to visit the doctor",
                "other": "Time for your activity"
            }.get(reminder.get("category", "other"), "Time for your task")
            message = f"{category_message}: {reminder['message']}"
            self._log_activity(f"Triggering reminder: {message}")
            self._play_voice(message, session.get("language", "en"))
            reminder["triggered"] = True
            self._save_custom_reminders()

    def set_custom_reminder(self, time_str, message, category="other", critical=False):
        reminder_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        reminder = {"time": reminder_time, "message": message, "category": category, "critical": critical}
        self.custom_reminders.append(reminder)
        self.schedule_custom_reminder(reminder)
        self._save_custom_reminders()
        self._log_activity(f"Set custom reminder: {message} at {time_str}")

    def _save_schedule(self):
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(self.schedule, f)

    def _save_custom_reminders(self):
        with open(CUSTOM_REMINDERS_FILE, "w") as f:
            json.dump(self.custom_reminders, f)

    def _log_activity(self, message):
        with open(ACTIVITY_LOG_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
        data.append({"timestamp": time.ctime(), "activity": message})
        with open(ACTIVITY_LOG_FILE, "w") as f:
            json.dump(data[-5:], f)

    def _play_voice(self, message, language):
        global playing, audio_lock
        with audio_lock:
            if playing:
                print("Audio already playing, skipping new request.")
                return
            playing = True

        def play_audio():
            global playing
            try:
                audio_file = f"temp_{int(time.time() * 1000)}.mp3"
                print(f"Generating audio for: {message} in language: {language}")
                lang_code = "hi" if language == "hi" else "en"
                tts = gTTS(text=message, lang=lang_code)
                tts.save(audio_file)
                print(f"Audio file saved as: {audio_file}")
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                os.remove(audio_file)
                print(f"Audio playback completed and file {audio_file} removed.")
            except Exception as e:
                print(f"Error in audio playback: {e}")
                self._log_activity(f"Voice playback failed for '{message}' in {language}: {e}")
            finally:
                with audio_lock:
                    playing = False

        threading.Thread(target=play_audio, daemon=True).start()

# Social Engagement Agent (Chatbot)
class SocialEngagementAgent:
    def __init__(self):
        self.activities = {
            "en": {
                "welcome": {
                    "male": "Welcome, Grandpa!",
                    "female": "Welcome, Grandma!"
                },
                "questions": [
                    "That’s a wonderful memory! Do you have any other special moments?",
                    "I enjoy hearing about your day. What else is on your mind?",
                    "What a lovely story! Have you had any fun adventures lately?",
                    "That sounds exciting! Tell me more about your friends.",
                    "I’m all ears! What’s something new happening in your life?"
                ],
                "labels": {
                    "heart_rate": "Heart Rate (bpm)",
                    "blood_pressure": "Blood Pressure (Systolic/Diastolic)",
                    "glucose": "Glucose (mg/dL)",
                    "submit_health": "Submit Health Data",
                    "reminder_time": "Reminder Time (YYYY-MM-DD HH:MM)",
                    "reminder_message": "Reminder Message",
                    "reminder_category": "Category",
                    "set_reminder": "Set Reminder",
                    "chat": "Let's Chat!",
                    "type_message": "Type your message...",
                    "send": "Send",
                    "start_chat": "Start Chat",
                    "recent_health": "Your Recent Health"
                },
                "keywords": {
                    "happy": "I’m glad you’re feeling happy! What made your day special?",
                    "good": "That’s great to hear! Any plans for today?",
                    "family": "Family is so important. Who’s your favorite person to spend time with?",
                    "tired": "I’m sorry you’re tired. Would you like a tip to relax?",
                    "birthday": "What a surprise! Did you celebrate with cake?",
                    "friends": "Your friends sound amazing! What do you love most about them?",
                    "summer": "Summer sounds wonderful! What’s your favorite summer activity?",
                    "enjoying": "I’m happy you’re enjoying yourself! What else are you doing?",
                    "fun": "That sounds fun! What other activities do you enjoy?",
                    "great": "Great to know! What’s making your day great?",
                    "default": [
                        "That’s interesting! Tell me more about what you enjoy related to that.",
                        "I’d love to hear more about that topic. What else can you share?",
                        "That sounds lovely! Can you tell me more about your experience?"
                    ]
                }
            },
            "hi": {
                "welcome": {
                    "male": "नमस्ते बाबाजी!",
                    "female": "नमस्ते अम्माजी!"
                },
                "questions": [
                    "यह एक अद्भुत याद है! क्या आपके पास कोई अन्य विशेष पल हैं?",
                    "मुझे आपके दिन के बारे में सुनना अच्छा लगता है। और क्या आपके दिमाग में है?",
                    "क्या शानदार कहानी! हाल ही में कोई मज़ेदार साहसिक कार्य हुआ?",
                    "यह रोमांचक लगता है! अपने दोस्तों के बारे में और बताएं।",
                    "मैं सुनने के लिए तैयार हूँ! आपके जीवन में क्या नया हो रहा है?"
                ],
                "labels": {
                    "heart_rate": "हृदय गति (बीपीएम)",
                    "blood_pressure": "रक्तचाप (सिस्टोलिक/डायस्टोलिक)",
                    "glucose": "ग्लूकोज (मिलीग्राम/डीएल)",
                    "submit_health": "स्वास्थ्य डेटा सबमिट करें",
                    "reminder_time": "रिमाइंडर समय (YYYY-MM-DD HH:MM)",
                    "reminder_message": "रिमाइंडर संदेश",
                    "reminder_category": "श्रेणी",
                    "set_reminder": "रिमाइंडर सेट करें",
                    "chat": "चैट शुरू करें!",
                    "type_message": "अपना संदेश टाइप करें...",
                    "send": "भेजें",
                    "start_chat": "चैट शुरू करें",
                    "recent_health": "आपका हालिया स्वास्थ्य"
                },
                "keywords": {
                    "खुश": "मुझे खुशी है कि आप खुश हैं! आपके दिन को खास क्या बनाया?",
                    "अच्छा": "यह सुनकर अच्छा लगा! आज आपके कोई प्लान हैं?",
                    "परिवार": "परिवार बहुत महत्वपूर्ण है। आपका पसंदीदा व्यक्ति कौन है?",
                    "थका": "मुझे दुख है कि आप थके हैं। क्या आपको आराम की सलाह चाहिए?",
                    "जन्मदिन": "क्या आश्चर्यजनक पल! क्या आपने केक के साथ जश्न मनाया?",
                    "दोस्त": "आपके दोस्त शानदार लगते हैं! आप उन्हें सबसे ज्यादा क्या पसंद करते हैं?",
                    "गर्मी": "गर्मी अद्भुत लगती है! आपका पसंदीदा गर्मी का काम क्या है?",
                    "आनंद": "मुझे खुशी है कि आप आनंद ले रहे हैं! और क्या कर रहे हैं?",
                    "मज़ा": "यह मज़ेदार लगता है! आप और कौन सी गतिविधियाँ पसंद करते हैं?",
                    "शानदार": "शानदार जानकर अच्छा लगा! आपका दिन शानदार क्यों है?",
                    "default": [
                        "यह रोचक है! उससे संबंधित और बताएं।",
                        "मुझे उस विषय पर और सुनना अच्छा लगेगा। और क्या बता सकते हैं?",
                        "यह प्यारा लगता है! अपने अनुभव के बारे में और बताएं।"
                    ]
                }
            }
        }
        self.chat_history = []
        self.current_language = "en"
        self.last_audio_time = 0
        self.audio_cooldown = 2  # 2-second cooldown between audios

    def start_chat(self, language="en", gender="male"):
        self.chat_history = []
        self.current_language = language
        greeting = self.activities[language]["welcome"][gender]
        self.chat_history.append({"role": "system", "message": greeting})
        self._log_activity(f"Chat started in {language} for {gender}: {greeting}")
        self._play_voice(greeting, language)
        return self.chat_history

    def respond_to_user(self, user_message, language="en", gender="male"):
        self.chat_history.append({"role": "user", "message": user_message})
        self._log_activity(f"User: {user_message}")

        activity = self.activities[language]
        user_message_lower = user_message.lower()
        response = random.choice(activity["keywords"]["default"])  # Default response

        # Enhanced keyword matching for context
        for keyword, replies in activity["keywords"].items():
            if keyword in user_message_lower and not response.startswith("That’s interesting!") and not response.startswith("I’d love to hear"):
                if isinstance(replies, list):
                    response = random.choice(replies)
                else:
                    response = replies
                break

        current_time = time.time()
        if current_time - self.last_audio_time >= self.audio_cooldown:
            self.chat_history.append({"role": "system", "message": response})
            self._play_voice(response, language)
            self.last_audio_time = current_time
        else:
            self.chat_history.append({"role": "system", "message": response + " (Audio delayed due to cooldown)"})
            print(f"Audio delayed for: {response}")

        self._log_activity(response)
        return self.chat_history

    def _log_activity(self, message):
        with open(ACTIVITY_LOG_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
        data.append({"timestamp": time.ctime(), "activity": message})
        with open(ACTIVITY_LOG_FILE, "w") as f:
            json.dump(data[-5:], f)

    def _play_voice(self, message, language):
        global playing, audio_lock
        with audio_lock:
            if playing:
                print("Audio already playing, skipping new request.")
                return
            playing = True

        def play_audio():
            global playing
            try:
                audio_file = f"temp_{int(time.time() * 1000)}.mp3"
                print(f"Generating audio for: {message} in language: {language}")
                lang_code = "hi" if language == "hi" else "en"
                tts = gTTS(text=message, lang=lang_code)
                tts.save(audio_file)
                print(f"Audio file saved as: {audio_file}")
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                os.remove(audio_file)
                print(f"Audio playback completed and file {audio_file} removed.")
            except Exception as e:
                print(f"Error in audio playback: {e}")
                self._log_activity(f"Voice playback failed for '{message}' in {language}: {e}")
            finally:
                with audio_lock:
                    playing = False

        threading.Thread(target=play_audio, daemon=True).start()

# Collaboration Agent
class CollaborationAgent:
    def send_alert(self, message, emergency=False, priority="Medium"):
        alert_message = f"Alert (Priority: {priority}): {message}"
        if emergency:
            alert_message += " Notifying local contact: Neighbor John to check on user. Estimated arrival: 5 minutes."
        self._log_activity(alert_message)
        self._play_voice(alert_message, session.get("language", "en"))
        return alert_message

    def confirm_action(self, message):
        self._play_voice(f"Caregiver, {message} Did you help them rest? (Simulated: Yes)", session.get("language", "en"))
        self._log_activity("Caregiver confirmed: Yes")
        return "Caregiver confirmed: Yes"

    def _log_activity(self, message):
        with open(ACTIVITY_LOG_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
        data.append({"timestamp": time.ctime(), "activity": message})
        with open(ACTIVITY_LOG_FILE, "w") as f:
            json.dump(data[-5:], f)

    def _play_voice(self, message, language):
        global playing, audio_lock
        with audio_lock:
            if playing:
                print("Audio already playing, skipping new request.")
                return
            playing = True

        def play_audio():
            global playing
            try:
                audio_file = f"temp_{int(time.time() * 1000)}.mp3"
                print(f"Generating audio for: {message} in language: {language}")
                lang_code = "hi" if language == "hi" else "en"
                tts = gTTS(text=message, lang=lang_code)
                tts.save(audio_file)
                print(f"Audio file saved as: {audio_file}")
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                os.remove(audio_file)
                print(f"Audio playback completed and file {audio_file} removed.")
            except Exception as e:
                print(f"Error in audio playback: {e}")
                self._log_activity(f"Voice playback failed for '{message}' in {language}: {e}")
            finally:
                with audio_lock:
                    playing = False

        threading.Thread(target=play_audio, daemon=True).start()

# Main System
class ElderlyCareSystem:
    def __init__(self):
        self.health_agent = HealthMonitoringAgent()
        self.reminder_agent = ReminderAgent()
        self.social_agent = SocialEngagementAgent()
        self.collaboration_agent = CollaborationAgent()
        self.suggestions_agent = HealthSuggestionsAgent()

    def run(self):
        print("Starting Elderly Care System...\n")
        last_alert_reset = time.time()

        # Schedule existing reminders
        for task in self.reminder_agent.schedule:
            self.reminder_agent.schedule_reminder(task)
        for reminder in self.reminder_agent.custom_reminders:
            self.reminder_agent.schedule_custom_reminder(reminder)

        # Start reminder scheduler
        reminder_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        reminder_thread.start()

        while True:
            print("=== Health Monitoring ===")
            risk_detected, risk_message = self.health_agent.monitor_health(self.health_agent.heart_rate, self.health_agent.blood_pressure, self.health_agent.glucose)
            if risk_detected:
                self.collaboration_agent.send_alert(risk_message, emergency=True, priority="High")
                self.collaboration_agent.confirm_action(f"Health risk detected: {risk_message}")
                suggestions = self.suggestions_agent.get_suggestions(
                    self.health_agent.heart_rate,
                    self.health_agent.blood_pressure,
                    self.health_agent.glucose,
                    self.health_agent.hr_threshold,
                    self.health_agent.bp_threshold,
                    self.health_agent.bp_low_threshold,
                    self.health_agent.glucose_threshold,
                    self.health_agent.glucose_low_threshold
                )
                for suggestion in suggestions:
                    self.suggestions_agent._play_voice(suggestion, session.get("language", "en"))
                self.reminder_agent.adjust_schedule(risk_detected)
            else:
                if self.health_agent.health_status != self.health_agent.last_health_status:
                    self.suggestions_agent._play_voice("Your health is normal. You’re doing great!", session.get("language", "en"))

            print("\n=== Fall Detection ===")
            fall_detected, fall_message = self.health_agent.detect_fall()
            if fall_detected and not risk_detected:
                self.collaboration_agent.send_alert(fall_message, emergency=True, priority="Critical")
                self.suggestions_agent._play_voice("A fall has been detected. Help is on the way.", session.get("language", "en"))

            print("\n=== Safety Monitoring ===")
            unusual_detected, unusual_message = self.health_agent.detect_unusual_behavior()
            if unusual_detected and not risk_detected:
                self.social_agent.start_chat(session.get("language", "en"), session.get("gender", "male"))
                self.collaboration_agent.send_alert(unusual_message, priority="Medium")
                self.reminder_agent.adjust_schedule(health_status=False, unusual_behavior=True)

            if time.time() - last_alert_reset >= 86400:  # 24 hours
                with open(ACTIVITY_LOG_FILE, "r") as f:
                    try:
                        activity_log = json.load(f)
                    except json.JSONDecodeError:
                        activity_log = []
                activity_log = [entry for entry in activity_log if not entry.get("timestamp", "").startswith(time.ctime().split()[0])]
                with open(ACTIVITY_LOG_FILE, "w") as f:
                    json.dump(activity_log, f)
                last_alert_reset = time.time()

            time.sleep(300)  # Check every 5 minutes

    def _run_scheduler(self):
        while True:
            schedule.run_pending()
            time.sleep(1)

# Flask Routes
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        if 'language' in request.form:
            session['language'] = request.form['language']
        if 'gender' in request.form:
            session['gender'] = request.form['gender']
    try:
        with open(HEALTH_LOG_FILE, "r") as f:
            health_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        health_data = []
    for entry in health_data:
        entry.setdefault('heart_rate', 0)
        entry.setdefault('glucose', 0)
    try:
        with open(ACTIVITY_LOG_FILE, "r") as f:
            activity_log = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        activity_log = []
    latest_health = health_data[-1] if health_data else {}
    alerts_today = sum(1 for log in activity_log if "Alert" in log["activity"] and log.get("timestamp", "").startswith(time.ctime().split()[0])) if activity_log else 0
    system = ElderlyCareSystem()
    labels = system.social_agent.activities[session.get("language", "en")]["labels"]
    chat_history = session.get('chat_history', [])
    return render_template("dashboard.html", health_data=health_data[-5:], activity_log=activity_log[-5:], latest_health=latest_health, alerts_today=alerts_today, language=session.get("language", "en"), gender=session.get("gender", "male"), labels=labels, chat_history=chat_history)

@app.route('/api/health')
def get_health():
    try:
        with open(HEALTH_LOG_FILE, "r") as f:
            health_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        health_data = []
    return jsonify(health_data[-5:])

@app.route('/api/activity')
def get_activity():
    try:
        with open(ACTIVITY_LOG_FILE, "r") as f:
            activity_log = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        activity_log = []
    return jsonify(activity_log[-5:])

@app.route('/set_reminder', methods=['POST'])
def set_reminder():
    data = request.form
    reminder_time = data.get('time')
    message = data.get('message')
    category = data.get('category', 'other')
    critical = data.get('critical', False) == 'true'
    if reminder_time and message:
        system = ElderlyCareSystem()
        system.reminder_agent.set_custom_reminder(reminder_time, message, category, critical)
        return jsonify({"status": "success", "message": "Reminder set successfully"})
    return jsonify({"status": "error", "message": "Invalid input"})

@app.route('/submit_health', methods=['POST'])
def submit_health():
    data = request.form
    try:
        heart_rate = int(data.get('heart_rate', 0))
        bp_systolic = int(data.get('bp_systolic', 0))
        bp_diastolic = int(data.get('bp_diastolic', 0))
        glucose = int(data.get('glucose', 0))
        if not (heart_rate and bp_systolic and bp_diastolic and glucose):
            return jsonify({"status": "error", "message": "All fields are required"})
        system = ElderlyCareSystem()
        _, health_status = system.health_agent.monitor_health(heart_rate, (bp_systolic, bp_diastolic), glucose)
        message = f"Successful submission. Your health status is {health_status}."
        system.health_agent._play_voice(message, session.get("language", "en"))
        return jsonify({"status": "success", "message": message, "health_status": health_status})
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid input"})

@app.route('/api/start_chat', methods=['POST'])
def start_chat():
    system = ElderlyCareSystem()
    language = session.get("language", "en")
    gender = session.get("gender", "male")
    chat_history = system.social_agent.start_chat(language, gender)
    session['chat_history'] = chat_history
    return jsonify({"chat_history": chat_history})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"chat_history": [{"role": "system", "message": "Please enter a message."}]})
    system = ElderlyCareSystem()
    language = session.get("language", "en")
    gender = session.get("gender", "male")
    chat_history = system.social_agent.respond_to_user(user_message, language, gender)
    session['chat_history'] = chat_history
    return jsonify({"chat_history": chat_history})

if __name__ == "__main__":
    system = ElderlyCareSystem()
    threading.Thread(target=system.run, daemon=True).start()
    app.run(debug=True, port=5000)