from flask import Flask, request, jsonify, render_template, session
import requests
import openai
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

openai.api_type = "azure"
openai.api_version = "2023-06-01-preview" 
openai.api_base = "https://a11ygenerative.openai.azure.com/"
openai.api_key = os.getenv("aoaikey")
subscription_key = os.getenv("bingkey")

# List of websites to search in
websites = [
    "microsoft.com"
]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    message = request.json['message']
    session['messages'].append({"role": "user", "content": message})

    # Query the LLM for relevant search terms
    search_terms_response = openai.ChatCompletion.create(
        engine="a11yultimate",
        messages=session['messages'] + [{"role": "system", "content": "What would be the relevant search terms for the web search based on the user's question? Please provide only the search terms as they will be used programmatically."}]
    )

    search_terms = search_terms_response['choices'][0]['message']['content']

    headers = {"Ocp-Apim-Subscription-Key" : subscription_key}
    params  = {"q": search_terms, "textDecorations": True, "textFormat": "HTML"}
    response = requests.get("https://api.bing.microsoft.com/v7.0/search", headers=headers, params=params)
    response.raise_for_status()
    search_results = response.json()

    search_content = []
    used_urls = []
    for result in search_results["webPages"]["value"]:
        if any(website in result["url"] for website in websites):
            response = requests.get(result["url"])
            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphs = soup.find_all('p')
            page_text = ' '.join([p.get_text() for p in paragraphs])
            search_content.append(page_text)
            used_urls.append(result["url"])
            if len(search_content) == 3:
                break

    search_content = ' '.join(search_content)

    # Ask the LLM the user's question with the obtained search results
    llm_response = openai.ChatCompletion.create(
        engine="a11yultimate",
        messages=session['messages'] + [
            {"role": "system", "content": "Here's some additional information that can help you provide an up-to-date answer. The following URLs were used for this information and you absolutely must cite these URLs in the answer you provide the user: "     + ', '.join(used_urls)},
            {"role": "assistant", "content": search_content}
        ]
    )

    answer = llm_response['choices'][0]['message']['content']
    session['messages'].append({"role": "assistant", "content": answer})
    return jsonify({"role": "assistant", "content": answer})

@app.before_request
def before_request():
    if 'messages' not in session:
        session['messages'] = [
            {"role": "system", "content": "Hi, I am the Microsoft accessibility bot that will provide you information about accessibility features in Microsoft products."},
        ]

if __name__ == '__main__':
    app.run(port=5000)

