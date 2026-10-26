from datetime import date, datetime

from pydantic import BaseModel, Field


class CustomerBalanceSummary(BaseModel):
    id: int
    name: str
    phone: str | None
    note: str | None
    balance: int


class OverdueCustomer(CustomerBalanceSummary):
    owed_since: datetime = Field(description="Date of the oldest credit that is still unpaid")
    days_outstanding: int


class Dashboard(BaseModel):
    total_outstanding: int = Field(description="Sum of all positive customer balances")
    customers_with_baki: int
    today: date = Field(description="The shop's local date used for today's collection")
    today_collection: int = Field(description="Sum of payments received today")
    top_customers: list[CustomerBalanceSummary] = Field(description="Top 5 by balance")
    overdue_days: int
    overdue_customers: list[OverdueCustomer] = Field(description="Oldest debt first")
