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
    return "Claude 3 Sonnet Business Chatbot is Live "

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
            "model": "anthropic/claude-3-sonnet-20240229",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.6
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
    chat_prompt = f"""
You are an AI assistant helping users understand business tools and KPIs. 
When the user asks about a KPI, tool, or concept like "{user_query}", respond in a way that is:

1. Easy to understand — avoid technical jargon.
2. Friendly and clear — like explaining to a beginner.
3. In 3 to 4 short paragraphs at most.
4. Highlight **3 important points** about the tool/KPI using bullet points.
5. End with a helpful or encouraging note if appropriate.

Avoid repeating the user's question. Keep tone informative and supportive.

Now respond to the following user query:

{user_query}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload={
       "model": "llama3-70b-8192",
       "messages": [
                {"role": "system", "content": "You are a helpful business assistant."},
                {"role": "user", "content": chat_prompt}
       ],
        "temperature": 0.7
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        content = response.json()["choices"][0]["message"]["content"]
        return jsonify({"response": content})
    except Exception as e:
        print("Chat error:", e)
        return jsonify({"error": "Unable to generate response"}), 500

if __name__ == '__main__':
    app.run(debug=True)
