"""Shared bounded parameters, validated before admitting a billable job."""
from pydantic import BaseModel,ConfigDict,Field


class TranscriptionSettings(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    onset_threshold:float=Field(default=.5,ge=.05,le=.95,allow_inf_nan=False)
    frame_threshold:float=Field(default=.3,ge=.05,le=.95,allow_inf_nan=False)
    minimum_note_length:float=Field(default=127.7,ge=20,le=2000,allow_inf_nan=False)
