from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.travel import Itinerary, Place


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\u2192", "->").replace("\u2014", "-").strip()


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_clean(text)).replace("\n", "<br/>"), style)


def _map_url(stop: Place) -> str:
    return (
        stop.google_maps_url
        or stop.map_url
        or f"https://www.google.com/maps/search/?api=1&query={stop.latitude},{stop.longitude}"
    )


def _source_text(stop: Place) -> str:
    if stop.source_url:
        return f"{stop.source_title or stop.source_type}: {stop.source_url}"
    if stop.source_title:
        return stop.source_title
    return "No source link stored."


def _stop_table(stop: Place, index: int, styles: dict[str, ParagraphStyle]) -> Table:
    rating = (
        f"{stop.google_rating:.1f} ({stop.google_user_rating_count} reviews)"
        if stop.google_rating and stop.google_user_rating_count
        else "Not available"
    )
    price = stop.price_label or stop.google_price_label or "Not available"
    rows = [
        [
            _paragraph(f"{index}. {stop.name}", styles["StopTitle"]),
            _paragraph(stop.category, styles["Meta"]),
        ],
        [
            _paragraph("Area", styles["Label"]),
            _paragraph(stop.neighborhood or stop.city, styles["Body"]),
        ],
        [
            _paragraph("Best time", styles["Label"]),
            _paragraph(stop.best_time or "Flexible", styles["Body"]),
        ],
        [
            _paragraph("Opening hours", styles["Label"]),
            _paragraph(stop.open_status_label or "Not available", styles["Body"]),
        ],
        [
            _paragraph("Rating / price", styles["Label"]),
            _paragraph(f"{rating} / {price}", styles["Body"]),
        ],
        [
            _paragraph("Why", styles["Label"]),
            _paragraph(stop.reason, styles["Body"]),
        ],
        [
            _paragraph("Local tip", styles["Label"]),
            _paragraph(stop.local_tip, styles["Body"]),
        ],
        [
            _paragraph("Map", styles["Label"]),
            _paragraph(_map_url(stop), styles["Link"]),
        ],
        [
            _paragraph("Source", styles["Label"]),
            _paragraph(_source_text(stop), styles["Link"]),
        ],
    ]
    table = Table(rows, colWidths=[34 * mm, 126 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFF1D8")),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#EADFE7")),
                ("INNERGRID", (0, 1), (-1, -1), 0.35, colors.HexColor("#F0E5ED")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#7C7081"))
    canvas.drawString(20 * mm, 12 * mm, "TravelBuddy France itinerary")
    canvas.drawRightString(
        A4[0] - 20 * mm,
        12 * mm,
        f"Page {document.page}",
    )
    canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#22313C"),
            spaceAfter=8,
        ),
        "Section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#BF567D"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "Day": ParagraphStyle(
            "Day",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=colors.HexColor("#3D5961"),
            spaceBefore=10,
            spaceAfter=5,
        ),
        "StopTitle": ParagraphStyle(
            "StopTitle",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor("#25313B"),
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=12,
            textColor=colors.HexColor("#25313B"),
        ),
        "Meta": ParagraphStyle(
            "Meta",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#7C7081"),
        ),
        "Label": ParagraphStyle(
            "Label",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.8,
            leading=11,
            textColor=colors.HexColor("#7C7081"),
        ),
        "Link": ParagraphStyle(
            "Link",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#476782"),
            wordWrap="CJK",
        ),
    }


def build_itinerary_pdf(itinerary: Itinerary) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=itinerary.title,
    )
    styles = _styles()
    story = [
        _paragraph(itinerary.title, styles["Title"]),
        _paragraph(f"Destination: {itinerary.destination}", styles["Meta"]),
        Spacer(1, 4 * mm),
        _paragraph("Summary", styles["Section"]),
        _paragraph(itinerary.summary, styles["Body"]),
        Spacer(1, 3 * mm),
        _paragraph("Themes", styles["Section"]),
        _paragraph(", ".join(itinerary.themes), styles["Body"]),
    ]

    day_sections = itinerary.days or [
        type("ItineraryDayFallback", (), {
            "day": 1,
            "title": "Recommended Stops",
            "summary": "",
            "stops": itinerary.stops,
        })()
    ]

    for day_index, day in enumerate(day_sections):
        if day_index:
            story.append(PageBreak())
        story.append(_paragraph(day.title or f"Day {day.day}", styles["Day"]))
        if day.summary:
            story.append(_paragraph(day.summary, styles["Body"]))
            story.append(Spacer(1, 3 * mm))

        for stop_index, stop in enumerate(day.stops, start=1):
            story.append(_stop_table(stop, stop_index, styles))
            story.append(Spacer(1, 4 * mm))

    if itinerary.avoidance_notes or itinerary.practical_notes:
        story.append(_paragraph("Notes", styles["Section"]))
        for note in [*itinerary.avoidance_notes, *itinerary.practical_notes]:
            story.append(_paragraph(f"- {note}", styles["Body"]))

    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer.read()
