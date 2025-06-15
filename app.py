import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS  

app = Flask(__name__)
CORS(app) 

# Load your GROQ API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@app.route('/')
def home():
    return "Groq KPI Recommender API is Live"

import json

@app.route('/strategy', methods=['POST'])
def strategy():
    data = request.get_json()
    biz = data.get("business_type", "")

    system_prompt = "You are a business strategy advisor."
    user_prompt = f"""
Suggest the top 3 KPIs, 3 tools, and 1 strategy tip for a business in the "{biz}" industry.

Respond ONLY in valid JSON format with double quotes and no extra text. Example:
{{
  "kpis": ["KPI1", "KPI2", "KPI3"],
  "tools": ["Tool1", "Tool2", "Tool3"],
  "advice": "Your single-line advice"
}}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        content = response.json()["choices"][0]["message"]["content"]
        print("Raw Groq Response:", content)

        parsed = json.loads(content)  # only works with valid JSON
        return jsonify(parsed)

    except json.JSONDecodeError as jde:
        print("JSON Decode Error:", jde)
        return jsonify({"error": "Invalid JSON from Groq"}), 500

    except Exception as e:
        print("General Error:", e)
        return jsonify({"error": "Groq failed to generate a valid response"}), 500



if __name__ == "__main__":
    app.run(debug=True)

