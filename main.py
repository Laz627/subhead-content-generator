import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse
from collections import Counter
from openai import OpenAI
from docx import Document
from io import BytesIO
import time
import random

# Set page config
st.set_page_config(page_title="SEO Content Outline Generator", layout="wide")
st.title("SEO Content Outline Generator")

# Initialize session state
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

def get_top_urls(keyword, num_results=5):
    url = f"https://www.google.com/search?q={quote_plus(keyword)}&num={num_results*2}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        urls = []
        for result in soup.select("div.yuRUbf > a"):
            href = result.get('href')
            if href and href.startswith('http'):
                parsed_url = urlparse(href)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                if base_url not in urls:
                    urls.append(base_url)
                    if len(urls) == num_results:
                        break
        
        st.write(f"Extracted {len(urls)} URLs:")
        for url in urls:
            st.write(url)
        
        return urls
    except Exception as e:
        st.error(f"Error fetching search results: {str(e)}")
        return []

def extract_headings(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Try to identify the main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.find('div', id='content')
        
        if main_content:
            content_to_search = main_content
        else:
            # If we can't identify a clear main content area, use the whole body
            # but exclude common non-content areas
            for element in soup(['header', 'nav', 'footer', 'aside']):
                element.decompose()
            content_to_search = soup.body
        
        headings = {
            "h2": [h.text.strip() for h in content_to_search.find_all("h2") if h.text.strip()],
            "h3": [h.text.strip() for h in content_to_search.find_all("h3") if h.text.strip()],
            "h4": [h.text.strip() for h in content_to_search.find_all("h4") if h.text.strip()]
        }
        
        return headings
    except Exception as e:
        st.warning(f"Error extracting headings from {url}: {str(e)}")
        return {"h2": [], "h3": [], "h4": []}

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
st.write("Enter your OpenAI API key and target keyword below:")

api_key = st.text_input("OpenAI API key:", value=st.session_state.api_key, type="password")
keyword = st.text_input("Target keyword:", value=st.session_state.keyword)

# Update session state
st.session_state.api_key = api_key
st.session_state.keyword = keyword

if st.button("Generate Content Outline"):
    if api_key and keyword:
        with st.spinner("Analyzing top search results..."):
            urls = get_top_urls(keyword)
            if not urls:
                st.error("No URLs were extracted. Please try a different keyword or try again later.")
            else:
                all_headings = []
                for url in urls:
                    time.sleep(random.uniform(1, 3))  # Random delay to avoid rate limiting
                    headings = extract_headings(url)
                    all_headings.append(headings)
                    st.write(f"Headings extracted from {url}:")
                    st.write(headings)
                
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
        st.error("Please enter both your OpenAI API key and a target keyword to generate a content outline.")
