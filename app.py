import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from googletrans import Translator, LANGUAGES
from pdf2image import convert_from_bytes
import io, textwrap, html, os
import arabic_reshaper
from bidi.algorithm import get_display

# PDF Imports
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4

# -------- CONFIGURATION --------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler-25.12.0\Library\bin"

# Ensure these files exist in your project folder
FONT_MAPPING = {
    "ta": "NotoSansTamil-Regular.ttf",
    "ar": "NotoSansArabic-Regular.ttf",
    "hi": "NotoSans-Regular.ttf",
    "default": "arial.ttf" # Use a standard system font as default
}

translator = Translator()

# -------- UTILITIES --------
def fix_rendering(text, lang_code):
    """Handles Arabic shaping and RTL logic."""
    if not text: return ""
    if lang_code == "ar":
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    return text

def get_ocr_langs(target_code):
    """Combines English with the target language for better OCR."""
    base = "eng"
    if target_code == "ta": base += "+tam"
    elif target_code == "ar": base += "+ara"
    elif target_code == "hi": base += "+hin"
    return base

# -------- UI --------
st.set_page_config(page_title="Universal Translator", layout="wide")
st.title("🌍 Universal Multi-Language Translator")

available_langs = {name.title(): code for code, name in LANGUAGES.items()}
target_lang_name = st.selectbox("Select Target Language", sorted(available_langs.keys()))
target_code = available_langs[target_lang_name]

# Font Registration
active_font_path = FONT_MAPPING.get(target_code, FONT_MAPPING["default"])
HAS_FONT = False
if os.path.exists(active_font_path):
    try:
        pdfmetrics.registerFont(TTFont('DynamicFont', active_font_path))
        HAS_FONT = True
    except: pass

# -------- PROCESSING --------
uploaded_file = st.file_uploader("Upload Image or PDF", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file:
    with st.spinner("Processing..."):
        # Load File
        if "image" in uploaded_file.type:
            input_images = [Image.open(uploaded_file)]
        else:
            input_images = convert_from_bytes(uploaded_file.read(), poppler_path=POPPLER_PATH)

        # PDF Setup
        pdf_io = io.BytesIO()
        doc = SimpleDocTemplate(pdf_io, pagesize=A4)
        styles = getSampleStyleSheet()
        style = styles["Normal"]
        if HAS_FONT: style.fontName = 'DynamicFont'
        style.leading = 25
        if target_code == "ar": style.alignment = 2
        
        story = []
        translated_images = []

        for i, img in enumerate(input_images):
            # 1. OCR (Read)
            raw_text = pytesseract.image_to_string(img, lang=get_ocr_langs(target_code))
            
            # 2. Translate
            translated_text = translator.translate(raw_text, dest=target_code).text
            
            # 3. Fix Script (Arabic/Tamil Shaping)
            display_text = fix_rendering(translated_text, target_code)

            # 4. Prepare Image Output
            draw_img = img.convert("RGB")
            try:
                # Use loaded font or fallback to default
                font = ImageFont.truetype(active_font_path, 30) if os.path.exists(active_font_path) else ImageFont.load_default()
            except:
                font = ImageFont.load_default()
                
            draw = ImageDraw.Draw(draw_img)
            wrapped = textwrap.fill(display_text, width=40)
            
            # Add white header for translated text on image
            bbox = draw.textbbox((0, 0), wrapped, font=font)
            h = (bbox[3] - bbox[1]) + 60
            final_img = Image.new('RGB', (img.width, img.height + h), (255, 255, 255))
            final_img.paste(draw_img, (0, h))
            ImageDraw.Draw(final_img).text((20, 20), wrapped, fill="black", font=font)
            translated_images.append(final_img)

            # 5. Prepare PDF Story
            clean_text = html.escape(display_text).replace("\n", "<br/>")
            story.append(Paragraph(f"<b>Page {i+1}</b>", style))
            story.append(Spacer(1, 12))
            story.append(Paragraph(clean_text, style))
            story.append(Spacer(1, 30))

        # Show Results
        st.image(translated_images[0], caption="Translated Preview")
        
        doc.build(story)
        st.download_button("📩 Download Translated PDF", pdf_io.getvalue(), "translated.pdf")
