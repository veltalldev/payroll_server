from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class Employee(BaseModel):
    employee_id: int
    name: str
    employee_number: str
    created_at: datetime
    active: bool

class ClockRequest(BaseModel):
    employee_id: int
    clock_type: str = "AUTO"  # Default to AUTO - server determines IN/OUT
    wifi_ssid: Optional[str] = None
    wifi_verification_required: bool = True

class ClockResponse(BaseModel):
    success: bool
    employee_name: str
    clock_type: str
    timestamp: datetime
    message: str
    location_verified: bool = True
    wifi_network: Optional[str] = None

class ClockValidation(BaseModel):
    session_id: str
    scanned_qr_code: str

class ClockValidationResponse(BaseModel):
    success: bool
    employee_name: str
    clock_type: str
    timestamp: datetime
    message: str
    location_verified: bool = False
    wifi_network: Optional[str] = None

class QRResponse(BaseModel):
    qr_code: str
    qr_image_base64: str
    expires_at: datetime
    session_id: str
    location_verified: bool = False
    wifi_network: Optional[str] = None

class TimeEntry(BaseModel):
    entry_id: int
    employee_id: int
    clock_type: str
    timestamp: datetime
    qr_code_used: str
    synced_to_cloud: bool
    wifi_network: Optional[str] = None
