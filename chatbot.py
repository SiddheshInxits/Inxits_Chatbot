# inxits_chatbot.py

import streamlit as st
import google.generativeai as genai
import random
import fitz  # PyMuPDF
import pyodbc
from difflib import SequenceMatcher
from datetime import datetime

# === Gemini API Config ===
genai.configure(api_key="AIzaSyD8lVp9I566j6M6UpnlP4LuL79M_zk3hkU")
model = genai.GenerativeModel("gemini-2.5-flash")
chat = model.start_chat(history=[])

# === SQL Server DB Config ===
conn = pyodbc.connect(
    'DRIVER={SQL Server};SERVER=54.145.168.143,1433;DATABASE=inxits_Nav;UID=inxits_nav_user;PWD=InxitsSch01105'
)
cursor = conn.cursor()

# === Log Function ===
def log_to_db(role, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO chat_log (timestamp, role, message) VALUES (?, ?, ?)",
        (timestamp, role, message)
    )
    conn.commit()

# === PDF Context ===
def extract_text_from_pdf_file(file_path):
    text = ""
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text()
    return text[:5000]

try:
    website_context = extract_text_from_pdf_file("C:\\Users\\Admin\\inxits_brochure.pdf")
except Exception as e:
    website_context = "Inxits.com helps users make better mutual fund decisions with comparison, filtering, and overlap analysis tools."
    st.warning(f"⚠️ PDF load failed. Using fallback. Error: {e}")

# === System Prompt ===
system_intro = (
    "You are a helpful, friendly, and concise mutual fund assistant chatbot for Inxits.com.\n"
    "Your job is to help Indian retail investors understand and use Inxits — a commission-free, DIY platform for mutual fund analysis.\n"
    "Inxits provides tools like return comparison, fund screening, and portfolio overlap detection to help users invest smarter.\n\n"
    "🧠 Tone: Clear, jargon-free, informative. Avoid promotional or vague statements. Focus on features, tools, and user value.\n\n"
    f"📄 Below is the latest official website/brochure context for Inxits:\n{website_context}\n\n"
    "📌 When a user asks general questions like 'What is Inxits?', give a concise summary.\n"
    "📌 When a user asks for more detail — e.g., 'Tell me more about Inxits', 'Explain Inxits in detail' — then pull content from the website context above and summarize it clearly in 200–300 words.\n"
    "📌 You may also refer to specific tools, examples, or use cases described in the context.\n\n"
    "If the user asks about something else (like returns, overlap, SIPs), respond appropriately using relevant parts of the context and tools offered by Inxits.\n"
)
chat.send_message(system_intro)

# === Session State Setup ===
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'tool_memory' not in st.session_state:
    st.session_state.tool_memory = {}
if 'last_intent' not in st.session_state:
    st.session_state.last_intent = None
if 'last_topic' not in st.session_state:
    st.session_state.last_topic = None

# === Custom Responses ===
CUSTOM_RESPONSES = {
    "what is inxits": """**Inxits** is a commission-free, DIY mutual fund platform designed for retail investors who want to make smarter, unbiased investment decisions.

💡 What makes Inxits different?
- No sales pitch. No conflict of interest. Just clear, data-backed tools.
- Built by data scientists and finance pros who believe investing should be intelligent, not overwhelming.

🧰 Core Tools:
- **Return Comparison** → See side-by-side performance, risk, and consistency.
- **Explore Tool** → Filter top-rated funds by category, risk, AMC, and more.
- **Portfolio Overlap** → Avoid holding the same stock across different funds.

🧠 Whether you’re saving for retirement, tax saving, or SIP planning — Inxits empowers you to invest like a pro.
""",
    "more about inxits": """Inxits offers a modern way to evaluate mutual funds with 100% transparency.

You can:
- 🔍 Explore top ELSS, Large Cap, or Balanced funds using 15+ filters.
- 🧮 Compare up to 5 funds based on Sharpe, Sortino, and rolling returns.
- 📊 Detect overlapping holdings across funds to avoid hidden risks.

✨ All tools are DIY, ad-free, and built for people who want control and clarity in investing.

Explore more at [inxits.com](https://inxits.com).""",
    "who made inxits": "Inxits.com is built by a passionate team of data scientists, engineers, and finance professionals to empower retail investors.",
    "how to compare funds": "You can compare up to 5 mutual funds side-by-side using the 🧮 Return Comparison Tool: https://portal.inxits.com/ReturnComparison/"
}

# === Tool Suggestions & Routing ===
def choose_variant(key, variants, url):
    last = st.session_state.tool_memory.get(key)
    options = [v for v in variants if v != last] or variants
    choice = random.choice(options)
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

# === Goal Detection ===
GOAL_KEYWORDS = {
    "retirement": "For retirement planning, consider long-term equity or hybrid funds.\nTry filtering with our 🔍 **Explore Tool**: [Explore Funds](https://portal.inxits.com/Explore/)",
    "tax": "For tax saving, explore **ELSS Funds** under section 80C.\nUse the 🔍 **Explore Tool** to filter ELSS options: [Explore Funds](https://portal.inxits.com/Explore/)",
    "child": "For child education or future planning, consider balanced or hybrid funds with consistent returns.\nExplore top-rated funds here: [Explore Funds](https://portal.inxits.com/Explore/)",
    "sip": "For SIP investments, start by shortlisting funds via category & risk using 🔍 **Explore Tool**: [Start SIP Planning](https://portal.inxits.com/Explore/)"
}

def detect_goal(message):
    msg = message.lower()
    for goal, response in GOAL_KEYWORDS.items():
        if goal in msg:
            return response
    return None

# === Intent Detection ===
def detect_intent(message):
    prompt = f"""
Classify the user message into one of:
- GREETING
- HELP_REQUEST
- TOOL_QUERY
- OTHER
Respond with one word.

User message: "{message}"
"""
    response = model.generate_content(prompt)
    return response.text.strip().upper()

def is_meaningful_input(message):
    if len(message.strip()) <= 3:
        return False
    prompt = f"""
You are a chatbot for mutual fund investing. Determine if the following is a meaningful user input. Respond ONLY with YES or NO.

User: "{message}"
"""
    response = model.generate_content(prompt)
    return response.text.strip().upper() == "YES"

def match_custom_response(user_message):
    user_message = user_message.lower()
    for key in CUSTOM_RESPONSES:
        if key in user_message:
            return CUSTOM_RESPONSES[key]
        similarity = SequenceMatcher(None, key, user_message).ratio()
        if similarity > 0.7:
            return CUSTOM_RESPONSES[key]
    return None

# === Streamlit UI ===
st.title("💬 Inxits Mutual Fund Assistant")

# First time onboarding
if len(st.session_state.chat_history) == 0:
    onboarding = (
        "👋 Welcome to the Inxits Mutual Fund Assistant!\n\n"
        "Curious about how Inxits works or what tools we offer?\n"
        "You can ask things like:\n"
        "- 'What is Inxits?'\n"
        "- 'How can I compare mutual funds?'\n"
        "- 'What does the overlap tool do?'\n\n"
        "Let’s explore smarter ways to invest. 🚀"
    )
    st.chat_message("assistant").markdown(onboarding)

for msg in st.session_state.chat_history:
    st.chat_message(msg["role"]).markdown(msg["content"])

user_input = st.chat_input("Ask me anything about Inxits, funds, or your goals...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.chat_message("user").markdown(user_input)
    log_to_db("User", user_input)

    reply = ""
    tool_response = get_tool_response(user_input)
    goal_response = detect_goal(user_input)
    lower_input = user_input.lower()

    if any(phrase in lower_input for phrase in [
        "explain tools", "what does each tool do", "how do your tools work",
        "compare explore overlap", "all tools", "explain all tools", "what are your features"
    ]):
        reply = (
            "**Here’s what each Inxits tool does:**\n\n"
            "🧮 **Return Comparison Tool**\nCompare up to 5 mutual funds side-by-side based on:\n"
            "- 1Y, 3Y, 5Y returns\n- Sharpe/Sortino ratios\n- Rolling return consistency\n\n"
            "🔍 **Explore Tool**\nFilter and rank funds using 15+ criteria like:\n"
            "- Category, risk level, ratings, returns, AMC\n- Goals like ELSS, Large Cap, SIP\n\n"
            "📊 **Portfolio Overlap Tool**\nAvoid over-diversification by:\n"
            "- Detecting common holdings in selected funds\n- Spotting duplicate exposure\n\n"
            "🧠 All tools are DIY, ad-free, and built for smarter investing."
        )
        st.session_state.last_topic = "tools"

    elif lower_input in ["tell me more", "in detail", "continue", "what else?"]:
        if st.session_state.last_topic in ["inxits", "tools"]:
            reply = (
                "**Inxits** is built for retail investors who want more control and clarity.\n\n"
                "🔧 You can:\n- Compare up to 5 funds deeply on performance & risk\n"
                "- Use 15+ filters to find top-performing funds by goal or type\n"
                "- Spot hidden overlaps in your investments to diversify smarter\n\n"
                "Built by a team of data scientists & finance nerds — for users who care about quality over hype."
            )
        else:
            reply = "You can explore all tools at [Inxits.com](https://inxits.com). Let me know what you're looking for."

    elif goal_response:
        reply = goal_response
        st.session_state.last_topic = "goal"

    elif tool_response:
        reply = tool_response
        st.session_state.last_topic = "tool"

    elif (matched := match_custom_response(user_input)):
        reply = matched
        st.session_state.last_topic = "inxits" if "inxits" in lower_input else None

    else:
        intent = detect_intent(user_input)
        st.session_state.last_intent = intent
        if "inxits" in lower_input:
            st.session_state.last_topic = "inxits"

        if intent == "GREETING":
            reply = "👋 Hey there! I’m your assistant from **Inxits.com**. Ask me about funds, comparisons, or tools to invest smarter."
        elif intent == "HELP_REQUEST":
            reply = "📌 Here’s what you can ask me:\n- What does each tool do?\n- What does Inxits do\n- How to compare funds effectively"
        elif not is_meaningful_input(user_input):
            prompt = f"Based on this context:\n{website_context}\nRespond briefly to:\n{user_input}"
            result = chat.send_message(prompt)
            reply = result.text.strip() or "🤔 Sorry, I didn’t get that. Can you rephrase?"
        else:
            prompt = f"Context: {website_context}\nUser: {user_input}\nRespond briefly and clearly:"
            result = chat.send_message(prompt)
            reply = result.text

    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    st.chat_message("assistant").markdown(reply)
    log_to_db("Assistant", reply)
