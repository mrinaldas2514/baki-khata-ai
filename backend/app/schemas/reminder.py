from pydantic import BaseModel, Field


class ReminderRequest(BaseModel):
    polish: bool = Field(
        default=True,
        description="Let the AI reword the message more naturally, when an AI model is set up",
    )


class Reminder(BaseModel):
    """A message for the shopkeeper to send. Nothing is sent by the server."""

    message: str = Field(description="Polite Banglish reminder with the customer's name and baki")
    polished: bool = Field(description="True if the AI reworded the template")
    phone: str | None = Field(description="The customer's phone as saved")
    whatsapp_number: str | None = Field(
        description="The phone in international form, digits only, for https://wa.me/<number>"
    )
