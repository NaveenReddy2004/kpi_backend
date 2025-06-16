import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@app.route('/')
def home():
    return "Groq KPI Recommender API is Live"

@app.route('/strategy', methods=['POST'])
def strategy():
    try:
        data = request.get_json()
        biz = data.get("business_type", "")

        system_prompt = "You are a business strategy advisor."
        user_prompt = f"""
You are a business strategy advisor. For a business in the {biz} domain:

Provide exactly 4 KPIs and 4 tools with one-line descriptions, and one piece of strategic advice.

Respond ONLY in **valid JSON format** like this, without any explanation or markdown:

{{
  "kpis": [
    {{ "name": "KPI1", "description": "..." }},
    {{ "name": "KPI2", "description": "..." }},
    {{ "name": "KPI3", "description": "..." }},
    {{ "name": "KPI4", "description": "..." }}
  ],
  "tools": [
    {{ "name": "Tool1", "description": "..." }},
    {{ "name": "Tool2", "description": "..." }},
    {{ "name": "Tool3", "description": "..." }},
    {{ "name": "Tool4", "description": "..." }}
  ],
  "advice": "One-line strategy advice"
}}

IMPORTANT:
- Use only double quotes ("), not single quotes (').
- Do NOT include any intro or summary text — only pure JSON.
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

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        raw_reply = response.json()["choices"][0]["message"]["content"]

        # Extract only JSON part from raw output
        start = raw_reply.find('{')
        end = raw_reply.rfind('}') + 1
        json_string = raw_reply[start:end]

        try:
            parsed_json = json.loads(json_string)
            return jsonify(parsed_json)
        except json.JSONDecodeError as e:
            print("JSON parsing error:", e)
            print("RAW Groq reply:", raw_reply)
            return jsonify({"error": "Invalid JSON format from Groq"}), 500

    except Exception as e:
        print("Server error:", e)
        return jsonify({"error": "Server error occurred"}), 500
        
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_query = data.get("query", "")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that answers business-related questions about KPIs, business tools, and strategic advice in simple terms."},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        reply = response.json()["choices"][0]["message"]["content"]
        return jsonify({"response": reply})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to generate chat response"}), 500


if __name__ == '__main__':
    app.run(debug=True)
