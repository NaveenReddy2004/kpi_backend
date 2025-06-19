import os
import re
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document

app = Flask(__name__)

CORS(app, origins="*")  # ❗ For production, replace with actual domain

# Load API key securely
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@app.route('/')
def home():
    return "Llama3-70b Business Chatbot is Live"

# /strategy route for quick KPIs, tools, and advice
@app.route('/strategy', methods=['POST'])
def strategy():
    try:
        data = request.get_json()
        biz = data.get("business_type", "")

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
                {"role": "system", "content": "You are a business strategy advisor."},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.6
        }

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        raw_reply = response.json()["choices"][0]["message"]["content"]

        match = re.search(r"\{.*\}", raw_reply, re.DOTALL)
        if not match:
            return jsonify({"error": "Invalid JSON format from Groq"}), 500

        return jsonify(json.loads(match.group()))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# /chat route for answering user questions about tools, KPIs, etc.
@app.route('/chat', methods=['POST'])
def chat():
    try:
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

        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": "You are a helpful business assistant."},
                {"role": "user", "content": chat_prompt}
            ],
            "temperature": 0.7
        }

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        content = response.json()["choices"][0]["message"]["content"]
        return jsonify({"response": content})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Allowed file types for business description upload
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file):
    filename = secure_filename(file.filename)
    extension = filename.rsplit('.', 1)[1].lower()

    if extension == 'txt':
        return file.read().decode('utf-8', errors='ignore')
    elif extension == 'pdf':
        reader = PdfReader(file)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif extension == 'docx':
        doc = Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    else:
        return ""


@app.route("/ai-business-plan", methods=["POST"])
def generate_business_plan():
    try:
        idea = request.form.get("idea", "").strip()

        file_text = ""
        if "file" in request.files:
            file = request.files["file"]
            if file and allowed_file(file.filename):
                file_text = extract_text_from_file(file)

        if not idea and not file_text:
            return jsonify({"error": "Please provide either a business idea or upload a document."}), 400

        # Combine idea and file text
        combined_idea = f"{idea}\n\n{file_text}".strip()

        prompt = f"""
You are an AI Business Advisor.

A user has described their idea: "{combined_idea}"

Please identify the domain, list exactly 4 KPIs and 4 tools with short explanations, and 5 steps to launch the business using KPIs and tools generated. Return only in this exact JSON format:

{{
  "domain": "...",
  "kpis": [{{"name": "...", "description": "..." }}, ...],
  "tools": [{{"name": "...", "description": "..." }}, ...],
  "steps": ["Step 1...", "Step 2...", ...]
}}
"""

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": "You are a helpful business advisor."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5
        }

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        ai_content = result["choices"][0]["message"]["content"]

        match = re.search(r"\{.*\}", ai_content, re.DOTALL)
        if not match:
            return jsonify({"error": "AI response does not contain valid JSON"}), 500

        return jsonify(json.loads(match.group()))

    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response as JSON"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True)
