import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from deep_translator import GoogleTranslator
from pdf2image import convert_from_bytes
import io, textwrap, html, os
import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4

# ---------------- LANGUAGES ----------------

LANGUAGES = {
    "English": "en",
    "Tamil": "ta",
    "Hindi": "hi",
    "Arabic": "ar",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Chinese": "zh-cn",
    "Japanese": "ja",
    "Korean": "ko"
}

# ---------------- FONT MAPPING ----------------

FONT_MAPPING = {
    "ta": "NotoSansTamil-Regular.ttf",
    "ar": "NotoSansArabic-Regular.ttf",
    "hi": "NotoSansDevanagari-Regular.ttf",
    "default": "NotoSans-Regular.ttf"
}

# ---------------- UTILITIES ----------------

def fix_rendering(text, lang_code):
    """Fix Arabic RTL rendering."""
    if not text:
        return ""

    if lang_code == "ar":
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)

    return text


def get_ocr_langs(target_code):
    """Better OCR detection."""
    base = "eng"

    if target_code == "ta":
        base += "+tam"
    elif target_code == "ar":
        base += "+ara"
    elif target_code == "hi":
        base += "+hin"

    return base


def draw_text_on_image(img, text, font_path):
    """Draw translated text above the image."""

    draw_img = img.convert("RGB")

    try:
        font = ImageFont.truetype(font_path, 32)
    except:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(draw_img)

    wrapped = textwrap.fill(text, width=40)

    bbox = draw.textbbox((0, 0), wrapped, font=font)
    h = (bbox[3] - bbox[1]) + 60

    final_img = Image.new("RGB", (img.width, img.height + h), (255, 255, 255))
    final_img.paste(draw_img, (0, h))

    draw2 = ImageDraw.Draw(final_img)
    draw2.text((20, 20), wrapped, fill="black", font=font)

    return final_img


# ---------------- STREAMLIT UI ----------------

st.set_page_config(page_title="AI Translator App", layout="wide")

st.title("🌍 AI Image & PDF Translator")
st.write("Upload an **Image or PDF** and translate the detected text.")

target_lang_name = st.selectbox(
    "Select Target Language",
    list(LANGUAGES.keys())
)

target_code = LANGUAGES[target_lang_name]

# ---------------- FONT SETUP ----------------

active_font_path = FONT_MAPPING.get(target_code, FONT_MAPPING["default"])

HAS_FONT = False

if os.path.exists(active_font_path):
    try:
        pdfmetrics.registerFont(TTFont("DynamicFont", active_font_path))
        HAS_FONT = True
    except:
        pass

# ---------------- FILE UPLOAD ----------------

uploaded_file = st.file_uploader(
    "Upload Image or PDF",
    type=["png", "jpg", "jpeg", "pdf"]
)

if uploaded_file:

    with st.spinner("Processing..."):

        # -------- LOAD FILE --------

        if "image" in uploaded_file.type:
            input_images = [Image.open(uploaded_file)]

        elif "pdf" in uploaded_file.type:
            try:
                input_images = convert_from_bytes(
                    uploaded_file.read(),
                    fmt="png"
                )
            except:
                st.error("❌ PDF processing failed. Please upload an image instead.")
                st.stop()

        # -------- PDF OUTPUT SETUP --------

        pdf_io = io.BytesIO()

        doc = SimpleDocTemplate(pdf_io, pagesize=A4)

        styles = getSampleStyleSheet()

        style = styles["Normal"]

        if HAS_FONT:
            style.fontName = "DynamicFont"

        style.leading = 25

        if target_code == "ar":
            style.alignment = 2

        story = []

        translated_images = []

        # -------- PROCESS PAGES --------

        for i, img in enumerate(input_images):

            raw_text = pytesseract.image_to_string(
                img,
                lang=get_ocr_langs(target_code)
            )

            translated_text = GoogleTranslator(
                source="auto",
                target=target_code
            ).translate(raw_text)

            display_text = fix_rendering(translated_text, target_code)

            result_img = draw_text_on_image(
                img,
                display_text,
                active_font_path
            )

            translated_images.append(result_img)

            clean_text = html.escape(display_text).replace("\n", "<br/>")

            story.append(Paragraph(f"<b>Page {i+1}</b>", style))
            story.append(Spacer(1, 12))
            story.append(Paragraph(clean_text, style))
            story.append(Spacer(1, 30))

        # -------- SHOW PREVIEW --------

        st.image(translated_images[0], caption="Translated Preview")

        # -------- BUILD PDF --------

        doc.build(story)

        st.download_button(
            "📄 Download Translated PDF",
            pdf_io.getvalue(),
            "translated.pdf"
        )
