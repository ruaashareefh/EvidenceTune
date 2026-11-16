from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

Category = Literal[
    "answerable",
    "unanswerable",
    "contradictory",
    "irrelevant",
    "partially_supported",
]

class EvidenceExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    context: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    answerable: bool
    category: Category

    @model_validator(mode="after")
    def validate_labels(self):
        # "Answerable" means fully supported.
        expected = self.category == "answerable"

        if self.answerable != expected:
            raise ValueError(
                "answerable must match category"
            )

        return self