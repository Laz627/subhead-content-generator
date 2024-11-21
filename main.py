import streamlit as st
from bs4 import BeautifulSoup
from collections import Counter
from openai import OpenAI
from docx import Document
from docx.shared import Pt
from docx.enum.style import WD_STYLE_TYPE
from io import BytesIO

# Set page config
st.set_page_config(page_title="SEO Content Outline Generator", layout="wide")
st.title("SEO Content Outline Generator")

# Instructions
st.markdown("""
## How to use this tool:
1. **Enter your OpenAI API key** in the field below.
2. **Input your target keyword.**
3. **Upload competitor HTML files** for comparison.
4. Click **'Generate Content Outline'** to analyze competitor content and create an optimized content structure.
5. Review the extracted subheads from the competitor content and the AI-generated optimized outline.
6. **Download the content brief** as a Word document.

This tool helps content creators and SEO professionals generate comprehensive, SEO-optimized content outlines based on competitor content for any given keyword.
""")

# Initialize session state
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ''
if 'keyword' not in st.session_state:
    st.session_state.keyword = ''

def extract_headings_from_html(html_content):
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove navigation and footer elements
        tags_to_remove = ['script', 'style', 'noscript', 'header', 'footer', 'nav', 'aside']
        for tag in tags_to_remove:
            for element in soup.find_all(tag):
                element.decompose()

        # Remove elements by common class and ID names
        classes_ids_to_remove = ['nav', 'navigation', 'sidebar', 'footer', 'header', 'menu',
                                 'breadcrumbs', 'breadcrumb', 'site-footer', 'site-header',
                                 'widget', 'widgets', 'site-navigation', 'main-navigation',
                                 'secondary-navigation', 'site-sidebar']
        for class_or_id in classes_ids_to_remove:
            for element in soup.find_all(attrs={'class': class_or_id}):
                element.decompose()
            for element in soup.find_all(attrs={'id': class_or_id}):
                element.decompose()

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
            "h1": [h.get_text(separator=' ', strip=True) for h in content_to_search.find_all("h1") if h.get_text(strip=True)],
            "h2": [h.get_text(separator=' ', strip=True) for h in content_to_search.find_all("h2") if h.get_text(strip=True)],
            "h3": [h.get_text(separator=' ', strip=True) for h in content_to_search.find_all("h3") if h.get_text(strip=True)],
            "h4": [h.get_text(separator=' ', strip=True) for h in content_to_search.find_all("h4") if h.get_text(strip=True)]
        }

        # Extract meta title and description
        meta_title = soup.title.string.strip() if soup.title else ''
        meta_description_tag = soup.find('meta', attrs={'name': 'description'})
        meta_description = meta_description_tag['content'].strip() if meta_description_tag else ''

        return meta_title, meta_description, headings
    except Exception as e:
        st.warning(f"Error extracting headings: {str(e)}")
        return '', '', {"h1": [], "h2": [], "h3": [], "h4": []}

def analyze_headings(all_headings):
    analysis = {}
    for level in ["h1", "h2", "h3", "h4"]:
        headings = [h for url_headings in all_headings for h in url_headings[level]]
        analysis[level] = {
            "count": len(headings),
            "avg_length": sum(len(h) for h in headings) / len(headings) if headings else 0,
            "common_words": Counter(" ".join(headings).lower().split()).most_common(10),
            "examples": headings[:10]  # Include up to 10 example headings
        }
    return analysis

def generate_optimized_structure(keyword, heading_analysis, competitor_meta_info, api_key):
    client = OpenAI(api_key=api_key)

    prompt = f"""
You are an SEO content strategist.

Your task is to analyze the provided competitor headings and meta information to generate specific, actionable recommendations for creating a new, optimized content outline.

- **Keyword**: "{keyword}"

- **Competitor Meta Information and Headings**:
{competitor_meta_info}

Instructions:

1. Based on the competitor data, recommend an optimized meta title, meta description, and H1 tag for a new page targeting the keyword.
2. Generate an optimized heading structure (H2s, H3s, H4s) for the new page, ensuring it covers all important topics and subtopics.
3. Ensure the structure flows cohesively, focusing on what users should know about the topic.
4. Avoid using branded subheads unless absolutely necessary for the topic.
5. Include brief directions on what content should be included under each heading.
6. Organize the content in a way that naturally progresses from basic concepts to more advanced ideas.
7. Include sections that address common questions or concerns related to the topic.
8. Where applicable, include comparisons with alternatives or related concepts.
9. Consider including a section on practical application or next steps for the reader.
10. Ensure the outline covers the topic thoroughly while remaining focused and relevant to the main keyword.

IMPORTANT: Use markdown syntax for bold text and headings. Present the recommendations in a clear, structured format using markdown.

Format:

**Meta Title Recommendation:**

Your recommendation here

---

**Meta Description Recommendation:**

Your recommendation here

---

**H1 Tag Recommendation:**

Your recommendation here

---

**Content Outline:**

For each heading:

---

**[Heading Level and Title]**

- **Content Guidance:** Brief description of what to include under this heading

---

Ensure that the headings are properly formatted using markdown (e.g., `**H2: Heading Title**`).

"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Provide detailed SEO content recommendations based on the analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        output = response.choices[0].message.content
        return output
    except Exception as e:
        st.error(f"Error generating optimized structure: {str(e)}")
        return None

def create_word_document(keyword, optimized_structure):
    if not optimized_structure:
        st.error("No content to create document. Please try again.")
        return None

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
    lines = optimized_structure.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('**Meta Title Recommendation:**'):
            doc.add_heading('Meta Title Recommendation', level=1)
        elif line.startswith('**Meta Description Recommendation:**'):
            doc.add_heading('Meta Description Recommendation', level=1)
        elif line.startswith('**H1 Tag Recommendation:**'):
            doc.add_heading('H1 Tag Recommendation', level=1)
        elif line.startswith('**Content Outline:**'):
            doc.add_heading('Content Outline', level=1)
        elif line.startswith('**H2:'):
            heading_text = line.replace('**H2:', '').replace('**', '').strip()
            doc.add_heading(heading_text, level=2)
        elif line.startswith('**H3:'):
            heading_text = line.replace('**H3:', '').replace('**', '').strip()
            doc.add_heading(heading_text, level=3)
        elif line.startswith('**H4:'):
            heading_text = line.replace('**H4:', '').replace('**', '').strip()
            doc.add_heading(heading_text, level=4)
        elif line.startswith('- **Content Guidance:**'):
            content_guidance = line.replace('- **Content Guidance:**', '').strip()
            doc.add_paragraph(content_guidance)
        elif line == '---':
            continue
        else:
            doc.add_paragraph(line)

    return doc

# Streamlit UI
st.write("Enter your API key and target keyword below:")

openai_api_key = st.text_input("OpenAI API key:", value=st.session_state.openai_api_key, type="password")
keyword = st.text_input("Target keyword:", value=st.session_state.keyword)

# Update session state
st.session_state.openai_api_key = openai_api_key
st.session_state.keyword = keyword

# File uploader for competitor HTML files
uploaded_competitor_files = st.file_uploader(
    "Upload competitor HTML files (you can select multiple files):",
    type=['html', 'htm'],
    accept_multiple_files=True
)

if st.button("Generate Content Outline"):
    if openai_api_key and keyword and uploaded_competitor_files:
        with st.spinner("Analyzing competitor content..."):
            all_headings = []
            competitor_meta_info = ''
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

            # Display extracted subheads
            st.subheader("Extracted Subheads from Competitor Content:")
            for idx, headings in enumerate(all_headings, 1):
                st.write(f"Competitor #{idx}:")
                for level in ["h1", "h2", "h3", "h4"]:
                    if headings[level]:
                        st.write(f"{level.upper()}:")
                        for heading in headings[level]:
                            st.write(f"- {heading}")
                st.write("---")

            heading_analysis = analyze_headings(all_headings)

            with st.spinner("Generating optimized content structure..."):
                optimized_structure = generate_optimized_structure(keyword, heading_analysis, competitor_meta_info, openai_api_key)
                if optimized_structure:
                    st.subheader("Optimized Content Structure:")
                    st.markdown(optimized_structure)

                    # Create and offer Word document download
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
                    st.error("Failed to generate optimized structure. Please try again.")
    else:
        st.error("Please enter your OpenAI API key, target keyword, and upload competitor HTML files to proceed.")
