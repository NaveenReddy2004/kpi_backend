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

1. Suggest 4 most important KPIs with 1-line explanations for each.
2. Suggest 4 helpful tools with 1-line explanations for each.
3. Give 1 short strategy advice.

Respond ONLY in this strict JSON format with double quotes (no single quotes):

{{
  "kpis": [
    {{"name": "KPI1", "description": "What it measures and why it's useful"}},
    {{"name": "KPI2", "description": "..."}},
    {{"name": "KPI3", "description": "..."}},
    {{"name": "KPI4", "description": "..."}}
  ],
  "tools": [
    {{"name": "Tool1", "description": "What it does and how it's helpful"}},
    {{"name": "Tool2", "description": "..."}},
    {{"name": "Tool3", "description": "..."}},
    {{"name": "Tool4", "description": "..."}}
  ],
  "advice": "One-line strategic advice"
}}

ONLY return pure JSON. Do not include markdown, explanations, or extra text.
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

if __name__ == '__main__':
    app.run(debug=True)
