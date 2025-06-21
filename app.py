import os
import re
import json
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document
from supabase import create_client, Client
import requests

app = Flask(__name__)
CORS(app, origins="*")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

def ask_llama(prompt, temp=0.5,text=""):
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
        "temperature": temp
    }

    result = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
    raw = result.json()["choices"][0]["message"]["content"]

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None  # Invalid JSON format

    parsed = json.loads(match.group())

    # Debug print
    print("AI Output:", json.dumps(parsed, indent=2))

    # Get user email from form
    user_email = request.form.get("email", "guest@example.com")
    combined_idea = request.form.get("idea", "").strip()
    file_text = ""
    if "file" in request.files:
        file = request.files["file"]
        if file and allowed_file(file.filename):
            file_text = extract_text_from_file(file)

    combined_input = f"{combined_idea}\n\n{file_text}".strip()

    # Save business plan
    plan_insert = supabase.table("business_plans").insert({
        "user_email": user_email,
        "idea": combined_input[:5000],
        "domain": parsed.get("domain", "Unknown"),
        "created_at": datetime.utcnow().isoformat()
    }).execute()

    plan_id = plan_insert.data[0]["id"]

    # Store KPIs
    for kpi in parsed.get("kpis", []):
        if isinstance(kpi, dict):
            supabase.table("kpis").insert({
                "business_plan_id": plan_id,
                "name": kpi.get("name", "Unnamed KPI"),
                "description": kpi.get("description", "No description available")
            }).execute()
        else:
            supabase.table("kpis").insert({
                "business_plan_id": plan_id,
                "name": str(kpi),
                "description": "No description available"
            }).execute()

    # Store Tools
    for tool in parsed.get("tools", []):
        if isinstance(tool, dict):
            supabase.table("tools").insert({
                "business_plan_id": plan_id,
                "name": tool.get("name", "Unnamed Tool"),
                "description": tool.get("description", "No description available")
            }).execute()
        else:
            supabase.table("tools").insert({
                "business_plan_id": plan_id,
                "name": str(tool),
                "description": "No description available"
            }).execute()

    return parsed

@app.route('/')
def home():
    return "Llama3-70b Business Chatbot is Live"

@app.route('/ai-business-plan', methods=['POST'])
def generate_plan():
    try:
        email = request.form.get("email", "guest@example.com").strip()
        idea = request.form.get("idea", "").strip()
        file_text = ""

        if "file" in request.files:
            file = request.files["file"]
            if file and allowed_file(file.filename):
                file_text = extract_text_from_file(file)

        if not idea and not file_text:
            return jsonify({"error": "Provide a business idea or upload a document"}), 400

        combined_input = f"{idea}\n\n{file_text}".strip()

        prompt = f"""
You are an AI Business Advisor.
User submitted: "{combined_input}"
Give:
- Domain
- 4 KPIs
- 4 Tools (briefly explained)
- 5 Launch Steps
Output valid JSON like:
{{
  "domain": "...",
  "kpis": [...],
  "tools": [...],
  "steps": [...]
}}
"""

        ai_output = ask_llama(prompt, email, combined_input)
        if not ai_output:
            return jsonify({"error": "Invalid JSON format from AI"}), 500

        return jsonify(ai_output)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/strategy', methods=['POST'])
def strategy():
    try:
        data = request.get_json()
        biz = data.get("business_type", "")

        user_prompt = f"""
You are a business strategy advisor. For a business in the {biz} domain:
Provide exactly 4 KPIs and 4 tools with one-line descriptions, and one piece of strategic advice.
Respond ONLY in **valid JSON format** like this:
{{
  "kpis": [{{"name": "...", "description": "..."}}, ...],
  "tools": [{{"name": "...", "description": "..."}}, ...],
  "advice": "..."
}}
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

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_query = data.get("query", "")

        chat_prompt = f"""
You are an AI assistant helping users understand business tools and KPIs.
User asked: {user_query}
Reply in 3-4 short paragraphs and 3 bullet points. Friendly, clear, and helpful.
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

if __name__ == '__main__':
    app.run(debug=True)
