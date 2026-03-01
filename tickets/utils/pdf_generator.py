from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import qrcode


def draw_tickets_to_buffer(tickets_data):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    for data in tickets_data:
        p.setFont("Helvetica-Bold", 20)
        p.drawString(100, 800, f"BILET: {data['event_name']}")
        p.drawString(100, 770, f"Uczestnik: {data['name']}")

        qr = qrcode.make(data['uuid'])
        p.drawInlineImage(qr, 400, 650, width=150, height=150)

        p.showPage()

    p.save()
    return buffer