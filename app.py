from flask import Flask, request, jsonify

app = Flask(__name__)

kpi_data = {
    "E-commerce": {
        "kpis": ["Conversion Rate", "Cart Abandonment", "Revenue"],
        "tools": ["Google Analytics", "Looker", "Hotjar"],
        "advice": "Track user journey and optimize product pages weekly."
    },
    "SaaS": {
        "kpis": ["Churn Rate", "Monthly Recurring Revenue", "LTV"],
        "tools": ["ChartMogul", "Mixpanel", "Segment"],
        "advice": "Focus on onboarding funnel and user engagement metrics."
    }
}

@app.route('/')
def home():
    return "KPI Generator API Working"

@app.route('/strategy', methods=['POST'])
def get_strategy():
    data = request.get_json()
    business = data.get("business_type", "")
    result = kpi_data.get(business, {
        "kpis": ["Custom KPI 1", "Custom KPI 2"],
        "tools": ["Tool A", "Tool B"],
        "advice": "Analyze your user funnel and retention weekly."
    })
    return jsonify(result)
