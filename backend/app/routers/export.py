from fastapi import APIRouter, Response

from app.schemas.travel import ExportRequest
from app.services.pdf_service import build_itinerary_pdf

router = APIRouter(tags=["export"])


@router.post("/export/pdf")
def export_pdf(request: ExportRequest) -> Response:
    pdf_bytes = build_itinerary_pdf(request.itinerary)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="france-itinerary.pdf"'
        },
    )
