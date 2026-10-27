import datetime as dt
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


class DaySummary(BaseModel):
    date: dt.date = Field(description="A local calendar day of the shop")
    credit: int = Field(description="New baki given that day")
    payment: int = Field(description="Payments received that day")


class Dashboard(BaseModel):
    total_outstanding: int = Field(description="Sum of all positive customer balances")
    customers_with_baki: int
    today: date = Field(description="The shop's local date used for today's numbers")
    today_collection: int = Field(description="Sum of payments received today")
    today_new_credit: int = Field(description="Sum of new baki given today")
    top_customers: list[CustomerBalanceSummary] = Field(description="Top 5 by balance")
    overdue_days: int
    overdue_customers: list[OverdueCustomer] = Field(description="Oldest debt first")
    last_7_days: list[DaySummary] = Field(description="Oldest first, ending with today")
