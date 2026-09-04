from __future__ import annotations
import csv, io, json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.land_record import LandRecord
from app.models.user import User

router = APIRouter(prefix="/exports", tags=["Exports"])

async def _records(db, user):
    rows = await db.execute(select(LandRecord).join(Document).where(Document.uploaded_by == user.id))
    return rows.scalars().all()

@router.get("/land-records/{format}")
async def export_records(format: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    records = await _records(db, current_user)
    data = [{"id": str(r.id), "document_id": str(r.document_id), "village": r.village, "tehsil": r.tehsil, "district": r.district, "state": r.state, "survey_number": r.survey_number, "khasra_number": r.khasra_number, "khata_number": r.khata_number, "plot_number": r.plot_number, "area": r.area, "area_unit": r.area_unit, "document_type": r.document_type, "status": r.status, "overall_confidence": r.overall_confidence} for r in records]
    if format == "json":
        body, media, name = json.dumps(data, ensure_ascii=False, default=str), "application/json", "land-records.json"
    elif format == "csv":
        out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(data[0]) if data else ["id"]); writer.writeheader(); writer.writerows(data); body, media, name = out.getvalue(), "text/csv", "land-records.csv"
    elif format == "xlsx":
        from openpyxl import Workbook
        out = io.BytesIO(); wb = Workbook(); ws = wb.active; ws.title = "Land Records"; headers = list(data[0]) if data else ["id"]; ws.append(headers)
        for row in data: ws.append([row.get(h) for h in headers])
        wb.save(out); out.seek(0); return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename={name}"})
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Format must be csv, json, or xlsx")
    return StreamingResponse(iter([body]), media_type=media, headers={"Content-Disposition": f"attachment; filename={name}"})
