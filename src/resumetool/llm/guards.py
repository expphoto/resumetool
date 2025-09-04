from pydantic import BaseModel


class GapAnalysis(BaseModel):
    missing_keywords: list[str]
    suggestions: list[str]


SCHEMA_EXAMPLE = GapAnalysis(missing_keywords=["python"], suggestions=["Quantify impact in bullets"]).model_json_schema()

