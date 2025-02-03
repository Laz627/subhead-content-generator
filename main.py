import streamlit as st
from bs4 import BeautifulSoup
from collections import Counter
from docx import Document
from docx.shared import Pt
from io import BytesIO
import numpy as np
import openai
import re

st.set_page_config(page_title="SEO Content Outline Generator", layout="wide")
st.title("SEO Content Outline Generator")

st.markdown("""
## Instructions:
1. **Enter your OpenAI API key.**
2. **Input your target keyword.**
3. **Upload competitor HTML files**.
4. Choose if you want just an outline or full content.
5. Choose article length:
   - Short: ~750 words total
   - Medium: ~1250-1500 words
   - Long: ~1500-3000 words
6. Click **'Generate Content Outline'**.
7. Download the final content as a Word document.
""")

if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

# -----------------------------------------------
# Helper functions (HTML extraction, cosine_similarity, etc.)
# -----------------------------------------------

def extract_headings_and_body(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    tags_to_remove = ['script', 'style', 'noscript', 'header', 'footer', 'nav', 'aside']
    for tag in tags_to_remove:
        for element in soup.find_all(tag):
            element.decompose()

    classes_ids_to_remove = ['nav', 'navigation', 'sidebar', 'footer', 'header', 'menu',
                             'breadcrumbs', 'breadcrumb', 'site-footer', 'site-header',
                             'widget', 'widgets', 'site-navigation', 'main-navigation',
                             'secondary-navigation', 'site-sidebar']
    for class_or_id in classes_ids_to_remove:
        for element in soup.find_all(attrs={'class': class_or_id}):
            element.decompose()
        for element in soup.find_all(attrs={'id': class_or_id}):
            element.decompose()

    main_content = (soup.find('main') or soup.find('article') or 
                    soup.find('div', class_='content') or soup.find('div', id='content'))
    if main_content:
        content_to_search = main_content
    else:
        for element in soup(['header', 'nav', 'footer', 'aside']):
            element.decompose()
        content_to_search = soup.body if soup.body else soup

    headings = {
        "h1": [h.get_text(separator=' ', strip=True) for h in content_to_search.find_all("h1") if h.get_text(strip=True)],
        "h2": [h.get_text(separator=' ', strip=True) for h in content_to_search.find_all("h2") if h.get_text(strip=True)],
        "h3": [h.get_text(separator=' ', strip=True) for h in content_to_search.find_all("h3") if h.get_text(strip=True)],
        "h4": [h.get_text(separator=' ', strip=True) for h in content_to_search.find_all("h4") if h.get_text(strip=True)]
    }

    paragraphs = [p.get_text(separator=' ', strip=True) for p in content_to_search.find_all('p') if p.get_text(strip=True)]
    meta_title = soup.title.string.strip() if soup.title else ''
    meta_description_tag = soup.find('meta', attrs={'name': 'description'})
    meta_description = meta_description_tag['content'].strip() if meta_description_tag else ''

    return meta_title, meta_description, headings, paragraphs

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# -----------------------------------------------
# New / Optimized Embedding Functions
# -----------------------------------------------

# Cache the embedding of the keyword so that if the same keyword is used again,
# you avoid an extra API call.
@st.cache(suppress_st_warning=True)
def get_keyword_embedding(text, model="text-embedding-ada-002"):
    response = openai.Embedding.create(input=[text], model=model)
    return np.array(response['data'][0]['embedding'], dtype=np.float32)

def get_batch_embeddings(texts, model="text-embedding-ada-002"):
    """
    Batch request embeddings for a list of texts.
    """
    response = openai.Embedding.create(input=texts, model=model)
    return [np.array(item['embedding'], dtype=np.float32) for item in response['data']]

# -----------------------------------------------
# Updated Insights Functions with Batched Embeddings
# -----------------------------------------------

def generate_semantic_insights(keyword, all_headings):
    competitor_headings = []
    for h_set in all_headings:
        # Use .get(...) in case any level is missing
        competitor_headings.extend(h_set.get("h2", []))
        competitor_headings.extend(h_set.get("h3", []))
        competitor_headings.extend(h_set.get("h4", []))
    
    if not competitor_headings:
        return "No additional semantic insights available."
    
    keyword_emb = get_keyword_embedding(keyword)
    # Batch request embeddings for all competitor headings
    heading_embeddings = get_batch_embeddings(competitor_headings)
    
    scored = [(ch, cosine_similarity(keyword_emb, emb))
              for ch, emb in zip(competitor_headings, heading_embeddings)]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_headings = [x[0] for x in scored[:5]]
    
    summary = "Topically relevant areas based on competitor headings:\n"
    for th in top_headings:
        summary += f"- {th}\n"
    summary += "\nConsider covering these topics thoroughly."
    return summary.strip()

def generate_body_insights(keyword, all_paragraphs):
    competitor_paragraphs = [p for plist in all_paragraphs for p in plist if len(p.split()) > 5]
    
    if not competitor_paragraphs:
        return "No additional body insights available."
    
    keyword_emb = get_keyword_embedding(keyword)
    # Batch request embeddings for competitor paragraphs
    paragraph_embeddings = get_batch_embeddings(competitor_paragraphs)
    
    scored = [(para, cosine_similarity(keyword_emb, emb))
              for para, emb in zip(competitor_paragraphs, paragraph_embeddings)]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_paras = [x[0] for x in scored[:5]]
    
    insights = "Competitor Body Insights (relevant paragraphs):\n"
    for i, tp in enumerate(top_paras, 1):
        insights += f"\nParagraph {i}:\n{tp}\n"
    return insights.strip()

# -----------------------------------------------
# Function to validate the generated output against the required template
# -----------------------------------------------
def validate_output(output):
    required_markers = [
        r"\*\*Meta Title:\*\*",
        r"\*\*Meta Description:\*\*",
        r"\*\*H1:\*\*",
        r"\*\*H2:",
        r"\*\*Final Summary\*\*"
    ]
    
    errors = []
    for marker in required_markers:
        if not re.search(marker, output):
            errors.append(f"Missing required element: {marker}")
    
    if errors:
        return False, errors
    return True, "All required elements found."

# -----------------------------------------------
# Generate Optimized Structure with Insights
# -----------------------------------------------
def generate_optimized_structure_with_insights(keyword, heading_analysis, competitor_meta_info, api_key, content_mode, article_length, all_headings, all_paragraphs):
    openai.api_key = api_key

    if article_length == "Short":
        word_count_range = "around 750 words"
        paragraph_guidance = """
- If Full Content: ~2 paragraphs (~100 words each) per H2; H3/H4 ~75 words each.
- If Outline mode: Just 1-2 sentences per heading.
"""
    elif article_length == "Medium":
        word_count_range = "approximately 1250-1500 words"
        paragraph_guidance = """
- If Full Content: Each H2 ~2-3 paragraphs (~100 words each); H3/H4 ~100 words each.
- If Outline mode: Just 1-2 sentences per heading.
Use H3s/H4s to break content.
"""
    else:  # Long
        word_count_range = "approximately 1500-3000 words"
        paragraph_guidance = """
- If Full Content: Each H2 ~3 paragraphs (~100 words each); multiple H3/H4 (~100 words each).
- If Outline mode: Just 1-2 sentences per heading.
Aim for ~20-25 headings total. More headings vs. overly long sections.
"""

    # Get the insights from competitor data
    semantic_insights = generate_semantic_insights(keyword, all_headings)
    body_insights = generate_body_insights(keyword, all_paragraphs)

    # Summarize competitor meta info to avoid overloading the prompt
    competitor_summary = competitor_meta_info[:500] + "..." if len(competitor_meta_info) > 500 else competitor_meta_info

    # IMPORTANT: Explicit instructions must come first.
    prompt = f"""
IMPORTANT: Your output MUST include the following sections EXACTLY as formatted:
**Meta Title:** [Your meta title here]
**Meta Description:** [Your meta description here]
**H1:** [Your H1 here]
**H2:** [Your H2 headings and guidance]
...
**Final Summary:** [Your final summary here]

Do NOT output any competitor data verbatim. Use the competitor insights below only for context.

[Competitor Data Summary]:
{competitor_summary}

Now, create a content outline for the target keyword "{keyword}" with the following requirements:
- Mode: {content_mode} (Full Content or Outline)
- Word Count Target: {word_count_range}
- {paragraph_guidance}

Instructions:
1. Provide meta title, meta description, and H1 in this format:
   **Meta Title:** ...
   **Meta Description:** ...
   **H1:** ...
2. Produce a structured outline with H2, H3, and H4 headings covering all subtopics.
3. { "Write fully formed, publish-ready paragraphs under each heading." if content_mode == "Full Content" 
           else "Provide only 1-2 sentence guidance under each heading (no full paragraphs)." }
4. End with a **Final Summary** section.

**Example (Outline mode):**
**Meta Title:** My Title
**Meta Description:** My Description
**H1:** My H1

**H2: Topic Heading**
(1-2 sentences guidance here, no full paragraphs.)

**Final Summary**
(A brief concluding summary.)

Remember: Do not output any competitor data. Follow the template exactly.
"""

    try:
        response = openai.ChatCompletion.create(
            model="o3-mini",
            messages=[
                {"role": "system", "content": "You are a helpful SEO content strategist. Follow the instructions exactly."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=16000
        )

        output = response.choices[0].message.content

        # Validate the output against our required template
        valid, validation_message = validate_output(output)
        if not valid:
            st.error("Validation errors in generated output: " + "; ".join(validation_message))
            return None

        return output
    except Exception as e:
        st.error(f"Error generating optimized structure: {str(e)}")
        return None

# -----------------------------------------------
# Word Document Creation Function
# -----------------------------------------------
def create_word_document(keyword, optimized_structure):
    if not optimized_structure:
        st.error("No content to create document.")
        return None

    doc = Document()
    styles = doc.styles

    h4_style = styles['Heading 4']
    h4_font = h4_style.font
    h4_font.size = Pt(12)
    h4_font.bold = True

    h2_style = styles['Heading 2']
    h2_font = h2_style.font
    h2_font.size = Pt(16)
    h2_font.bold = True

    h3_style = styles['Heading 3']
    h3_font = h3_style.font
    h3_font.size = Pt(14)
    h3_font.bold = True

    doc.add_heading(f'Content Brief: {keyword}', level=1)
    lines = optimized_structure.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('**Meta Title:**'):
            doc.add_heading('Meta Title', level=4)
            doc.add_paragraph(line.replace('**Meta Title:**', '').strip())
        elif line.startswith('**Meta Description:**'):
            doc.add_heading('Meta Description', level=4)
            doc.add_paragraph(line.replace('**Meta Description:**', '').strip())
        elif line.startswith('**H1:**'):
            doc.add_heading('H1', level=4)
            doc.add_paragraph(line.replace('**H1:**', '').strip())
        elif line.startswith('**H2:'):
            heading_text = line.replace('**H2:', '').replace('**', '').strip()
            doc.add_heading(heading_text, level=2)
        elif line.startswith('**H3:'):
            heading_text = line.replace('**H3:', '').replace('**', '').strip()
            doc.add_heading(heading_text, level=3)
        elif line.startswith('**H4:'):
            heading_text = line.replace('**H4:', '').replace('**', '').strip()
            doc.add_heading(heading_text, level=4)
        elif line.startswith('**Final Summary**'):
            doc.add_heading('Final Summary', level=1)
        elif line == '---':
            continue
        else:
            paragraph = doc.add_paragraph(line)
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)

    return doc

# -----------------------------------------------
# Streamlit UI and Main Application Logic
# -----------------------------------------------
st.write("Enter your API key, target keyword, and upload competitor files:")
openai_api_key = st.text_input("OpenAI API key:", value=st.session_state.openai_api_key, type="password")
keyword = st.text_input("Target keyword:", value=st.session_state.keyword)
content_mode = st.radio("Content Generation Mode:", ("Just Outline & Guidance", "Full Content"))
article_length = st.radio("Article Length:", ("Short", "Medium", "Long"))
uploaded_competitor_files = st.file_uploader("Upload competitor HTML files:", type=['html', 'htm'], accept_multiple_files=True)

st.session_state.openai_api_key = openai_api_key
st.session_state.keyword = keyword

if st.button("Generate Content Outline"):
    if openai_api_key and keyword and uploaded_competitor_files:
        openai.api_key = openai_api_key
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("Extracting data from competitor pages...")
        all_headings = []
        all_paragraphs = []
        competitor_meta_info = ''

        for idx, file in enumerate(uploaded_competitor_files, 1):
            html_content = file.read().decode('utf-8')
            meta_title, meta_description, headings, paragraphs = extract_headings_and_body(html_content)
            all_headings.append(headings)
            all_paragraphs.append(paragraphs)

            competitor_meta_info += f"Competitor #{idx} Meta Title: {meta_title}\n"
            competitor_meta_info += f"Competitor #{idx} Meta Description: {meta_description}\n"
            competitor_headings_str = ''
            for level in ["h1", "h2", "h3", "h4"]:
                for heading in headings[level]:
                    competitor_headings_str += f"{level.upper()}: {heading}\n"
            competitor_meta_info += f"Competitor #{idx} Headings:\n{competitor_headings_str}\n\n"

        progress_bar.progress(33)
        status_text.text("Analyzing headings...")

        # Analyze headings across all competitor files.
        def analyze_headings(all_headings):
            analysis = {}
            total_headings_count = 0
            for level in ["h1", "h2", "h3", "h4"]:
                level_headings = [h for url_headings in all_headings for h in url_headings[level]]
                total_headings_count += len(level_headings)
                analysis[level] = {
                    "count": len(level_headings),
                    "avg_length": sum(len(h) for h in level_headings) / len(level_headings) if level_headings else 0,
                    "common_words": Counter(" ".join(level_headings).lower().split()).most_common(10),
                    "examples": level_headings[:10]
                }
            analysis["total_headings_count"] = total_headings_count
            return analysis

        heading_analysis = analyze_headings(all_headings)

        progress_bar.progress(50)
        status_text.text("Generating optimized content structure...")

        optimized_structure = generate_optimized_structure_with_insights(
            keyword, heading_analysis, competitor_meta_info, openai_api_key, content_mode, article_length, all_headings, all_paragraphs
        )

        if optimized_structure:
            st.subheader("Optimized Content Structure:")
            st.markdown(optimized_structure)

            progress_bar.progress(80)
            status_text.text("Creating Word document...")

            doc = create_word_document(keyword, optimized_structure)
            if doc:
                bio = BytesIO()
                doc.save(bio)
                bio.seek(0)
                st.download_button(
                    label="Download Content Brief",
                    data=bio,
                    file_name=f"content_brief_{keyword.replace(' ', '_')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        else:
            st.error("Failed to generate structure. Please try again.")

        progress_bar.progress(100)
        status_text.text("Process completed.")
    else:
        st.error("Please provide all required inputs.")
