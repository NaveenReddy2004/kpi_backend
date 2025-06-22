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
from auth_utils import get_user_from_request

app = Flask(__name__)
CORS(app, origins="*")

@app.route("/secure-data", methods=["GET"])
def secure_data():
    user = get_user_from_request(request)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({"message": f"Hello, {user['email']}!"})


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

def ask_llama(prompt, email, combined_idea, temp=0.5):
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

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        if "choices" not in result or not result["choices"]:
            print("❌ Groq API Error Response:", result)
            return None

        raw = result["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None

        parsed = json.loads(match.group())

        # Supabase insertions (optional, if you’re calling from generate_plan)
        plan_insert = supabase.table("business_plans").insert({
            "user_email": email or "guest@example.com",
            "idea": combined_idea[:5000],
            "domain": parsed.get("domain", "Unknown"),
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        plan_id = plan_insert.data[0]["id"]

        for kpi in parsed.get("kpis", []):
            if isinstance(kpi, dict):
                name = kpi.get("name", "Unnamed KPI")
                desc = kpi.get("description", "No description available")
            else:  # if it's just a string
                name = kpi
                desc = "No description available"

            supabase.table("kpis").insert({
                    "business_plan_id": plan_id,
                    "name": name,
                    "description": desc
                }).execute()


        for tool in parsed.get("tools", []):
            if isinstance(tool, dict):
                name = tool.get("name", "Unnamed Tool")
                desc = tool.get("description", "No description available")
            else:
                name = tool
                desc = "No description available"

            supabase.table("tools").insert({
                "business_plan_id": plan_id,
                "name": name,
                "description": desc
            }).execute()

        return parsed

    except Exception as e:
        print("❌ Groq API Error:", str(e))
        return None

@app.route('/')
def home():
    return "Llama3-70b Business Chatbot is Live"
    

@app.route('/ai-business-plan', methods=['POST'])
def generate_plan():
    try:
        user = get_user_from_request(request)
        email = user["email"] if user else "guest@example.com"
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
You are an expert AI Business Advisor.

The user provided this idea or description of a business:
\"\"\"{combined_input}\"\"\"

Based on this, analyze the business and return a detailed response in the following **strict JSON format**:

{{
  "domain": "A one-word or short phrase categorizing the business domain (e.g., FinTech, EdTech, E-commerce, etc.)",
  "kpis": [
    {{ "name": "KPI Name", "description": "What it measures and why it's important" }},
    {{ "name": "KPI Name", "description": "..." }},
    {{ "name": "KPI Name", "description": "..." }},
    {{ "name": "KPI Name", "description": "..." }}
  ],
  "tools": [
    {{ "name": "Tool Name", "description": "How the tool supports the business" }},
    {{ "name": "Tool Name", "description": "..." }},
    {{ "name": "Tool Name", "description": "..." }},
    {{ "name": "Tool Name", "description": "..." }}
  ],
  "steps": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ...",
    "Step 4: ...",
    "Step 5: ..."
  ]
}}

Rules:
- Use only double quotes (") for JSON.
- Each KPI and Tool must include a `name` and a short `description`.
- Do NOT include explanations outside the JSON.
- Avoid markdown or extra commentary.
- Keep the response compact but informative.
"""

        ai_output = ask_llama(prompt, email, combined_input)
        if not ai_output:
            return jsonify({"error": "Failed to get valid response from AI"}), 500

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
