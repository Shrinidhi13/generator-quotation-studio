"""Customer-facing A4 quotation design; pricing is supplied only by domain.py."""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Image,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)
from catalog import CATALOG
from domain import calculate_option, money, validate_quote
from equipment_features import LEGACY_FEATURES, TWIN_500_FEATURES

ASSETS = Path(__file__).resolve().parent / "assets"
NAVY, RED = colors.HexColor("#202A30"), colors.HexColor("#C72B35")
INK, MUTED = colors.HexColor("#2C3439"), colors.HexColor("#5B6264")
PALE, WARM, LINE = [colors.HexColor(c) for c in ("#F4F5F3", "#F5F1E8", "#DFE2DE")]
WHITE = colors.white
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 42
CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2
TEMPLATE_VERSION = "customer-2026-10-v6.1-multiline-address"


def _register_fonts():
    for name, filename in {
        "QuoteBody": "Manrope-Regular.ttf",
        "QuoteBody-Bold": "Manrope-Semibold.ttf",
        "QuoteDisplay": "SpaceGrotesk-Medium.ttf",
        "QuoteDisplay-Bold": "SpaceGrotesk-Bold.ttf",
    }.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(ASSETS / "fonts" / filename)))
    pdfmetrics.registerFontFamily(
        "QuoteBody",
        normal="QuoteBody",
        bold="QuoteBody-Bold",
        italic="QuoteBody",
        boldItalic="QuoteBody-Bold",
    )


def _styles():
    _register_fonts()
    common = dict(fontName="QuoteBody", textColor=INK, splitLongWords=True)

    def style(name, size, leading, **extra):
        return ParagraphStyle(name, fontSize=size, leading=leading, **(common | extra))

    return {
        "body": style("Body", 10, 14.2, spaceAfter=5),
        "small": style("Small", 8.6, 12, spaceAfter=4),
        "tiny": style("Tiny", 7.5, 10.2, textColor=MUTED),
        "eyebrow": style(
            "Eyebrow", 8, 11, fontName="QuoteBody-Bold", textColor=RED, spaceAfter=5
        ),
        "title": style(
            "Title", 30, 35, fontName="QuoteDisplay-Bold", textColor=NAVY, spaceAfter=7
        ),
        "customer": style(
            "Customer",
            14,
            18,
            fontName="QuoteDisplay-Bold",
            textColor=NAVY,
            spaceAfter=4,
        ),
        "capacity": style(
            "Capacity",
            31,
            35,
            fontName="QuoteDisplay-Bold",
            textColor=NAVY,
            spaceAfter=7,
        ),
        "section": style(
            "Section",
            17,
            22,
            fontName="QuoteBody-Bold",
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=9,
            keepWithNext=True,
        ),
        "subheading": style(
            "Subheading",
            11,
            15,
            fontName="QuoteBody-Bold",
            textColor=NAVY,
            spaceBefore=5,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "table": style("Table", 8.6, 12),
        "table_head": style(
            "TableHead", 7.5, 10.5, fontName="QuoteBody-Bold", textColor=NAVY
        ),
        "number": style("Number", 8.6, 12, alignment=TA_RIGHT),
        "number_head": style(
            "NumberHead",
            7.5,
            10.5,
            alignment=TA_RIGHT,
            fontName="QuoteBody-Bold",
            textColor=NAVY,
        ),
        "total": style(
            "Total",
            21,
            25,
            alignment=TA_RIGHT,
            fontName="QuoteBody-Bold",
            textColor=WHITE,
        ),
        "band_title": style(
            "BandTitle", 16, 20, fontName="QuoteBody-Bold", textColor=WHITE
        ),
        "band_label": style("BandLabel", 8, 11, textColor=colors.HexColor("#CCD8DF")),
        "band_right_label": style(
            "BandRightLabel",
            8,
            11,
            textColor=colors.HexColor("#CCD8DF"),
            alignment=TA_RIGHT,
        ),
        "total_dark": style(
            "TotalDark",
            18,
            22,
            alignment=TA_RIGHT,
            fontName="QuoteBody-Bold",
            textColor=NAVY,
        ),
        "terms": style("Terms", 9.5, 13.6),
        "term_label": style(
            "TermLabel", 9.8, 13.6, fontName="QuoteBody-Bold", textColor=NAVY
        ),
    }


def _text(value):
    text = "" if value is None else str(value)
    for old, new in {
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u20b9": "INR ",
    }.items():
        text = text.replace(old, new)
    return "".join(c for c in text if c in "\n\t" or ord(c) >= 32)


def _escaped(value):
    return escape(_text(value)).replace("\r", "").replace("\n", "<br/>")


def _p(value, style):
    return Paragraph(_escaped(value), style)


def _label(label, value, style):
    return Paragraph(f"<b>{_escaped(label)}</b> {_escaped(value)}", style)


def _date(value):
    return date.fromisoformat(value).strftime("%d %b %Y")


def _capacity(o):
    return o["capacity"].replace("KVA", "kVA")


def _image(name, max_width, max_height):
    path = ASSETS / name
    if not path.is_file():
        return None
    try:
        w, h = ImageReader(str(path)).getSize()
        scale = min(max_width / w, max_height / h)
        im = Image(str(path), width=w * scale, height=h * scale)
        im.hAlign = "CENTER"
        return im
    except (OSError, ValueError):
        return None


def _layout(rows, widths, padding=0, background=None):
    t = LongTable(rows, colWidths=widths, hAlign="LEFT", splitByRow=1, splitInRow=1)
    commands = [("VALIGN", (0, 0), (-1, -1), "TOP")]
    for side in ("LEFT", "RIGHT", "TOP", "BOTTOM"):
        commands.append((side + "PADDING", (0, 0), (-1, -1), padding))
    if background:
        commands.append(("BACKGROUND", (0, 0), (-1, -1), background))
    t.setStyle(TableStyle(commands))
    return t


def _table(rows, widths, padding=7):
    t = LongTable(
        rows, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1, splitInRow=1
    )
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), PALE),
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, NAVY),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
                ("BACKGROUND", (0, 1), (-1, -1), WHITE),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), padding),
                ("RIGHTPADDING", (0, 0), (-1, -1), padding),
                ("TOPPADDING", (0, 0), (-1, -1), padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ]
        )
    )
    return t


def _elide(value, width, font, size):
    text = _text(value).replace("\n", " ")
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    while text and pdfmetrics.stringWidth(text + "...", font, size) > width:
        text = text[:-1]
    return text + "..."


def _page_chrome(q):
    def draw(c, doc):
        c.saveState()
        c.setFillColor(RED)
        c.rect(MARGIN, PAGE_HEIGHT - 12, 34, 3, stroke=0, fill=1)
        if doc.page > 1:
            c.setFont("QuoteBody-Bold", 9)
            c.setFillColor(NAVY)
            c.drawString(
                MARGIN,
                PAGE_HEIGHT - 30,
                _elide(
                    q["seller"]["name"].upper(),
                    CONTENT_WIDTH * 0.53,
                    "QuoteBody-Bold",
                    9,
                ),
            )
            c.setFont("QuoteBody", 8)
            c.setFillColor(MUTED)
            c.drawRightString(
                PAGE_WIDTH - MARGIN,
                PAGE_HEIGHT - 30,
                _elide(q["quote_number"], CONTENT_WIDTH * 0.42, "QuoteBody", 8),
            )
        c.setStrokeColor(LINE)
        c.line(MARGIN, 43, PAGE_WIDTH - MARGIN, 43)
        c.setFillColor(MUTED)
        c.setFont("QuoteBody", 7.5)
        footer = (
            f"{q['quote_number']}   /   R{q['revision']:02d}   /   Lead {q['lead_ref']}"
        )
        c.drawString(MARGIN, 28, _elide(footer, CONTENT_WIDTH - 72, "QuoteBody", 7.5))
        c.setFillColor(NAVY)
        c.setFont("QuoteBody-Bold", 8)
        c.drawRightString(PAGE_WIDTH - MARGIN, 28, f"PAGE {doc.page:02d}")
        c.restoreState()

    return draw


def _cover_line(
    c, text, x, y, width, size=10, font="QuoteBody", color=INK, right=False
):
    """Bound short presentation text; the full values flow in the schedule."""
    c.setFillColor(color)
    c.setFont(font, size)
    value = _elide(text, width, font, size)
    (c.drawRightString if right else c.drawString)(x, y, value)


def _cover_address(c, address):
    """Keep a short postal block intact; full long addresses flow in the schedule."""
    lines = []
    for paragraph in _text(address).splitlines():
        lines.extend(simpleSplit(paragraph, "QuoteBody", 9, CONTENT_WIDTH))
    if len(lines) > 3:
        lines = lines[:2] + [" ".join(lines[2:])]
    for index, line in enumerate(lines):
        _cover_line(c, line, MARGIN, 663 - 12 * index, CONTENT_WIDTH, 9, color=MUTED)


class _ProposalCover(Flowable):
    """A deliberate one-page composition, separate from the flowing detail pages."""

    def __init__(self, quote, height):
        super().__init__()
        self.q = quote
        self.width, self.height = CONTENT_WIDTH, height

    def draw(self):
        c, q = self.canv, self.q
        c.saveState()
        c.resetTransforms()
        c.setFillColor(WARM)
        c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
        c.setFillColor(RED)
        c.rect(MARGIN, 756, 36, 3, fill=1, stroke=0)
        # Masthead uses clean type; the original manufacturer's identity stays on the product.
        _cover_line(
            c,
            q["seller"]["name"].upper(),
            MARGIN,
            797,
            320,
            18,
            "QuoteDisplay-Bold",
            NAVY,
        )
        _cover_line(
            c,
            "AUTHORISED SALES, SERVICE & SPARES",
            MARGIN,
            781,
            320,
            7.1,
            "QuoteBody",
            MUTED,
        )
        _cover_line(
            c,
            "MAHINDRA",
            PAGE_WIDTH - MARGIN,
            798,
            150,
            12,
            "QuoteDisplay-Bold",
            RED,
            True,
        )
        _cover_line(
            c,
            "POWEROL",
            PAGE_WIDTH - MARGIN,
            781,
            150,
            12,
            "QuoteDisplay-Bold",
            NAVY,
            True,
        )
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(MARGIN + 48, 757, PAGE_WIDTH - MARGIN, 757)

        _cover_line(
            c, "GENERATOR QUOTATION", MARGIN, 728, 280, 8, "QuoteBody-Bold", RED
        )
        _cover_line(c, "Prepared for", MARGIN, 704, 310, 8.5, color=MUTED)
        _cover_line(
            c,
            q["customer"]["name"],
            MARGIN,
            681,
            CONTENT_WIDTH,
            20,
            "QuoteDisplay-Bold",
            NAVY,
        )
        _cover_address(c, q["customer"]["address"])
        until = date.fromisoformat(q["date"]) + timedelta(days=q["valid_days"])
        _cover_line(
            c,
            q["quote_number"],
            PAGE_WIDTH - MARGIN,
            729,
            213,
            8,
            "QuoteBody-Bold",
            NAVY,
            True,
        )
        _cover_line(
            c,
            f"{_date(q['date'])}   /   R{q['revision']:02d}",
            PAGE_WIDTH - MARGIN,
            713,
            213,
            8,
            color=MUTED,
            right=True,
        )

        options = q["options"]
        multi = len(options) > 1
        all_twin = all(CATALOG[o["capacity"]]["twin"] for o in options)
        # Engineering guide marks keep the composition restrained and industrial.
        c.setStrokeColor(colors.HexColor("#E2DDD3"))
        c.setLineWidth(0.45)
        c.line(MARGIN, 425, PAGE_WIDTH - MARGIN, 425)
        for x in (MARGIN, MARGIN + 154, PAGE_WIDTH - MARGIN):
            c.line(x, 419, x, 431)
        if multi:
            headline = (
                "Power, your way."
                if q["mode"] == "alternatives"
                else "Power, together."
            )
            _cover_line(
                c, headline, MARGIN, 608, CONTENT_WIDTH, 35, "QuoteDisplay-Bold", NAVY
            )
            _cover_line(
                c,
                f"{len(options)} {'capacity options' if q['mode']=='alternatives' else 'supply items'}  /  {'Twin genset systems' if all_twin else 'Diesel generating sets'}",
                MARGIN,
                586,
                CONTENT_WIDTH,
                10,
                color=MUTED,
            )
            image_name = (
                "product-twin-premium.png" if all_twin else "product-single-premium.png"
            )
            image_box = (MARGIN + 45, 435, CONTENT_WIDTH - 85, 133)
        else:
            o = options[0]
            capacity = _capacity(o).split(" (")[0].replace(" kVA", "")
            _cover_line(
                c, capacity, MARGIN - 3, 526, 257, 88, "QuoteDisplay-Bold", NAVY
            )
            _cover_line(c, "kVA", MARGIN, 491, 170, 27, "QuoteDisplay", NAVY)
            _cover_line(
                c,
                "TWIN GENSET" if all_twin else "DIESEL GENERATING SET",
                MARGIN,
                468,
                220,
                8,
                "QuoteBody-Bold",
                RED,
            )
            _cover_line(
                c,
                f"{o['phase']}  /  Quantity {o['quantity']}",
                MARGIN,
                448,
                220,
                9,
                color=MUTED,
            )
            image_name = (
                "product-twin-premium.png" if all_twin else "product-single-premium.png"
            )
            image_box = (248, 446, 317 if all_twin else 305, 174)
        photo = _image(image_name, image_box[2], image_box[3])
        if photo:
            photo.drawOn(
                c,
                image_box[0] + (image_box[2] - photo.drawWidth) / 2,
                image_box[1] + (image_box[3] - photo.drawHeight) / 2,
            )
        _cover_line(
            c,
            "Representative product artwork. Configuration varies by model.",
            MARGIN,
            408,
            CONTENT_WIDTH,
            7,
            color=MUTED,
        )

        if not multi:
            o = options[0]
            c.setFillColor(NAVY)
            c.rect(MARGIN, 282, CONTENT_WIDTH, 103, stroke=0, fill=1)
            c.setFillColor(RED)
            c.rect(MARGIN, 282, 3, 103, stroke=0, fill=1)
            _cover_line(
                c,
                "YOUR PROPOSED SYSTEM",
                MARGIN + 18,
                363,
                CONTENT_WIDTH - 36,
                8,
                "QuoteBody-Bold",
                colors.HexColor("#D2D8DA"),
            )
            _cover_line(
                c,
                _capacity(o),
                MARGIN + 18,
                328,
                CONTENT_WIDTH - 36,
                30,
                "QuoteDisplay-Bold",
                WHITE,
            )
            _cover_line(
                c,
                f"{o['phase']}  /  Quantity {o['quantity']}  /  Mahindra Powerol",
                MARGIN + 18,
                304,
                CONTENT_WIDTH - 36,
                9,
                color=colors.HexColor("#D2D8DA"),
            )
        else:
            card_width = (CONTENT_WIDTH - 15) / 2
            for i, o in enumerate(options[:2]):
                x = MARGIN + i * (card_width + 15)
                c.setFillColor(NAVY)
                c.rect(x, 282, card_width, 103, stroke=0, fill=1)
                c.setFillColor(RED)
                c.rect(x, 382, 32, 3, stroke=0, fill=1)
                tag = "OPTION" if q["mode"] == "alternatives" else "SUPPLY ITEM"
                _cover_line(
                    c,
                    f"{tag} {i+1:02d}",
                    x + 15,
                    364,
                    card_width - 30,
                    7.5,
                    "QuoteBody-Bold",
                    colors.HexColor("#D2D8DA"),
                )
                _cover_line(
                    c,
                    _capacity(o).split(" (")[0],
                    x + 15,
                    335,
                    card_width - 30,
                    27,
                    "QuoteDisplay-Bold",
                    WHITE,
                )
                config = (
                    _capacity(o).split(" (")[1].rstrip(")") + " kVA"
                    if " (" in _capacity(o)
                    else o["phase"]
                )
                _cover_line(
                    c,
                    f"{config}  /  Qty {o['quantity']}",
                    x + 15,
                    315,
                    card_width - 30,
                    8,
                    color=colors.HexColor("#D2D8DA"),
                )
                note = (
                    "Subject to supplier confirmation"
                    if o["capacity"] == "400 KVA (200 x 2)"
                    else "Configuration details inside"
                )
                _cover_line(
                    c,
                    note,
                    x + 15,
                    297,
                    card_width - 30,
                    7.5,
                    color=colors.HexColor("#D2D8DA"),
                )
        _cover_line(
            c, "YOUR PROPOSAL", MARGIN, 257, CONTENT_WIDTH, 8, "QuoteBody-Bold", RED
        )
        journey = (
            "Equipment details  /  Your offer  /  Commercial terms"
            if q["include_specs"]
            else "Your offer  /  Commercial terms"
        )
        _cover_line(c, journey, MARGIN, 237, CONTENT_WIDTH, 12, "QuoteDisplay", NAVY)
        _cover_line(
            c,
            "Review the equipment, followed by pricing and commercial terms.",
            MARGIN,
            218,
            CONTENT_WIDTH,
            8.5,
            color=MUTED,
        )
        if len(options) > 2:
            _cover_line(
                c,
                "Additional capacities are listed inside.",
                MARGIN,
                201,
                CONTENT_WIDTH,
                8,
                "QuoteBody-Bold",
                RED,
            )

        c.setStrokeColor(LINE)
        c.line(MARGIN, 188, PAGE_WIDTH - MARGIN, 188)
        _cover_line(c, "REFERENCE", MARGIN, 169, 330, 7.5, "QuoteBody-Bold", RED)
        ref = q["reference"]
        reference = ref["source"] or "Your generator requirement"
        if ref["meeting_date"]:
            reference += "  /  " + _date(ref["meeting_date"])
        _cover_line(c, reference, MARGIN, 153, CONTENT_WIDTH, 9, color=NAVY)
        if ref["previous_quote"]:
            _cover_line(
                c,
                "Earlier quote: " + ref["previous_quote"],
                MARGIN,
                137,
                CONTENT_WIDTH,
                8,
                color=MUTED,
            )
        elif ref["discussion"]:
            _cover_line(
                c, ref["discussion"], MARGIN, 137, CONTENT_WIDTH, 8, color=MUTED
            )
        _cover_line(
            c,
            f"VALID UNTIL  {_date(until.isoformat()).upper()}",
            MARGIN,
            113,
            CONTENT_WIDTH,
            8,
            "QuoteBody-Bold",
            NAVY,
        )
        _cover_line(
            c,
            "The price schedule is followed by the final commercial terms.",
            MARGIN,
            96,
            CONTENT_WIDTH,
            7.5,
            color=MUTED,
        )

        c.setStrokeColor(NAVY)
        c.line(MARGIN, 70, PAGE_WIDTH - MARGIN, 70)
        _cover_line(
            c,
            q["seller"]["phone"],
            MARGIN,
            51,
            CONTENT_WIDTH - 70,
            8,
            "QuoteBody-Bold",
            NAVY,
        )
        _cover_line(
            c, q["seller"]["email"], MARGIN, 36, CONTENT_WIDTH - 70, 8, color=MUTED
        )
        _cover_line(
            c, "01", PAGE_WIDTH - MARGIN, 42, 40, 18, "QuoteDisplay-Bold", NAVY, True
        )
        c.restoreState()


def _recipient_details(q, s):
    """Full, unabridged customer/reference data; long values safely flow to more pages."""
    customer = q["customer"]
    contact_title = ParagraphStyle(
        "ContactTitle", parent=s["small"], fontName="QuoteBody-Bold", textColor=NAVY
    )
    left = [_p("PREPARED FOR", s["eyebrow"]), _p(customer["name"], contact_title)]
    if customer["address"].strip():
        left.append(_p(customer["address"], s["small"]))
    for key, label in [
        ("attention", "Attn:"),
        ("phone", "Phone:"),
        ("email", "Email:"),
        ("gstin", "GSTIN:"),
    ]:
        if customer[key].strip():
            left.append(_label(label, customer[key], s["small"]))
    right = [
        _p("QUOTATION REFERENCE", s["eyebrow"]),
        _p(q["quote_number"], contact_title),
        _label("Lead:", q["lead_ref"], s["small"]),
    ]
    ref = q["reference"]
    if ref["source"] or ref["meeting_date"]:
        source = ref["source"] + (
            " / " + _date(ref["meeting_date"]) if ref["meeting_date"] else ""
        )
        right.append(_p(source, s["small"]))
    if ref["previous_quote"]:
        right.append(_label("Previous quotation:", ref["previous_quote"], s["small"]))
    # Short discussions stay with the references; longer prose gets the full width.
    long_discussion = len(ref["discussion"]) > 170 or "\n" in ref["discussion"]
    if ref["discussion"] and not long_discussion:
        right.append(_p(ref["discussion"], s["small"]))
    table = _layout(
        [[left, right]], [CONTENT_WIDTH * 0.53, CONTENT_WIDTH * 0.47], padding=6
    )
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.6, LINE)]))
    result = [table, Spacer(1, 5)]
    if long_discussion:
        result += [
            _label("Discussion / reference:", ref["discussion"], s["small"]),
            Spacer(1, 5),
        ]
    return result


def _price_table(rows, s):
    headings = [
        "Description",
        "Qty",
        "Unit rate\nINR",
        "GST\nINR / rate",
        "Amount\nincl. GST, INR",
    ]
    data = [
        [
            _p(h, s["table_head"] if i == 0 else s["number_head"])
            for i, h in enumerate(headings)
        ]
    ]
    for row in rows:
        tax = Paragraph(
            f"{_escaped(money(row['tax']))}<br/><font size='7.4' color='#60717A'>@ {_escaped(row['tax_rate'])}%</font>",
            s["number"],
        )
        data.append(
            [
                _p(row["description"].replace("KVA", "kVA"), s["table"]),
                _p(row["quantity"], s["number"]),
                _p(money(row["rate"]), s["number"]),
                tax,
                _p(money(row["total"]), s["number"]),
            ]
        )
    return _table(data, [CONTENT_WIDTH - 28 - 79 - 79 - 97, 28, 79, 79, 97], padding=5)


def _price_band(o, c, index, mode, s):
    tag = "OPTION" if mode == "alternatives" else "SUPPLY ITEM"
    left = [
        _p(f"{tag} {index:02d}", s["eyebrow"]),
        _p(_capacity(o), s["customer"]),
    ]
    right = [
        _p(
            "TOTAL INCLUDING GST",
            ParagraphStyle("BandTax", parent=s["tiny"], alignment=TA_RIGHT),
        ),
        _p("INR " + money(c["total"]), s["total_dark"]),
    ]
    return _layout(
        [[left, right]],
        [CONTENT_WIDTH * 0.49, CONTENT_WIDTH * 0.51],
        padding=5,
    )


def _option_pricing(o, c, i, mode, s, single=False):
    story = (
        [Spacer(1, 7)]
        if single
        else [Spacer(1, 4), _price_band(o, c, i, mode, s), Spacer(1, 3)]
    )
    included = [r for r in c["rows"] if not r["optional"]]
    optional = [r for r in c["rows"] if r["optional"]]
    story.append(_price_table(included, s))
    story.append(
        _layout(
            [
                [
                    _p("Basic amount  INR " + money(c["subtotal"]), s["small"]),
                    _p(
                        "GST  INR " + money(c["tax"]),
                        ParagraphStyle(
                            "TaxRight", parent=s["small"], alignment=TA_RIGHT
                        ),
                    ),
                ]
            ],
            [CONTENT_WIDTH * 0.6, CONTENT_WIDTH * 0.4],
            padding=5,
            background=PALE,
        )
    )
    if single:
        total = _layout(
            [
                [
                    [
                        _p("YOUR QUOTATION TOTAL", s["band_label"]),
                        _p("Including GST. Optional extras excluded.", s["band_label"]),
                    ],
                    _p("INR " + money(c["total"]), s["total"]),
                ]
            ],
            [CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5],
            padding=12,
            background=NAVY,
        )
        story += [Spacer(1, 4), total]
        # A short ordinary offer moves as one block when customer details grow,
        # so its total cannot become the only item on a continuation page.
        if len(included) <= 6 and all(len(r["description"]) <= 180 for r in included):
            story = [KeepTogether(story)]
    if optional:
        extra_story = [
            Spacer(1, 6),
            _p("Optional extras - excluded from the offer total", s["small"]),
            _price_table(optional, s),
            _p(
                "Optional extras total incl. GST: INR " + money(c["optional_total"]),
                s["small"],
            ),
        ]
        if len(optional) <= 6 and all(len(r["description"]) <= 180 for r in optional):
            story.append(KeepTogether(extra_story))
        else:
            story += extra_story
    if o["notes"].strip():
        story += [Spacer(1, 5), _label("Offer notes:", o["notes"], s["small"])]
    entry = CATALOG[o["capacity"]]
    if entry["twin"] and not entry["verified"]:
        story.append(
            _p(
                "400 kVA (200 x 2): technical specifications and availability to be confirmed with supplier.",
                s["small"],
            )
        )
    return story


def _feature_groups(q):
    """Use only the source profile applicable to each selected equipment family."""
    legacy = [o for o in q["options"] if not CATALOG[o["capacity"]]["twin"]]
    twin = [o for o in q["options"] if o["capacity"] == "500 KVA (250 x 2)"]
    groups = []
    if legacy:
        groups.append((LEGACY_FEATURES, legacy, False))
    if twin:
        groups.append((TWIN_500_FEATURES, twin, True))
    return groups


def _equipment_section_count(q):
    if not q["include_specs"]:
        return 0
    return 1 + bool(_feature_groups(q))


def _feature_bullets(items, s):
    bullet_style = ParagraphStyle(
        "FeatureBullet",
        parent=s["body"],
        fontSize=9.2,
        leading=12.8,
        leftIndent=10,
        bulletIndent=0,
        spaceAfter=4,
    )
    return [Paragraph(_escaped(item), bullet_style, bulletText="-") for item in items]


def _equipment_features(q, s):
    story = []
    for profile, options, twin in _feature_groups(q):
        applicable = list(
            dict.fromkeys(f"{_capacity(o)} / {o['phase']}" for o in options)
        )
        story += [
            PageBreak(),
            _p("01  /  EQUIPMENT FEATURES", s["eyebrow"]),
            _p("DG features", s["title"]),
            _p("Built around your power requirements.", s["body"]),
            _p("Applies to: " + "; ".join(applicable), s["small"]),
            Spacer(1, 7),
            _p("Product salient features", s["subheading"]),
        ]
        midpoint = (len(profile["highlights"]) + 1) // 2
        highlights = _layout(
            [
                [
                    _feature_bullets(profile["highlights"][:midpoint], s),
                    _feature_bullets(profile["highlights"][midpoint:], s),
                ]
            ],
            [CONTENT_WIDTH / 2, CONTENT_WIDTH / 2],
            padding=10,
            background=WARM,
        )
        story += [highlights, Spacer(1, 13)]
        if twin:
            photo = _image("twin-genset-components.png", CONTENT_WIDTH, 115)
            if photo:
                story += [
                    photo,
                    Spacer(1, 5),
                    _p(
                        "Twin-system illustration from the supplied brochure. Representative arrangement.",
                        s["tiny"],
                    ),
                    Spacer(1, 10),
                ]
        columns = []
        for title, key, filename in [
            ("Engine", "engine", "engine.png"),
            ("Alternator", "alternator", "alternator.png"),
        ]:
            details = [_p(title.upper(), s["eyebrow"])]
            if not twin:
                photo = _image(filename, 150, 93)
                if photo:
                    details += [
                        photo,
                        Spacer(1, 8),
                    ]
            details += _feature_bullets(profile[key], s)
            if twin and key == "engine":
                details += [Spacer(1, 4), _p(profile["section_notes"][key], s["tiny"])]
            columns.append(details)
        components = _layout(
            [[columns[0], columns[1]]],
            [CONTENT_WIDTH / 2, CONTENT_WIDTH / 2],
            padding=11,
            background=PALE,
        )
        components.setStyle(TableStyle([("LINEBEFORE", (1, 0), (1, -1), 0.5, LINE)]))
        story += [components, Spacer(1, 10), _p(profile["note"], s["tiny"])]
        if not twin:
            story.append(
                _p(
                    "Component images are representative of the equipment family.",
                    s["tiny"],
                )
            )

        story += [
            PageBreak(),
            _p("01  /  EQUIPMENT FEATURES", s["eyebrow"]),
            _p("Controls & enclosure", s["title"]),
            _p("Monitoring, protection and practical service access.", s["body"]),
            _p("Applies to: " + "; ".join(applicable), s["small"]),
            Spacer(1, 9),
        ]
        for title, key, filename in [
            (
                "Controller",
                "controller",
                "twin-controller.png" if twin else "controller.png",
            ),
            (
                "Acoustic enclosure",
                "enclosure",
                "twin-genset.png" if twin else "features.png",
            ),
        ]:
            photo = _image(filename, 128, 125)
            visual = [photo, Spacer(1, 7)] if photo else []
            visual.append(
                _p(
                    "Representative "
                    + ("control panel" if key == "controller" else "DG enclosure"),
                    s["tiny"],
                )
            )
            details = [
                _p(title.upper(), s["eyebrow"]),
                *_feature_bullets(profile[key], s),
            ]
            if key == "controller" or twin:
                details += [Spacer(1, 4), _p(profile["section_notes"][key], s["tiny"])]
            panel = _layout(
                [[visual, details]],
                [148, CONTENT_WIDTH - 148],
                padding=10,
                background=PALE,
            )
            story += [KeepTogether([panel]), Spacer(1, 12)]
        story.append(_p(profile["note"], s["tiny"]))
        if any(o["capacity"] == "400 KVA (200 x 2)" for o in q["options"]):
            pending = _layout(
                [
                    [
                        _p(
                            "400 kVA (200 x 2): product, engine, alternator, controller and enclosure details require supplier confirmation. The features above do not apply to this pending configuration.",
                            s["small"],
                        )
                    ]
                ],
                [CONTENT_WIDTH],
                padding=9,
                background=WARM,
            )
            pending.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, -1), 2, RED)]))
            story += [Spacer(1, 8), pending]
    return story


def _specifications(q, s, compact=False):
    story = (
        [Spacer(1, 13), _p("Equipment details", s["subheading"])]
        if compact
        else [
            PageBreak(),
            _p(
                f"{_equipment_section_count(q):02d}  /  EQUIPMENT DETAILS", s["eyebrow"]
            ),
            _p("Technical specifications", s["title"]),
            _p("The equipment behind your quotation.", s["body"]),
            Spacer(1, 6),
        ]
    )
    seen = set()
    for o in q["options"]:
        key = (o["capacity"], o["phase"])
        if key in seen:
            continue
        seen.add(key)
        e = CATALOG[o["capacity"]]
        linked = ", ".join(
            str(i)
            for i, x in enumerate(q["options"], 1)
            if (x["capacity"], x["phase"]) == key
        )
        story += [
            _p(_capacity(o), s["subheading"] if compact else s["section"]),
            _p(
                f"{o['phase']}  /  {'Option' if q['mode']=='alternatives' else 'Supply item'} {linked}",
                s["small"],
            ),
        ]
        if e["twin"] and not e["verified"]:
            pending_specs = [
                _label(label + ":", value, s["small"])
                for label, value in e["specs"].items()
            ]
            pending_specs.append(_p(e["spec_note"], s["tiny"]))
            pending_specs.append(
                _p(
                    "Product features, engine and alternator models, starting system, electrical specifications, controller and enclosure details require supplier confirmation.",
                    s["small"],
                )
            )
            story += [
                _layout(
                    [[pending_specs]], [CONTENT_WIDTH], padding=10, background=WARM
                ),
                Spacer(1, 7),
            ]
            continue
        photo = _image(
            "twin-genset.png" if e["twin"] else "features.png",
            205,
            90 if e["twin"] else 130,
        )
        summary = [
            _p("TWIN GENSET" if e["twin"] else "DIESEL GENERATING SET", s["eyebrow"])
        ]
        if e["model"]:
            summary.append(_label("Model:", e["model"], s["body"]))
        if e["kwe"] is not None:
            summary.append(_label("Power:", str(e["kwe"]) + " kWe", s["body"]))
        if e["twin"]:
            summary.append(
                _p(
                    "One quoted unit is one complete system with two internal DG units.",
                    s["small"],
                )
            )
        summary.append(
            _p(
                "Representative image. Final specification and supply scope are as quoted.",
                s["tiny"],
            )
        )
        if photo and not compact:
            story += [
                KeepTogether(
                    [
                        _layout(
                            [[summary, photo]],
                            [CONTENT_WIDTH * 0.56, CONTENT_WIDTH * 0.44],
                            padding=6,
                            background=PALE,
                        )
                    ]
                ),
                Spacer(1, 9),
            ]
        rows = [[_p("Specification", s["table_head"]), _p("Details", s["table_head"])]]
        for label, value in e["specs"].items():
            if value is not None and str(value).strip():
                rows.append([_p(label, s["table"]), _p(value, s["table"])])
        story += [
            _table(rows, [CONTENT_WIDTH * 0.43, CONTENT_WIDTH * 0.57], padding=3),
            Spacer(1, 7),
            _p(e["spec_note"], s["tiny"]),
        ]
    return story


def _terms(q, s):
    story = [
        PageBreak(),
        _p(
            f"{_equipment_section_count(q) + 2:02d}  /  THE DETAILS THAT MATTER",
            s["eyebrow"],
        ),
        _p("Commercial terms", s["title"]),
        _p("A clear scope, from order to delivery.", s["body"]),
        Spacer(1, 6),
    ]
    until = date.fromisoformat(q["date"]) + timedelta(days=q["valid_days"])
    rows = [
        [
            _p("Pricing & taxes", s["term_label"]),
            _p(
                "All amounts are in INR. The offer total includes GST at the itemized rates. Separately listed optional extras are excluded.",
                s["terms"],
            ),
        ],
        [
            _p("Offer validity", s["term_label"]),
            _p(
                f"{q['valid_days']} days from {_date(q['date'])}; valid until {_date(until.isoformat())}. Prices are subject to reconfirmation after this date.",
                s["terms"],
            ),
        ],
    ]
    for field, label in [
        ("payment", "Payment"),
        ("delivery", "Delivery"),
        ("warranty", "Warranty"),
        ("scope", "Scope of supply"),
        ("exclusions", "Exclusions"),
        ("additional", "Additional terms"),
    ]:
        if q["terms"][field].strip():
            rows.append([_p(label, s["term_label"]), _p(q["terms"][field], s["terms"])])
    if q["mode"] == "alternatives" and len(q["options"]) > 1:
        rows.append(
            [
                _p("Capacity selection", s["term_label"]),
                _p(
                    "The capacities are alternative offers under one lead. Please specify your selected option and any accepted optional extras in the purchase order.",
                    s["terms"],
                ),
            ]
        )
    table = _layout(rows, [116, CONTENT_WIDTH - 116], padding=7)
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.45, LINE)]))
    story.append(table)
    seller = q["seller"]
    closing = [
        _p("READY TO TAKE THE NEXT STEP?", s["eyebrow"]),
        _p("We look forward to supporting your power requirement.", s["subheading"]),
        _p("For " + seller["name"], s["body"]),
    ]
    for field in ("contact", "phone", "email"):
        if seller[field].strip():
            closing.append(_p(seller[field], s["small"]))
    story += [Spacer(1, 17), KeepTogether(closing)]
    if seller["address"].strip():
        story.append(_label("Registered address:", seller["address"], s["tiny"]))
    if seller["name"].strip().casefold() == "techno electromechs":
        story.append(
            _p(
                "Sales office: Opp. Sudharshan Petrol Pump, near Bagavati Mangal Karyalay, NH-04, Gokulshirgaon, Kolhapur - 416234.",
                s["tiny"],
            )
        )
    if seller["gstin"].strip():
        story.append(_label("GSTIN:", seller["gstin"], s["tiny"]))
    return story


def create_pdf(quote):
    errors = validate_quote(quote)
    if errors:
        raise ValueError("\n".join(errors))
    s = _styles()
    calculations = [calculate_option(o) for o in quote["options"]]
    out = BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=51,
        bottomMargin=57,
        title=f"Quotation {quote['quote_number']} - Revision {quote['revision']}",
        author=_text(quote["seller"]["name"]),
        subject="Mahindra Powerol generator quotation",
        pageCompression=1,
        allowSplitting=1,
    )
    multi = len(quote["options"]) > 1
    story = [_ProposalCover(quote, doc.height - 12)]
    if quote["include_specs"]:
        story += _equipment_features(quote, s)
        story += _specifications(quote, s)
    story += [
        PageBreak(),
        _p(f"{_equipment_section_count(quote) + 1:02d}  /  YOUR OFFER", s["eyebrow"]),
        _p("Price schedule", s["title"]),
    ]
    story += _recipient_details(quote, s)
    for i, (o, c) in enumerate(zip(quote["options"], calculations), 1):
        story += _option_pricing(o, c, i, quote["mode"], s, single=not multi)
    if quote["mode"] == "combined" and multi:
        total = sum((c["total"] for c in calculations), Decimal("0.00"))
        story += [
            Spacer(1, 7),
            _layout(
                [
                    [
                        [
                            _p("Combined order total", s["small"]),
                            _p("Including GST. Optional extras excluded.", s["tiny"]),
                        ],
                        _p("INR " + money(total), s["total_dark"]),
                    ]
                ],
                [CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5],
                padding=5,
                background=WARM,
            ),
        ]
    story += _terms(quote, s)
    chrome = _page_chrome(quote)
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=chrome)
    return out.getvalue()
