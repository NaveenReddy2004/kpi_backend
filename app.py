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
    system_prompt = "You are a business strategy advisor."
    user_prompt = f"""
You are a business strategy advisor. For a business in the {biz} domain:

1. Suggest 3 most important KPIs with 1-line explanations for each.
2. Suggest 3 helpful tools with 1-line explanations for each.
3. Give 1 short strategy advice.

Respond ONLY in this strict JSON format:
{{
  "kpis": [
    {{"name": "KPI1", "description": "What it measures and why it's useful"}},
    {{"name": "KPI2", "description": "..." }},
    ...
  ],
  "tools": [
    {{"name": "Tool1", "description": "What it does and how it's helpful"}},
    ...
  ],
  "advice": "One-line strategic advice"
}}
Return ONLY valid JSON.
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


