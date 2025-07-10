# inxits_chatbot.py

import streamlit as st
import google.generativeai as genai
import random
import fitz  # PyMuPDF
from difflib import SequenceMatcher
from datetime import datetime
from sqlalchemy import create_engine, text

# === Configure Gemini ===
genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
model = genai.GenerativeModel("gemini-2.0-flash-lite")
chat = model.start_chat(history=[])

# === SQLAlchemy Connection ===
driver = 'ODBC Driver 17 for SQL Server'
driver_encoded = driver.replace(" ", "+")
conn_str = (
    f"mssql+pyodbc://{st.secrets['UID']}:{st.secrets['PWD']}@{st.secrets['SERVER_NAME']},{st.secrets['PORT']}/"
    f"{st.secrets['DATABASE']}?driver={driver_encoded}"
)
engine = create_engine(conn_str)

# === Logging Function ===
def log_to_db(role, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO chat_log (timestamp, role, message) VALUES (:ts, :role, :msg)"),
                {"ts": timestamp, "role": role, "msg": message}
            )
    except Exception as e:
        st.warning(f"Logging failed: {e}")

# === PDF Context Extraction ===
def extract_text_from_pdf(file_path):
    try:
        return "\n".join([page.get_text() for page in fitz.open(file_path)])[:5000]
    except Exception as e:
        st.warning(f"⚠️ PDF load failed. Using fallback. Error: {e}")
        return "Inxits.com helps users make better mutual fund decisions with comparison, filtering, and overlap analysis tools."

website_context = extract_text_from_pdf("inxits_brochure.pdf")

# === Set System Prompt ===
chat.send_message(
    f"""
You are a helpful mutual fund assistant chatbot for Inxits.com.
Help Indian investors understand and use Inxits — a DIY platform for mutual fund analysis.

Tools:
- Return Comparison
- Explore Tool
- Portfolio Overlap

Avoid promotional tone. Use examples when useful.

📄 Website context:
{website_context}
"""
)

# === Session State Setup ===
for key in ['chat_history', 'tool_memory']:
    st.session_state.setdefault(key, {} if 'memory' in key else [])

# === Intent Detection ===
def detect_intent(msg):
    result = model.generate_content(
        f"Classify this message as GREETING, HELP_REQUEST, TOOL_QUERY, or OTHER:\nMessage: '{msg}'"
    )
    return result.text.strip().split()[0].upper()

# === Match Predefined Responses ===
CUSTOM_RESPONSES = {
    "what is inxits": "**Inxits** is a commission-free DIY mutual fund platform...\n\n🧰 Tools:\n- Return Comparison\n- Explore\n- Overlap",
    "more about inxits": "Inxits is designed for investors who want full control and clarity...",
    "who made inxits": "Inxits.com was created by data scientists, engineers, and finance pros.",
    "how to compare funds": "Use the Return Comparison Tool to analyze up to 5 funds side-by-side."
}

def match_custom_response(msg):
    msg_lower = msg.lower()
    for key in CUSTOM_RESPONSES:
        if key in msg_lower or SequenceMatcher(None, key, msg_lower).ratio() > 0.7:
            return CUSTOM_RESPONSES[key]
    return None

# === Goal Detection ===
GOAL_KEYWORDS = {
    "retirement": "For retirement, explore long-term equity funds: [Explore Funds](https://portal.inxits.com/Explore/)",
    "tax": "For tax-saving, check ELSS funds: [Explore Funds](https://portal.inxits.com/Explore/)",
    "child": "For child goals, explore balanced or hybrid funds.",
    "sip": "Plan SIPs using the Explore Tool: [Start Here](https://portal.inxits.com/Explore/)"
}

def detect_goal(msg):
    return next((v for k, v in GOAL_KEYWORDS.items() if k in msg.lower()), None)

# === Tool-Specific Responses ===
def choose_variant(key, variants, url):
    last = st.session_state.tool_memory.get(key)
    options = [v for v in variants if v != last] or variants
    choice = random.choice(options)
    st.session_state.tool_memory[key] = choice
    return f"{choice}\n👉 [Try it here]({url})"

def get_tool_response(msg):
    msg = msg.lower()
    if any(k in msg for k in ["compare", "return", "sharpe", "performance"]):
        return choose_variant("compare", [
            "🧮 Compare returns, volatility, Sharpe ratios, and benchmarks across 5 mutual funds.",
            "📈 Use Return Comparison Tool for performance and risk metrics."
        ], "https://portal.inxits.com/ReturnComparison/")
    elif any(k in msg for k in ["explore", "filter", "rank"]):
        return choose_variant("explore", [
            "🔍 Explore Tool lets you filter by category, rating, AMC, and timeframe.",
            "📊 Discover top-rated funds for your risk appetite."
        ], "https://portal.inxits.com/Explore/")
    elif any(k in msg for k in ["overlap", "diversify"]):
        return choose_variant("overlap", [
            "📊 Overlap Tool helps detect common holdings and avoid duplication.",
            "🔄 Reduce redundancy across your mutual funds using Portfolio Overlap."
        ], "https://portal.inxits.com/PortfolioOverlap/")
    return None

# === UI ===
st.title("💬 Inxits Virtual Assistant")

if not st.session_state.chat_history:
    onboarding = "👋 Welcome to the Inxits Assistant!\n\nAsk things like:\n- What is Inxits?\n- How to compare funds?\n- What does overlap tool do?"
    st.chat_message("assistant").markdown(onboarding)

for msg in st.session_state.chat_history:
    st.chat_message(msg["role"]).markdown(msg["content"])

user_input = st.chat_input("Ask anything about funds, SIPs, or Inxits tools...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.chat_message("user").markdown(user_input)
    log_to_db("User", user_input)

    response = (
        match_custom_response(user_input)
        or detect_goal(user_input)
        or get_tool_response(user_input)
    )

    if not response:
        intent = detect_intent(user_input)

        if intent == "GREETING":
            response = random.choice([
                "👋 Hello! How can I help you today?",
                "Hi! Ask me anything about mutual funds or Inxits tools.",
                "Welcome! Let's explore mutual funds together."
            ])
        elif intent == "HELP_REQUEST":
            response = "Try asking:\n- What is Inxits?\n- How to compare mutual funds?\n- What does the Overlap Tool do?"
        elif "inxits" in user_input.lower():
            result = chat.send_message(f"{website_context}\nUser: {user_input}")
            response = result.text.strip()
        elif any(k in user_input.lower() for k in ["mutual fund", "sip", "returns", "investment"]):
            prompt = f"""
You are a friendly mutual fund assistant for Inxits.
Avoid financial jargon or suggesting users contact a financial advisor.
Only refer to Inxits.com tools.

User Question: {user_input}
"""
            response = model.generate_content(prompt).text.strip()
        else:
            response = "❌ I can only answer questions about mutual funds or Inxits tools."

    st.chat_message("assistant").markdown(response)
    st.session_state.chat_history.append({"role": "assistant", "content": response})
    log_to_db("Assistant", response)
