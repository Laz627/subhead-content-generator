import streamlit as st
from bs4 import BeautifulSoup
from collections import Counter
from docx import Document
from docx.shared import Pt
from io import BytesIO
import numpy as np
import openai

# Set page config
st.set_page_config(page_title="SEO Content Outline Generator", layout="wide")
st.title("SEO Content Outline Generator")

st.markdown("""
## Instructions:
1. **Enter your OpenAI API key**.
2. **Input your target keyword.**
3. **Upload competitor HTML files**.
4. Choose if you want just an outline or full content.
5. Choose article length (Short, Medium, or Long).
6. Click **'Generate Content Outline'**.
7. Download the final content as a Word document.
""")

if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

def extract_headings_from_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove non-content elements
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

    meta_title = soup.title.string.strip() if soup.title else ''
    meta_description_tag = soup.find('meta', attrs={'name': 'description'})
    meta_description = meta_description_tag['content'].strip() if meta_description_tag else ''
    return meta_title, meta_description, headings

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

def generate_optimized_structure(keyword, heading_analysis, competitor_meta_info, api_key, content_mode, article_length, relevant_snippets):
    # Set the OpenAI API key
    openai.api_key = api_key

    # Determine suggested subhead count based on article length and competitor complexity
    total_competitor_headings = heading_analysis.get("total_headings_count", 0)
    if article_length == "Short":
        base_min, base_max = 5, 8
    elif article_length == "Medium":
        base_min, base_max = 8, 12
    else:
        base_min, base_max = 12, 20

    extra = min((total_competitor_headings - 20) // 10, base_max - base_min) if total_competitor_headings > 20 else 0
    suggested_min = base_min + extra
    suggested_max = base_max + extra
    suggested_min = min(suggested_min, suggested_max)
    
    length_instruction = f"""
The competitors collectively have about {total_competitor_headings} total headings. 
Try to produce a cohesive structure that covers the topic thoroughly. 
For a {article_length.lower()} article, aim for roughly {suggested_min}-{suggested_max} total H2/H3/H4 headings combined.
"""

    if content_mode == "Full Content":
        content_instructions = f"""
For each heading in the content outline:
- **Content Guidance:** Provide detailed, original paragraphs of content. Incorporate relevant details from the provided competitor snippets if any. 
"""
    else:
        content_instructions = """
For each heading in the content outline:
- **Content Guidance:** Provide a brief (1-2 sentences) description of what should be covered under this heading. 
"""

    snippet_text = ""
    for i, snippet in enumerate(relevant_snippets, 1):
        snippet_text += f"Competitor Snippet #{i}:\n{snippet}\n\n"

    prompt = f"""
You are an SEO content strategist.

Your task is to create an optimized content outline and corresponding guidance (or full content) for a new article targeting the keyword "{keyword}".

- **Competitor Meta and Headings**:
{competitor_meta_info}

- **Relevant Competitor Snippets**:
{snippet_text}

Instructions:
1. Recommend an optimized meta title, meta description, and H1 tag.
2. Generate an optimized heading structure (H2/H3/H4) covering important subtopics and ensuring topical completeness.
3. Ensure the structure flows cohesively from basic to advanced concepts.
4. Include sections for common questions, comparisons, and practical steps.
5. Add subtopics not covered by competitors if relevant.
6. Provide a final summary.

{length_instruction}
{content_instructions}

Format:

**Meta Title Recommendation:**
Your recommendation

---

**Meta Description Recommendation:**
Your recommendation

---

**H1 Tag Recommendation:**
Your recommendation

---

**Content Outline:**

**H2: Heading Title**
- **Content Guidance:** [Content or guidance]

(Repeat for all headings)

---

**Final Summary**
Your summary
---
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Provide detailed SEO content recommendations based on the analysis and snippets."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )

        output = response.choices[0].message.content
        return output
    except Exception as e:
        st.error(f"Error generating optimized structure: {str(e)}")
        return None

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
        if line.startswith('**Meta Title Recommendation:**'):
            doc.add_heading('Meta Title Recommendation', level=4)
        elif line.startswith('**Meta Description Recommendation:**'):
            doc.add_heading('Meta Description Recommendation', level=4)
        elif line.startswith('**H1 Tag Recommendation:**'):
            doc.add_heading('H1 Tag Recommendation', level=4)
        elif line.startswith('**Content Outline:**'):
            doc.add_heading('Content Outline', level=1)
        elif line.startswith('**Final Summary**'):
            doc.add_heading('Final Summary', level=1)
        elif line.startswith('**H2:'):
            heading_text = line.replace('**H2:', '').replace('**', '').strip()
            doc.add_heading(f"H2: {heading_text}", level=2)
        elif line.startswith('**H3:'):
            heading_text = line.replace('**H3:', '').replace('**', '').strip()
            doc.add_heading(f"H3: {heading_text}", level=3)
        elif line.startswith('**H4:'):
            heading_text = line.replace('**H4:', '').replace('**', '').strip()
            doc.add_heading(f"H4: {heading_text}", level=4)
        elif line.startswith('- **Content Guidance:**'):
            content_guidance = line.replace('- **Content Guidance:**', '').strip()
            doc.add_paragraph(content_guidance)
        elif line == '---':
            continue
        else:
            doc.add_paragraph(line)

    return doc

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
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("Extracting headings from competitor content...")
        all_headings = []
        competitor_meta_info = ''
        relevant_snippets = []  # If you want to use embeddings and similarity search, do so before this step.

        for idx, file in enumerate(uploaded_competitor_files, 1):
            html_content = file.read().decode('utf-8')
            meta_title, meta_description, headings = extract_headings_from_html(html_content)
            all_headings.append(headings)

            competitor_meta_info += f"Competitor #{idx} Meta Title: {meta_title}\n"
            competitor_meta_info += f"Competitor #{idx} Meta Description: {meta_description}\n"
            competitor_headings_str = ''
            for level in ["h1", "h2", "h3", "h4"]:
                for heading in headings[level]:
                    competitor_headings_str += f"{level.upper()}: {heading}\n"
            competitor_meta_info += f"Competitor #{idx} Headings:\n{competitor_headings_str}\n\n"

        progress_bar.progress(33)
        status_text.text("Analyzing headings...")

        heading_analysis = analyze_headings(all_headings)

        progress_bar.progress(50)
        status_text.text("Generating optimized content structure...")

        optimized_structure = generate_optimized_structure(keyword, heading_analysis, competitor_meta_info, openai_api_key, content_mode, article_length, relevant_snippets)

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
