from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class WorkSession(BaseModel):
    """Represents a complete work session (clock in -> clock out)"""
    session_id: str
    employee_id: int
    employee_name: str
    clock_in: datetime
    clock_out: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    duration_hours: Optional[float] = None
    is_complete: bool = False
    wifi_network_in: Optional[str] = None
    wifi_network_out: Optional[str] = None
    date: str  # YYYY-MM-DD

class DailySummary(BaseModel):
    """Daily work summary for an employee"""
    employee_id: int
    employee_name: str
    date: str
    total_hours: float
    sessions: List[WorkSession]
    has_incomplete_session: bool = False
    overtime_hours: float = 0.0
    regular_hours: float = 0.0

class PayrollSummary(BaseModel):
    """Payroll summary for a period"""
    employee_id: int
    employee_name: str
    start_date: str
    end_date: str
    total_hours: float
    regular_hours: float
    overtime_hours: float
    total_days_worked: int
    sessions: List[WorkSession]
    daily_summaries: List[DailySummary]

class PayrollConfig(BaseModel):
    """Payroll calculation configuration"""
    regular_hours_per_day: float = 8.0
    overtime_multiplier: float = 1.5
    max_regular_hours_per_week: float = 40.0
