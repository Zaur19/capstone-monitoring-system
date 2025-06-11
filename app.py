from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import os
import csv
import sqlite3
import openai
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)
CORS(app)

CSV_FILE = "logs.csv"
DB_FILE = "logs.db"

# Write CSV header if missing
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["DateTime", "FullName", "Age", "Symptoms", "Condition", "Urgency", "Advice"])

# Initialize DB
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT,
            datetime TEXT,
            age TEXT,
            symptoms TEXT,
            condition TEXT,
            urgency TEXT,
            advice TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    fullname = data.get("fullname", "").strip()
    symptoms = data.get("text", "").strip()
    age = data.get("age", "").strip()

    if not symptoms or not age:
        return jsonify(condition="Invalid", urgency="Invalid", advice="Missing age or symptoms.")

    try:
        prompt = f"The patient is {age} years old and describes the following symptoms: {symptoms}. What is the most likely medical condition, its urgency level (Low, Moderate, High), and advice?"
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        reply = response.choices[0].message.content.strip()

        condition, urgency, advice = "", "", ""

        for line in reply.splitlines():
            lower = line.lower()
            if "condition:" in lower and not condition:
                condition = line.split(":", 1)[1].strip()
            elif "urgency:" in lower and not urgency:
                urgency = line.split(":", 1)[1].strip()
            elif "advice:" in lower and not advice:
                advice = line.split(":", 1)[1].strip()

        if not condition:
            condition = reply.splitlines()[0].strip()

        if not advice:
            match = re.search(r"(it is (recommended|important|advised)[^.]+\.)", reply, re.IGNORECASE)
            if match:
                advice = match.group(1).strip()
        if not advice:
            advice = "Consult a doctor."

        # Rule-based urgency check
        critical_symptoms = ["fever", "headache", "sore throat", "fatigue", "dizziness", "chest pain", "cough", "rash"]
        selected_symptoms = [s.strip().lower() for s in symptoms.split(",")]
        if len([s for s in selected_symptoms if s in critical_symptoms]) >= 6:
            urgency = "High"

        urgency_check = urgency.lower()
        if "high" in urgency_check:
            urgency = "High"
        elif "moderate" in urgency_check or "medium" in urgency_check:
            urgency = "Medium"
        elif "low" in urgency_check:
            urgency = "Low"
        else:
            urgency_text = reply.lower()
            if "high level of urgency" in urgency_text:
                urgency = "High"
            elif "moderate level of urgency" in urgency_text:
                urgency = "Medium"
            elif "low level of urgency" in urgency_text:
                urgency = "Low"
            else:
                match = re.search(r"urgency level.*?(low|moderate|high)", urgency_text, re.IGNORECASE)
                if match:
                    urgency = match.group(1).capitalize()
                else:
                    urgency = "Unknown"

    except Exception as e:
        return jsonify(condition="Error", urgency="Error", advice=str(e))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Save to CSV
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, fullname, age, symptoms, condition, urgency, advice])

    # Save to DB
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO logs (fullname, datetime, age, symptoms, condition, urgency, advice) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (fullname, timestamp, age, symptoms, condition, urgency, advice))
    conn.commit()
    conn.close()

    return jsonify(condition=condition, urgency=urgency, advice=advice)

if __name__ == "__main__":
    app.run(debug=True)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=10000)

