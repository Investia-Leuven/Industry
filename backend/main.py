import io
import json
import os
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
import numpy as np

try:
    from backend.logic import (
        apply_final_sorting_and_formatting,
        combine_industry_dataframes,
        generate_plain_excel,
        generate_styled_excel,
        get_available_sectors,
        get_gradient_columns,
        get_industries_for_sector,
        process_uploaded_tickers,
    )
except ImportError:
    from logic import (
        apply_final_sorting_and_formatting,
        combine_industry_dataframes,
        generate_plain_excel,
        generate_styled_excel,
        get_available_sectors,
        get_gradient_columns,
        get_industries_for_sector,
        process_uploaded_tickers,
    )

_REPO_ROOT = Path(__file__).resolve().parent.parent
HELP_PDF = _REPO_ROOT / "help.pdf"

app = FastAPI(title="Investia Sector API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class FetchRequest(BaseModel):
    industry_names: List[str]
    industry_keys: List[str]
    data_method: str


class ExportBody(BaseModel):
    data: List[dict] = Field(default_factory=list)
    sheet_name: str = "Export"


def _dataframe_response(buffer: io.BytesIO, filename: str) -> Response:
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/sectors")
async def get_sectors():
    return get_available_sectors()


@app.get("/api/industries/{sector_key}")
async def get_industries(sector_key: str):
    return get_industries_for_sector(sector_key)


def _to_json_safe(df: pd.DataFrame):
    """Deep cleans a DataFrame for JSON by manually scanning all values."""
    # Convert to records first
    records = df.to_dict(orient="records")
    
    def clean_obj(obj):
        if isinstance(obj, list):
            return [clean_obj(i) for i in obj]
        if isinstance(obj, dict):
            return {k: clean_obj(v) for k, v in obj.items()}
        if isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
        return obj
        
    return clean_obj(records)

@app.post("/api/fetch")
async def fetch_data(req: FetchRequest):
    if len(req.industry_names) != len(req.industry_keys):
        raise HTTPException(
            status_code=400,
            detail="industry_names and industry_keys must have the same length.",
        )
    if not req.industry_names:
        raise HTTPException(status_code=400, detail="Select at least one industry.")
    try:
        df, warnings = combine_industry_dataframes(
            req.industry_names, req.industry_keys, req.data_method
        )
        if df.empty:
            return {"data": [], "columns": [], "warnings": warnings}

        df = apply_final_sorting_and_formatting(df)
        gradient_cols, inverse_gradient_cols = get_gradient_columns()
        return {
            "data": _to_json_safe(df),
            "columns": df.columns.tolist(),
            "warnings": warnings,
            "meta": {
                "gradient_columns": gradient_cols,
                "inverse_gradient_columns": inverse_gradient_cols
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/upload")
async def upload_tickers(
    file: UploadFile = File(...),
    merge: bool = Form(False),
    existing_json: Optional[str] = Form(None),
):
    contents = await file.read()
    existing_df = pd.DataFrame()
    if merge:
        if existing_json:
            try:
                rows = json.loads(existing_json)
                if isinstance(rows, list):
                    existing_df = pd.DataFrame(rows)
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="existing_json must be a JSON array of row objects.",
                    )
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=400, detail="existing_json must be valid JSON."
                ) from exc
    try:
        combined_df, error, warnings = process_uploaded_tickers(
            io.BytesIO(contents),
            existing_df if merge else pd.DataFrame(),
        )
        if error:
            raise HTTPException(status_code=400, detail=error)

        combined_df = apply_final_sorting_and_formatting(combined_df)
        gradient_cols, inverse_gradient_cols = get_gradient_columns()
        return {
            "data": _to_json_safe(combined_df),
            "columns": combined_df.columns.tolist(),
            "warnings": warnings,
            "meta": {
                "gradient_columns": gradient_cols,
                "inverse_gradient_columns": inverse_gradient_cols
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/export/plain")
async def export_plain(body: ExportBody):
    try:
        df = pd.DataFrame(body.data)
        buf = generate_plain_excel(df, sheet_name=body.sheet_name)
        return _dataframe_response(buf, "industry_companies_plain.xlsx")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/export/styled")
async def export_styled(body: ExportBody):
    try:
        df = pd.DataFrame(body.data)
        gradient_columns, inverse_gradient_columns = get_gradient_columns()
        buf = generate_styled_excel(
            df,
            gradient_columns,
            inverse_gradient_columns,
            sheet_name=body.sheet_name,
        )
        return _dataframe_response(buf, "industry_companies_styled.xlsx")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/help.pdf")
async def help_pdf():
    if not HELP_PDF.is_file():
        raise HTTPException(status_code=404, detail="Help PDF not found on server.")
    return FileResponse(
        HELP_PDF,
        filename="investia_sector_help.pdf",
        media_type="application/pdf",
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


if os.path.exists("frontend/dist"):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
