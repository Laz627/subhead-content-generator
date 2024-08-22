import streamlit as st
import requests
from bs4 import BeautifulSoup
from collections import Counter
from openai import OpenAI
from docx import Document
from docx.shared import Pt
from docx.enum.style import WD_STYLE_TYPE
from io import BytesIO
import time
import random
from serpapi import GoogleSearch

# Set page config
st.set_page_config(page_title="SEO Content Outline Generator", layout="wide")
st.title("SEO Content Outline Generator")

# Author information and instructions
st.write("Created by Brandon Lazovic")
st.markdown("""
## How to use this tool:
1. Enter your OpenAI and SerpApi API keys in the fields below.
2. Input your target keyword.
3. Click 'Generate Content Outline' to analyze top-ranking pages and create an optimized content structure.
4. Review the extracted subheads from top results and the AI-generated optimized outline.
5. Download the content brief as a Word document.

This tool helps content creators and SEO professionals generate comprehensive, SEO-optimized content outlines based on top-ranking pages for any given keyword.
""")

# Initialize session state
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'serpapi_api_key' not in st.session_state:
    st.session_state.serpapi_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

def get_top_urls(keyword, serpapi_key, num_results=5):
    params = {
        "api_key": serpapi_key,
        "engine": "google",
        "q": keyword,
        "num": num_results,
        "gl": "us",
        "hl": "en"
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        urls = []
        for result in results.get("organic_results", [])[:num_results]:
            urls.append(result["link"])
        
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
            "common_words": Counter(" ".join(headings).lower().split()).most_common(10),
            "examples": headings[:10]  # Include up to 10 example headings
        }
    return analysis

def generate_optimized_structure(keyword, heading_analysis, api_key):
    client = OpenAI(api_key=api_key)
    
    prompt = f"""
    Generate an optimized heading structure for a content brief on the keyword: "{keyword}"
    
    Use the following heading analysis as a guide:
    {heading_analysis}
    
    Pay special attention to the 'examples' in each heading level, as these are actual headings from top-ranking pages.
    
    Requirements:
    1. Create a logical, user-focused structure with H2s, H3s, and H4s that guides the reader through understanding the topic comprehensively.
    2. Ensure the structure flows cohesively, focusing on what users should know about the topic.
    3. Avoid using branded subheads unless absolutely necessary for the topic.
    4. Include brief directions on what content should be included under each heading.
    5. Maintain a similar style and tone to the example headings while improving clarity and user focus.
    6. Organize the content in a way that naturally progresses from basic concepts to more advanced ideas.
    7. Include sections that address common questions or concerns related to the topic.
    8. Where applicable, include comparisons with alternatives or related concepts.
    9. Consider including a section on practical application or next steps for the reader.
    10. Ensure the outline covers the topic thoroughly while remaining focused and relevant to the main keyword.

    Provide the output in the following format:
    H2: [Heading based on examples and best practices]
    - [Brief direction on content]
      H3: [Subheading based on examples and best practices]
      - [Brief direction on content]
        H4: [Sub-subheading based on examples and best practices]
        - [Brief direction on content]
    
    Repeat this structure as needed, ensuring a logical flow of information that best serves the user's needs based on the given keyword.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an SEO expert creating optimized, user-focused content outlines for any given topic."},
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
    
    # Add styles
    styles = doc.styles
    h1_style = styles.add_style('H1', WD_STYLE_TYPE.PARAGRAPH)
    h1_style.font.size = Pt(18)
    h1_style.font.bold = True
    
    h2_style = styles.add_style('H2', WD_STYLE_TYPE.PARAGRAPH)
    h2_style.font.size = Pt(16)
    h2_style.font.bold = True
    
    h3_style = styles.add_style('H3', WD_STYLE_TYPE.PARAGRAPH)
    h3_style.font.size = Pt(14)
    h3_style.font.bold = True
    
    h4_style = styles.add_style('H4', WD_STYLE_TYPE.PARAGRAPH)
    h4_style.font.size = Pt(12)
    h4_style.font.bold = True
    
    # Add title
    doc.add_paragraph(f'Content Brief: {keyword}', style='H1')
    
    # Process the optimized structure
    lines = optimized_structure.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('H2:'):
            doc.add_paragraph(f"H2: {line[3:].strip()}", style='H2')
            i += 1
            # Add content for H2
            while i < len(lines) and lines[i].strip().startswith('-'):
                doc.add_paragraph(lines[i].strip(), style='List Bullet')
                i += 1
        elif line.startswith('H3:'):
            doc.add_paragraph(f"H3: {line[3:].strip()}", style='H3')
            i += 1
            # Add content for H3
            while i < len(lines) and lines[i].strip().startswith('-'):
                doc.add_paragraph(lines[i].strip(), style='List Bullet')
                i += 1
        elif line.startswith('H4:'):
            doc.add_paragraph(f"H4: {line[3:].strip()}", style='H4')
            i += 1
            # Add content for H4
            while i < len(lines) and lines[i].strip().startswith('-'):
                doc.add_paragraph(lines[i].strip(), style='List Bullet')
                i += 1
        else:
            i += 1
    
    return doc

# Streamlit UI
st.write("Enter your API keys and target keyword below:")

openai_api_key = st.text_input("OpenAI API key:", value=st.session_state.openai_api_key, type="password")
serpapi_api_key = st.text_input("SerpApi API key:", value=st.session_state.serpapi_api_key, type="password")
keyword = st.text_input("Target keyword:", value=st.session_state.keyword)

# Update session state
st.session_state.openai_api_key = openai_api_key
st.session_state.serpapi_api_key = serpapi_api_key
st.session_state.keyword = keyword

if st.button("Generate Content Outline"):
    if openai_api_key and serpapi_api_key and keyword:
        with st.spinner("Analyzing top search results..."):
            urls = get_top_urls(keyword, serpapi_api_key)
            if not urls:
                st.error("No URLs were extracted. Please check your SerpApi key and try again.")
            else:
                all_headings = []
                for url in urls:
                    time.sleep(random.uniform(1, 3))  # Random delay to avoid rate limiting
                    headings = extract_headings(url)
                    all_headings.append((url, headings))
                
                # Display extracted subheads
                st.subheader("Extracted Subheads from Top Results:")
                for i, (url, headings) in enumerate(all_headings, 1):
                    st.write(f"URL {i}: {url}")
                    for level in ["h2", "h3", "h4"]:
                        if headings[level]:
                            st.write(f"{level.upper()}:")
                            for heading in headings[level]:
                                st.write(f"- {heading}")
                    st.write("---")
                
                heading_analysis = analyze_headings([h for _, h in all_headings])
                
                with st.spinner("Generating optimized content structure..."):
                    optimized_structure = generate_optimized_structure(keyword, heading_analysis, openai_api_key)
                    if optimized_structure:
                        st.subheader("Optimized Content Structure:")
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
        st.error("Please enter your OpenAI API key, SerpApi API key, and a target keyword to generate a content outline.")
