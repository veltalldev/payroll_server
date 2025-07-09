from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ManualTimeEntry(BaseModel):
    employee_id: int
    clock_type: str  # "IN" or "OUT"
    timestamp: datetime
    reason: str      # "network_outage", "emergency", etc.
    admin_notes: str

class TimeEntryEdit(BaseModel):
    """Model for editing time entries"""
    entry_id: int
    new_timestamp: datetime
    new_clock_type: str  # "IN" or "OUT"
    admin_notes: str

class TimeEntryCreate(BaseModel):
    """Model for creating missing time entries"""
    employee_id: int
    clock_type: str  # "IN" or "OUT"
    timestamp: datetime
    admin_notes: str
    wifi_network: Optional[str] = "ADMIN_CREATED"

class ProblemTimeEntry(BaseModel):
    """Model for flagging problematic entries"""
    entry_id: int
    employee_id: int
    employee_name: str
    timestamp: datetime
    clock_type: str
    problem_type: str
    problem_description: str
    suggested_action: str
