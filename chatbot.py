# inxits_chatbot.py

import streamlit as st
import google.generativeai as genai
import random
import fitz  # PyMuPDF
from difflib import SequenceMatcher
from datetime import datetime
from sqlalchemy import create_engine, text

# === Gemini API Config ===
genai.configure(api_key="AIzaSyD8lVp9I566j6M6UpnlP4LuL79M_zk3hkU")
model = genai.GenerativeModel("gemini-2.5-flash")
chat = model.start_chat(history=[])

# === SQL Server Connection using SQLAlchemy + pyodbc ===
server_name = '54.145.168.143'
port = '1433'
user_name = 'inxits_nav_user'
database_name = 'inxits_Nav'
password = 'InxitsSch01105'
driver = 'ODBC Driver 17 for SQL Server'  # Make sure this driver is installed

driver_encoded = driver.replace(" ", "+")
conn_str = (
    f"mssql+pyodbc://{user_name}:{password}@{server_name},{port}/{database_name}"
    f"?driver={driver_encoded}"
)

engine = create_engine(conn_str)
conn = engine.connect()

# === Logging Function ===
def log_to_db(role, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            text("INSERT INTO chat_log (timestamp, role, message) VALUES (:ts, :role, :msg)"),
            {"ts": timestamp, "role": role, "msg": message}
        )
    except Exception as e:
        st.warning(f"Logging failed: {e}")

# === Load PDF Context ===
def extract_text_from_pdf_file(file_path):
    try:
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])[:5000]
    except Exception as e:
        st.warning(f"⚠️ PDF load failed. Using fallback. Error: {e}")
        return "Inxits.com helps users make better mutual fund decisions with comparison, filtering, and overlap analysis tools."

website_context = extract_text_from_pdf_file("inxits_brochure.pdf")

# === System Prompt ===
system_intro = (
    "You are a helpful, friendly, and concise mutual fund assistant chatbot for Inxits.com.\n"
    "Your job is to help Indian retail investors understand and use Inxits — a commission-free, DIY platform for mutual fund analysis.\n"
    "Inxits provides tools like return comparison, fund screening, and portfolio overlap detection to help users invest smarter.\n\n"
    f"📄 Brochure Context:\n{website_context}\n\n"
    "📌 If user asks general questions like 'What is Inxits?', give a short answer.\n"
    "📌 If user asks for detail — e.g., 'Explain Inxits in detail' — use the context above.\n"
)
chat.send_message(system_intro)

# === Session State Setup ===
for key in ['chat_history', 'tool_memory', 'last_intent', 'last_topic']:
    st.session_state.setdefault(key, {} if 'memory' in key else None if 'intent' in key else [])

# === Custom Responses & Tools ===
CUSTOM_RESPONSES = {
    "what is inxits": """**Inxits** is a commission-free DIY mutual fund platform...

🧰 Core Tools:
- **Return Comparison**
- **Explore Tool**
- **Portfolio Overlap**
""",
    "more about inxits": """Inxits offers a modern way to evaluate mutual funds...

✨ All tools are DIY, ad-free, and built for people who want control and clarity in investing.""",
    "who made inxits": "Inxits.com is built by data scientists, engineers, and finance pros.",
    "how to compare funds": "Use the 🧮 Return Comparison Tool: https://portal.inxits.com/ReturnComparison/"
}

def choose_variant(key, variants, url):
    last = st.session_state.tool_memory.get(key)
    choice = random.choice([v for v in variants if v != last] or variants)
    st.session_state.tool_memory[key] = choice
    return f"{choice}\n👉 [Try it here]({url})"

def get_tool_response(message):
    msg = message.lower()
    if any(kw in msg for kw in ["compare", "return", "performance", "sharpe"]):
        return choose_variant("compare", [
            "🧮 Compare up to 5 mutual funds:\n- ✅ Returns\n- ⚖️ Sharpe\n- 🔄 Rolling returns",
            "🧮 Compare mutual funds by:\n- 📈 Returns\n- 📉 Volatility\n- 🆚 Benchmark"
        ], "https://portal.inxits.com/ReturnComparison/")
    elif any(kw in msg for kw in ["explore", "filter"]):
        return choose_variant("explore", [
            "🔍 Explore top funds by category, rating, AMC, etc.",
            "🔍 Filter by return, risk, and fund house to find best funds."
        ], "https://portal.inxits.com/Explore/")
    elif "overlap" in msg:
        return choose_variant("overlap", [
            "📊 Use the Portfolio Overlap Tool to find duplicate holdings.",
            "📊 Detect overlap across your funds to reduce risk."
        ], "https://portal.inxits.com/PortfolioOverlap/")
    elif "home" in msg:
        return "🌐 Visit [Inxits.com](https://inxits.com)"
    return ""

GOAL_KEYWORDS = {
    "retirement": "For retirement planning... [Explore Funds](https://portal.inxits.com/Explore/)",
    "tax": "For tax saving, explore **ELSS Funds**: [Explore Funds](https://portal.inxits.com/Explore/)",
    "child": "For child education, consider balanced funds: [Explore Funds](https://portal.inxits.com/Explore/)",
    "sip": "Use the Explore Tool for SIP planning: [Start SIP](https://portal.inxits.com/Explore/)"
}

def detect_goal(msg):
    return next((response for key, response in GOAL_KEYWORDS.items() if key in msg.lower()), None)

def detect_intent(message):
    response = model.generate_content(f"Classify: '{message}'\nGREETING, HELP_REQUEST, TOOL_QUERY, OTHER?")
    return response.text.strip().upper()

def is_meaningful_input(msg):
    response = model.generate_content(f"Respond YES/NO. Is this meaningful?\n'{msg}'")
    return response.text.strip().upper() == "YES"

def match_custom_response(message):
    msg = message.lower()
    for key in CUSTOM_RESPONSES:
        if key in msg or SequenceMatcher(None, key, msg).ratio() > 0.7:
            return CUSTOM_RESPONSES[key]
    return None

# === Streamlit Chat UI ===
st.title("💬 Inxits Mutual Fund Assistant")

if not st.session_state.chat_history:
    onboarding = (
        "👋 Welcome to the Inxits Assistant!\n\n"
        "Ask things like:\n"
        "- What is Inxits?\n"
        "- How to compare funds?\n"
        "- What does overlap tool do?"
    )
    st.chat_message("assistant").markdown(onboarding)

for msg in st.session_state.chat_history:
    st.chat_message(msg["role"]).markdown(msg["content"])

user_input = st.chat_input("Ask anything about funds, goals, or tools...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.chat_message("user").markdown(user_input)
    log_to_db("User", user_input)

    lower_input = user_input.lower()
    reply = (
        match_custom_response(user_input)
        or detect_goal(user_input)
        or get_tool_response(user_input)
    )

    if not reply:
        if any(x in lower_input for x in ["tools", "features"]):
            reply = (
                "🧰 **Inxits Tools**\n\n"
                "- 🧮 Return Comparison: Side-by-side fund analysis\n"
                "- 🔍 Explore Tool: Filter by category, rating\n"
                "- 📊 Overlap Tool: Find duplicate holdings"
            )
        elif lower_input in ["continue", "tell me more"]:
            reply = "Let me know your specific query or try the Explore Tool!"
        else:
            intent = detect_intent(user_input)
            if intent == "GREETING":
                reply = "👋 Hey! Ask me about fund tools, returns, or planning."
            elif intent == "HELP_REQUEST":
                reply = "💡 You can ask about tool usage, compare funds, or SIP planning."
            elif not is_meaningful_input(user_input):
                result = chat.send_message(f"Context: {website_context}\nUser: {user_input}")
                reply = result.text.strip() or "🤔 Sorry, I didn’t get that. Can you rephrase?"
            else:
                result = chat.send_message(f"{website_context}\nUser: {user_input}")
                reply = result.text.strip()

    st.chat_message("assistant").markdown(reply)
    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    log_to_db("Assistant", reply)
