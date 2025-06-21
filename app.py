import os
import re
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document
from supabase import create_client, Client
from datetime import datetime

app = Flask(__name__)
CORS(app, origins="*")  # For development; restrict in production

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

def ask_llama(prompt, temp=0.5):
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
        return jsonify({"error": "AI response does not contain valid JSON"}), 500

    parsed = json.loads(match.group())

    # Optional: Get user email (if you're sending it from frontend)
    user_email = request.form.get("user_email", "guest@example.com")

    # Truncate long ideas if needed
    idea_text = combined_idea[:2000]

    # Insert into Supabase
    plan_insert = supabase.table("business_plans").insert({
        "user_email": user_email,
        "idea": idea_text,
        "domain": parsed["domain"]
    }).execute()

    plan_id = plan_insert.data[0]["id"]

    # Store KPIs
    for kpi in parsed.get("kpis", []):
        supabase.table("kpis").insert({
            "business_plan_id": plan_id,
            "name": kpi["name"],
            "description": kpi["description"]
        }).execute()

    # Store Tools
    for tool in parsed.get("tools", []):
        supabase.table("tools").insert({
            "business_plan_id": plan_id,
            "name": tool["name"],
            "description": tool["description"]
        }).execute()

    return jsonify(parsed)


@app.route('/')
def home():
    return "LLaMA3 Business Chatbot API is live."

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

        # Make Groq API request
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        
        print("Groq API response code:", response.status_code)
        print("Groq API raw response:", response.text)

        if response.status_code != 200:
            return jsonify({"error": f"Groq API Error: {response.status_code}", "details": response.text}), 500

        raw_reply = response.json()["choices"][0]["message"]["content"]

        # Extract JSON using regex
        import re
        match = re.search(r"\{.*\}", raw_reply, re.DOTALL)
        if not match:
            return jsonify({"error": "Invalid JSON format from Groq"}), 500

        return jsonify(json.loads(match.group()))

    except Exception as e:
        import traceback
        print("Strategy Endpoint Exception:", str(e))
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        query = request.json.get("query", "")

        prompt = f"""
You are a friendly AI advisor. When the user asks about KPIs, tools, or concepts like "{query}":

- Avoid jargon
- Write in 3-4 short paragraphs
- List 3 key points with bullet points
- End on a helpful note

Now answer:
{query}
"""
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": "You are a helpful business assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response_text = res.json()["choices"][0]["message"]["content"]
        return jsonify({"response": response_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ai-business-plan', methods=['POST'])
def generate_plan():
    try:
        email = request.form.get("email", "").strip()
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
        ai_output = ask_llama(prompt)
        if not ai_output:
            return jsonify({"error": "Invalid JSON format from AI"}), 500

        # Save to Supabase
        supabase.table("business_plans").insert({
            "user_email": email or "anonymous",
            "idea": combined_input[:5000],
            "result": json.dumps(ai_output),
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        return jsonify(ai_output)

    # After receiving ai_output from ask_llama(prompt)
    if isinstance(ai_output, str):
        match = re.search(r"\{.*\}", ai_output, re.DOTALL)
        if not match:
            print("❌ Invalid JSON returned by Groq:", ai_output)
            return jsonify({"error": "AI returned invalid format."}), 500
        try:
            ai_output = json.loads(match.group())
        except json.JSONDecodeError:
            print("❌ JSON decode error")
            return jsonify({"error": "Could not parse AI response"}), 500

@app.route("/history", methods=["POST"])
def history():
    try:
        email = request.json.get("email")
        if not email:
            return jsonify({"error": "Email is required"}), 400

        response = supabase.table("business_plans") \
            .select("*") \
            .eq("user_email", email) \
            .order("created_at", desc=True) \
            .limit(10) \
            .execute()

        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
