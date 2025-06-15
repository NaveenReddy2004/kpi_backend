import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all origins

# Get Groq API Key from environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@app.route('/')
def home():
    return "Groq KPI Recommender API is Live!"

@app.route('/strategy', methods=['POST'])
def strategy():
    data = request.get_json()
    biz = data.get("business_type", "")

    if not biz:
        return jsonify({"error": "Missing 'business_type' in request"}), 400

    # Prompt engineering for strict JSON output
    system_prompt = "You are a business strategy advisor. Always respond with valid JSON, no markdown, no explanation."
user_prompt = f"""
Give exactly 4 KPIs, 4 tools, and 1 strategy advice for a business in the {biz} domain. Respond in this format:
{{
  "kpis": ["KPI1", "KPI2", "KPI3", "KPI4"],
  "tools": ["Tool1", "Tool2", "Tool3", "Tool4"],
  "advice": "One short actionable advice"
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
        "temperature": 0.7
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        reply_text = response.json()["choices"][0]["message"]["content"]
        print("Groq Reply:\n", reply_text)

        # Parse the JSON string in the reply
        result = json.loads(reply_text)
        return jsonify(result)

    except json.JSONDecodeError as je:
        print("JSON parsing failed:", je)
        return jsonify({"error": "Invalid JSON from Groq response"}), 500

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Groq failed to generate a valid response"}), 500

# Run app (needed for local testing)
if __name__ == "__main__":
    app.run(debug=True)


