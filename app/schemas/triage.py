from pydantic import BaseModel, Field


class TriageRunRequest(BaseModel):
    jurisdiction_code: str | None = Field(
        None,
        description=(
            "Optional jurisdiction to scope the batch to. For countries, the "
            "scope includes all sub-jurisdictions."
        ),
    )
    max_items: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum items the triage agent will review in this run.",
    )
