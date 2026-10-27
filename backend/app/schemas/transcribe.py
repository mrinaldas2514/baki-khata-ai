from pydantic import BaseModel, Field


class TranscribeResult(BaseModel):
    text: str = Field(
        description="What was said. Empty when no speech was heard.",
        examples=["rahim bhai 2 kg chal 120 taka baki"],
    )


class TranscribeStatus(BaseModel):
    available: bool = Field(description="False when the server has no speech-to-text key")
    max_seconds: float
    max_bytes: int
