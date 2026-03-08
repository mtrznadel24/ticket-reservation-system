from io import BytesIO

from django.conf import settings
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import qrcode


def draw_tickets_to_buffer(tickets_data):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    tickets_per_page = 4
    ticket_height = page_height / tickets_per_page

    for index, data in enumerate(tickets_data):
        pos_on_page = index % tickets_per_page

        if pos_on_page == 0 and index > 0:
            p.showPage()

        top_y = page_height - (pos_on_page * ticket_height)
        bottom_y = top_y - ticket_height

        margin_x = 40
        margin_y = 15

        box_x = margin_x
        box_y = bottom_y + margin_y
        box_w = page_width - (2 * margin_x)
        box_h = ticket_height - (2 * margin_y)

        p.setLineWidth(1.5)
        p.setStrokeColor(HexColor("#2C3E50"))
        p.setFillColor(HexColor("#F8F9FA"))
        p.roundRect(box_x, box_y, box_w, box_h, radius=10, fill=1, stroke=1)

        p.setDash(6, 4)
        p.setStrokeColor(HexColor("#BDC3C7"))
        line_x = box_x + box_w - 140
        p.line(line_x, box_y, line_x, box_y + box_h)
        p.setDash()

        p.setFillColor(HexColor("#000000"))

        p.setFont("Helvetica-Bold", 16)
        p.drawString(box_x + 20, box_y + box_h - 35, f"EVENT: {data['event_name']}")

        p.setFont("Helvetica", 12)
        p.drawString(box_x + 20, box_y + box_h - 60, f"PARTICIPANT: {data['name']}")

        if data.get("has_numbered_seats"):
            p.setFont("Helvetica-Bold", 12)
            p.setFillColor(HexColor("#E74C3C"))
            p.drawString(box_x + 20, box_y + box_h - 80, f"SECTOR: {data['sector']}   |   ROW: {data['row']}")

            p.setFont("Helvetica-Bold", 14)
            p.drawString(box_x + 20, box_y + box_h - 100, f"SEAT: {data['seat']}")

        p.setFillColor(HexColor("#7F8C8D"))
        p.setFont("Helvetica-Oblique", 8)
        p.drawString(box_x + 20, box_y + 15, f"ID: {data['uuid']}")

        qr_url = f"{settings.SITE_URL}/scan/{data['uuid']}/"
        qr = qrcode.make(qr_url)
        qr_size = 100
        qr_x = box_x + box_w - 120
        qr_y = box_y + (box_h - qr_size) / 2

        p.drawInlineImage(qr, qr_x, qr_y, width=qr_size, height=qr_size)

    p.showPage()
    p.save()

    return buffer