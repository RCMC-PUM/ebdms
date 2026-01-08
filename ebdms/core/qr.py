import base64
from io import BytesIO

import qrcode
from django.utils.html import format_html


def qr_img_tag(
    data_payload: str,
    width: int = 55,
    height: int = 55,
    box_size: int = 10,
    border: int = 0,
) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,  # LOW important
        box_size=box_size,
        border=border,
    )

    qr.add_data(data_payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return format_html(
        '<img src="data:image/png;base64,{}" '
        'width="{}" height="{}" '
        'style="padding: 8px; background: #fff;" '
        'alt="QR code" />',
        encoded,
        width,
        height,
    )
