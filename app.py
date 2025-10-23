from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import mysql.connector
import re
import urllib.parse
import requests

app = Flask(__name__)

# 🔑 Configure your Gemini API Key
genai.configure(api_key="AIzaSyCUrUWOBpcO9JeP_YZLdp2ydWlHfIgSyoM")
model = genai.GenerativeModel("gemini-2.5-flash-lite")

# Connect to MySQL database
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="chatbot"
)

def convert_markdown_links_to_html(text):
    """Convert Markdown-style links to clickable HTML links"""
    return re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)

def get_user_country(ip_address):
    """Get country from IP using a free API"""
    try:
        response = requests.get(f"https://ipinfo.io/{ip_address}/json")
        data = response.json()
        return data.get("country", "IN")  # default to IN
    except:
        return "IN"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_response', methods=['POST'])
def get_response():
    user_message = request.json.get("message", "").strip()

    # Save user message to DB
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO enquiries (user_message) VALUES (%s)", (user_message,))
        conn.commit()
        cursor.close()
    except Exception as db_error:
        print("Database error:", db_error)

    # 🔹 Refined prompt — natural but still constrained
    prompt = f"""
You are a smart Indian shopping assistant.


Your task:
- Answer all product-related queries, including questions about features, specifications, comparisons, reviews, recommendations, colors, and price.
- Always provide the exact product name as it appears in India (do not generalize or shorten names).
- Only consider products that are available in India.
- If the user mentions a price range (like "under 500", "below 2000", "around 1000"), list only products approximately within that range.
- Always display prices in Indian rupees (₹). Do not use any other currency.
- If the question is clearly unrelated to products (for example: history, politics, movies, general knowledge), politely respond:
  "I am a shopping assistant and can only help you with product-related queries."
- For product listings, provide 2–3 realistic examples.
- Format each product line as:
  Product Name - Price (₹)
- Keep your answer clear, neat, and conversational.

User Query: {user_message}
"""


    try:
        # Generate product info using Gemini
        response = model.generate_content(prompt)
        reply_text = response.text.strip() if hasattr(response, "text") else "Sorry, I couldn’t process that right now."

        # Handle non-product queries
        if "shopping assistant" in reply_text.lower() and "product-related" in reply_text.lower():
            return jsonify({"reply": reply_text})

        # Format product links
        lines = [line.strip() for line in reply_text.split("\n") if line.strip()]
        reply_with_links = []

        for line in lines:
            if '-' in line and '₹' in line:
                try:
                    product_name, price = line.split('-', 1)
                    product_name = product_name.strip()
                    price = price.strip()

                    search_query = urllib.parse.quote_plus(product_name)
                    amazon_link = f"https://www.amazon.in/s?k={search_query}"
                    flipkart_link = f"https://www.flipkart.com/search?q={search_query}"

                    reply_with_links.append(
                        f"<b><u><a href='{amazon_link}' target='_blank'>Amazon: {product_name}</a></u></b> / "
                        f"<b><u><a href='{flipkart_link}' target='_blank'>Flipkart: {product_name}</a></u></b> - {price}"
                    )
                except Exception:
                    reply_with_links.append(line)
            else:
                reply_with_links.append(line)

        reply_html = "<br>".join(reply_with_links)
        return jsonify({"reply": reply_html})

    except Exception as e:
        return jsonify({"reply": f"⚠️ Error: {str(e)}"})




@app.route('/get_total_enquiries')
def get_total_enquiries():
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM enquiries")
    total = cursor.fetchone()[0]
    cursor.close()
    return jsonify({"total": total})

if __name__ == "__main__":
    app.run(debug=True)
