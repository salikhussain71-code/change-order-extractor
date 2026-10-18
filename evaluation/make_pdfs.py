"""Generate the synthetic sample PDFs in data/. Run: python evaluation/make_pdfs.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

DATA = Path(__file__).resolve().parent.parent / "data"

DIGITAL = {
    "co_011.pdf": [
        "CHANGE ORDER NO. 058", "Project: Westgate Community Center", "Date: November 12, 2025",
        "Contractor: Ironwood Structural Inc.", "",
        "Description: Add steel beam at gym roof opening per RFI-087.", "",
        "Total Amount: $31,640.00", "Schedule Impact: 7 calendar days", "Status: Approved",
    ],
    "co_012.pdf": [
        "CHANGE ORDER #CO-3", "Project Name: Elm Street Duplex", "Date: 02/20/2026",
        "Contractor: Bluebird Painting", "",
        "Description: Deduct interior paint at unit B; owner will paint.", "",
        "Credit: ($2,150.00)", "Schedule Impact: None", "Pending owner approval",
    ],
}

for name, lines in DIGITAL.items():
    c = canvas.Canvas(str(DATA / name), pagesize=letter)
    y = 740
    for ln in lines:
        c.setFont("Helvetica", 12)
        c.drawString(72, y, ln)
        y -= 20
    c.save()

# Scanned-style PDF: text is drawn into an IMAGE, so there is no text layer.
img = Image.new("RGB", (850, 500), "white")
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("DejaVuSans.ttf", 22)
except OSError:
    font = ImageFont.load_default()
for i, ln in enumerate(["CHANGE ORDER NO. 77", "Project: Scanned Warehouse", "Total Amount: $9,999.00"]):
    d.text((50, 50 + i * 40), ln, fill="black", font=font)
img.save(DATA / "co_013_scanned.pdf", "PDF", resolution=100)
print("PDFs written to", DATA)
