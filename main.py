import streamlit as st
from bs4 import BeautifulSoup
from collections import Counter
from docx import Document
from docx.shared import Pt
from io import BytesIO
import numpy as np
import openai

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

**Note:**  
- The model cannot measure words exactly. It will try to meet or exceed the target word count.  
- In "Full Content" mode, produce **final, ready-to-publish paragraphs**. Avoid phrases like "This section will discuss...". Just present the information directly and in a completed form.
- Write as if the article is fully complete and published, providing all details directly.
""")

if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

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

def get_embedding(text, model="text-embedding-ada-002"):
    response = openai.Embedding.create(
        input=[text],
        model=model
    )
    return np.array(response['data'][0]['embedding'], dtype=np.float32)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a)*np.linalg.norm(b))

def generate_semantic_insights(keyword, all_headings):
    competitor_headings = []
    for h_set in all_headings:
        competitor_headings.extend(h_set["h2"])
        competitor_headings.extend(h_set["h3"])
        competitor_headings.extend(h_set["h4"])

    if not competitor_headings:
        return "No additional semantic insights available."

    keyword_emb = get_embedding(keyword)

    heading_embeddings = []
    for ch in competitor_headings:
        emb = get_embedding(ch)
        heading_embeddings.append((ch, emb))

    scored = []
    for ch, emb in heading_embeddings:
        score = cosine_similarity(keyword_emb, emb)
        scored.append((ch, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_headings = [x[0] for x in scored[:5]]

    summary = "Based on competitor headings related to your keyword, consider these topically relevant areas:\n"
    for th in top_headings:
        summary += f"- {th}\n"

    summary += "\nThese headings suggest key areas of interest for your article."
    return summary.strip()

def generate_body_insights(keyword, all_paragraphs):
    competitor_paragraphs = [p for plist in all_paragraphs for p in plist if len(p.split()) > 5]

    if not competitor_paragraphs:
        return "No additional body insights available."

    keyword_emb = get_embedding(keyword)
    paragraph_embeddings = []
    for para in competitor_paragraphs:
        emb = get_embedding(para)
        paragraph_embeddings.append((para, emb))

    scored = []
    for para, emb in paragraph_embeddings:
        score = cosine_similarity(keyword_emb, emb)
        scored.append((para, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    top_paras = [x[0] for x in scored[:5]]

    insights = "Competitor Body Insights (relevant paragraphs):\n"
    for i, tp in enumerate(top_paras, 1):
        insights += f"\nParagraph {i}:\n{tp}\n"
    return insights.strip()

def generate_optimized_structure_with_insights(keyword, heading_analysis, competitor_meta_info, api_key, content_mode, article_length, all_headings, all_paragraphs):
    openai.api_key = api_key

    # Adjust heading counts and paragraph instructions as needed
    if article_length == "Short":
        word_count_range = "around 750 words"
        paragraph_guidance = """
- Aim for 8-10 total headings.
- For Full Content: ~2 paragraphs (~100 words each) per H2. H3/H4 get ~75 words each.
- Do not write about what you 'will' discuss, just present the information directly.
"""
    elif article_length == "Medium":
        word_count_range = "approximately 1250-1500 words"
        paragraph_guidance = """
- Aim for 15-18 total headings.
- For Full Content: Each H2 ~2-3 paragraphs (~100 words each). H3/H4 ~100 words each.
- Include sufficient headings and subheadings to reach ~1250-1500 words.
- Do not say 'this section will discuss'; present the content as final text.
"""
    else:  # Long
        word_count_range = "approximately 1500-3000 words"
        paragraph_guidance = """
- Aim for 20-25 total headings.
- For Full Content: Each H2 ~3 paragraphs (~100 words each). Use multiple H3/H4 subheadings (each ~100 words).
- If unsure, add more detail to exceed 1500 words.
- Avoid future-tense placeholders. Present all content as if final.
"""

    semantic_insights = generate_semantic_insights(keyword, all_headings)
    body_insights = generate_body_insights(keyword, all_paragraphs)

    # Add explicit instructions to avoid placeholder language
    prompt = f"""
You are an SEO content strategist.

Your task:
- Create an optimized content structure for an article targeting "{keyword}".
- "Full Content" mode: fully written paragraphs (no placeholders like "this section will..."). Present final, ready-to-publish text.
- "Outline" mode: 1-2 sentence guidance per heading.

**Competitor Meta and Headings**:
{competitor_meta_info}

**Competitor Semantic Insights (from headings)**:
{semantic_insights}

**Competitor Body Insights (from paragraphs)**:
{body_insights}

Instructions:
1. Provide meta title, meta description, and H1.
2. Produce heading structure (H2/H3/H4) covering all subtopics.
3. Ensure logical flow, comprehensive coverage.
4. Include a final summary.
5. Word count target: {word_count_range}
{paragraph_guidance}

Additional Important Instructions:
- In Full Content mode, write as if the article is final and already published.
- Do NOT say "this section will discuss". Instead, directly provide the information.
- Expand on details thoroughly. If needed, err on writing more content.
- Provide actual facts, descriptions, and explanations directly under each heading.

**Formatting:**
- `**H2: Heading Title**`
- `**H3: Subheading Title**`, `**H4: Sub-subheading Title**`
- Full Content mode: full paragraphs, final text.
- Outline mode: brief guidance.

Example (Full Content mode):
**H2: Example Heading**
Write full paragraphs here, describing the topic as if final.

---

**Final Summary**
Final concluding paragraphs, fully written.

No placeholders or references to “this section” or “we will discuss”.

"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful SEO content strategist. Produce fully written, ready-to-publish content in Full Content mode. Avoid placeholders."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=7000
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
        elif line == '---':
            continue
        else:
            paragraph = doc.add_paragraph(line)
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)

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
