import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@app.route('/')
def home():
    return "Groq KPI Recommender API is Live"

@app.route('/strategy', methods=['POST'])
def strategy():
    data = request.get_json()
    biz = data.get("business_type", "")

    system_prompt = "You are a business strategy advisor."
    user_prompt = f"""
Suggest the top 3 KPIs, 3 tools, and 1 strategy tip for a business in the {biz} industry.
Respond ONLY in the following JSON format:
{{
  "kpis": ["KPI1", "KPI2", "KPI3"],
  "tools": ["Tool1", "Tool2", "Tool3"],
  "advice": "Some advice here"
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
        reply = response.json()["choices"][0]["message"]["content"]
        return jsonify(eval(reply))  # Only do this if you're confident the response is safe
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Groq failed to generate a valid response"}), 500
