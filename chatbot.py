# inxits_chatbot.py

import streamlit as st
import google.generativeai as genai
import random
import fitz  # PyMuPDF
from difflib import SequenceMatcher
from datetime import datetime
from sqlalchemy import create_engine, text

# === Gemini API Config ===
genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
model = genai.GenerativeModel("Gemma 3")
chat = model.start_chat(history=[])

# === SQL Server Connection using SQLAlchemy + pyodbc ===
server_name = st.secrets['SERVER_NAME']
port = st.secrets['PORT']
user_name = st.secrets['UID']
database_name = st.secrets['DATABASE']
password = st.secrets['PWD']
driver = 'ODBC Driver 17 for SQL Server'

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
        with engine.begin() as conn:
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
    "🧠 Tone: Clear, jargon-free, informative. Avoid promotional or vague statements. Focus on features, tools, and user value.\n\n"
    f"📄 Below is the latest official website/brochure context for Inxits:\n{website_context}\n\n"
    "📌 When a user asks general questions like 'What is Inxits?', give a concise summary in 200 to 300 words.\n"
    "📌 You may also refer to specific tools, examples, or use cases described in the context.\n\n"
    "If the user asks about something else (like returns, overlap, SIPs), respond appropriately using relevant parts of the context and tools offered by Inxits.\n"
    "You can use the web but don't mention third-party websites, companies, or share external links or brand names in your answers.\n"
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
    if any(kw in msg for kw in ["compare", "return", "performance", "sharpe", "volatility"]):
        return choose_variant("compare", [
            """🧮 Looking to understand fund performance?
Our **Return Comparison Tool** lets you analyze up to **5 mutual funds** side-by-side:\n
- ✅ Returns (1Y, 3Y, 5Y)
- ⚖️ Sharpe & Sortino ratios
- 🔄 Rolling & benchmark returns""",
            """🧮 Curious about returns or risk?
Use our tool to compare mutual funds on:\n
- 📈 Historical returns
- 📉 Volatility
- 🆚 Fund vs Benchmark"""
        ], "https://portal.inxits.com/ReturnComparison/")

    elif any(kw in msg for kw in ["explore", "filter", "rank"]):
        return choose_variant("explore", [
            """🔍 Use the **Explore Tool** to:
- 🧠 Filter by category, rating, AMC, or return
- 📊 Discover best funds for your risk type""",
            """🔍 Want top-rated funds?
Use Explore Tool to filter by type, rating, risk, or returns across timeframes."""
        ], "https://portal.inxits.com/Explore/")

    elif any(kw in msg for kw in ["overlap", "diversify"]):
        return choose_variant("overlap", [
            """📊 **Portfolio Overlap Tool** helps:
- 🔄 Detect common holdings across funds
- 🧱 Improve diversification and reduce duplication""",
            """📊 Avoid redundant investments using Overlap Tool:
- Spot holdings duplication across funds easily"""
        ], "https://portal.inxits.com/PortfolioOverlap/")

    elif any(kw in msg for kw in ["home", "homepage", "start"]):
        return choose_variant("home", [
            """🌐 Visit [Inxits.com](https://inxits.com) to explore all tools for fund comparison, screening, and overlap analysis."""
        ], "https://inxits.com/")
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
st.title("💬 Inxits Virtual Assistant")

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
    # reply = (
    #     match_custom_response(user_input)
    #     or detect_goal(user_input)
    #     or get_tool_response(user_input)
    # )
    reply = None

    # Step 1: Check for exact custom matches
    custom = match_custom_response(user_input)
    if custom:
        reply = custom

    # Step 2: Check for goal-based suggestions
    elif detect_goal(user_input):
        reply = detect_goal(user_input)

    # Step 3: Check for tool-related responses
    elif get_tool_response(user_input):
        reply = get_tool_response(user_input)


    if not reply:
        def is_mutual_fund_related(msg):
            keywords = ["mutual fund", "mf", "sip", "etf", "nav", "investment", "returns", "fund", "amc"]
            return any(kw in msg.lower() for kw in keywords)

        def is_inxits_query(msg):
            return any(word in msg.lower() for word in ["inxits", "tools", "explore", "compare", "overlap", "fund analysis"])
        
        intent = detect_intent(user_input)

        if is_inxits_query(user_input):
            result = chat.send_message(f"{website_context}\nUser: {user_input}")
            reply = result.text.strip()
        
        elif intent == "GREETING":
            reply = random.choice([
            "👋 Hello! How can I help you with mutual funds or Inxits tools today?",
            "Hi there! Ask me about fund comparison, SIPs, or Inxits features.",
            "Welcome! Feel free to ask anything about Inxits or mutual funds."
        ])

        elif intent == "HELP_REQUEST":
            reply = "Sure! You can ask things like:\n- What is Inxits?\n- How to compare mutual funds?\n- What does the Overlap Tool do?"

        elif intent == "TOOL_QUERY" or is_inxits_query(user_input):
            result = chat.send_message(f"{website_context}\nUser: {user_input}")
            reply = result.text.strip()

        elif is_mutual_fund_related(user_input):
            prompt = f"""
You are a helpful assistant for Indian mutual fund investors.
Answer clearly without financial jargon or vague advice.
Avoid suggesting to consult a financial advisor unless truly required.

✅ You may refer to web knowledge for accurate answers,
but do not show or mention any third-party site, brand, or URL in your response.
Only mention inxits.com or its tools.

Question: {user_input}
"""
            result = model.generate_content(prompt)
            reply = result.text.strip()

            if any(phrase in reply.lower() for phrase in ["consult", "advisor", "not financial advice"]):
                reply += "\n\n📞 For more help, contact **abcxyz**."

        else:
            reply = "❌ I can only answer questions related to mutual funds or Inxits tools. Try asking about SIP, fund comparison, or Inxits features."

    st.chat_message("assistant").markdown(reply)
    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    log_to_db("Assistant", reply)
