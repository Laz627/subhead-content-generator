import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from collections import Counter
import trafilatura
from openai import OpenAI
from docx import Document
from io import BytesIO
import time
import random

# Set page config
st.set_page_config(page_title="SEO Content Outline Generator", layout="wide")
st.title("SEO Content Outline Generator")

# Function to get top 5 Google search results
def get_top_urls(keyword, num_results=5):
    url = f"https://www.google.com/search?q={quote_plus(keyword)}&num={num_results+5}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    urls = []
    for result in soup.select("div.yuRUbf > a"):
        if len(urls) < num_results:
            urls.append(result["href"])
    return urls

# Function to extract headings from a URL
def extract_headings(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        soup = BeautifulSoup(trafilatura.extract(downloaded), "html.parser")
        headings = {
            "h2": [h.text.strip() for h in soup.find_all("h2")],
            "h3": [h.text.strip() for h in soup.find_all("h3")],
            "h4": [h.text.strip() for h in soup.find_all("h4")]
        }
        return headings
    except Exception as e:
        st.warning(f"Error extracting headings from {url}: {str(e)}")
        return {"h2": [], "h3": [], "h4": []}

# Function to analyze headings
def analyze_headings(all_headings):
    analysis = {}
    for level in ["h2", "h3", "h4"]:
        headings = [h for url_headings in all_headings for h in url_headings[level]]
        analysis[level] = {
            "count": len(headings),
            "avg_length": sum(len(h) for h in headings) / len(headings) if headings else 0,
            "common_words": Counter(" ".join(headings).lower().split()).most_common(10)
        }
    return analysis

# Function to generate optimized heading structure using GPT-4
def generate_optimized_structure(keyword, heading_analysis, api_key):
    client = OpenAI(api_key=api_key)
    
    prompt = f"""
    Generate an optimized heading structure for a content brief on the keyword: "{keyword}"
    
    Use the following heading analysis as a guide:
    {heading_analysis}
    
    Requirements:
    - Create a structure with H2s, H3s, and H4s
    - Incorporate common themes and words from the analysis
    - Ensure the structure is comprehensive and covers the topic thoroughly
    - Include brief directions on what content should be included under each heading
    
    Provide the output in the following format:
    H2: [Heading]
    - [Brief direction on content]
      H3: [Subheading]
      - [Brief direction on content]
        H4: [Sub-subheading]
        - [Brief direction on content]
    
    Repeat this structure for multiple H2s, H3s, and H4s as needed.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an SEO expert creating optimized content outlines."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error generating optimized structure: {str(e)}")
        return None

# Function to create Word document
def create_word_document(keyword, optimized_structure):
    doc = Document()
    doc.add_heading(f'Content Brief: {keyword}', 0)
    
    for line in optimized_structure.split('\n'):
        if line.startswith('H2:'):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith('H3:'):
            doc.add_heading(line[3:].strip(), level=3)
        elif line.startswith('H4:'):
            doc.add_heading(line[3:].strip(), level=4)
        elif line.strip().startswith('-'):
            doc.add_paragraph(line.strip(), style='List Bullet')
    
    return doc

# Streamlit UI
api_key = st.text_input("Enter your OpenAI API key:", type="password")
keyword = st.text_input("Enter your target keyword:")

if st.button("Generate Content Outline") and api_key and keyword:
    with st.spinner("Analyzing top search results..."):
        urls = get_top_urls(keyword)
        all_headings = []
        for url in urls:
            time.sleep(random.uniform(1, 3))  # Random delay to avoid rate limiting
            all_headings.append(extract_headings(url))
        
        heading_analysis = analyze_headings(all_headings)
        st.write("Heading Analysis:", heading_analysis)
        
    with st.spinner("Generating optimized content structure..."):
        optimized_structure = generate_optimized_structure(keyword, heading_analysis, api_key)
        if optimized_structure:
            st.write("Optimized Content Structure:")
            st.text(optimized_structure)
            
            # Create and offer Word document download
            doc = create_word_document(keyword, optimized_structure)
            bio = BytesIO()
            doc.save(bio)
            st.download_button(
                label="Download Content Brief",
                data=bio.getvalue(),
                file_name=f"content_brief_{keyword.replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
else:
    st.write("Please enter your OpenAI API key and a target keyword to generate a content outline.")
