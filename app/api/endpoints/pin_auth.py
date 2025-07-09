# app/api/endpoints/pin_auth.py - NEW FILE
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import hashlib
import hmac
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.config import ServerConfig
from app.models.common import ClockRequest, ClockResponse
from app.api.endpoints.clocking import request_clock_operation

router = APIRouter()
logger = logging.getLogger(__name__)

class PINValidationRequest(BaseModel):
    employee_id: int
    pin: str

class PINValidationResponse(BaseModel):
    success: bool
    employee_name: str
    employee_id: int
    message: str

class SetPINRequest(BaseModel):
    employee_id: int
    new_pin: str
    admin_secret: str

class PINClockRequest(BaseModel):
    employee_id: int
    pin: str
    wifi_ssid: Optional[str] = None
    wifi_verification_required: bool = True

def hash_pin(pin: str, salt: str) -> str:
    """Hash a PIN with salt using HMAC-SHA256"""
    return hmac.new(
        salt.encode('utf-8'),
        pin.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def generate_salt(employee_id: int) -> str:
    """Generate a consistent salt for an employee"""
    return hashlib.sha256(f"{employee_id}_{ServerConfig.ADMIN_SECRET}".encode()).hexdigest()[:16]

@router.post("/auth/validate-pin", response_model=PINValidationResponse)
async def validate_employee_pin(request: PINValidationRequest, client_request: Request):
    """Validate employee PIN for authentication"""
    
    client_ip = client_request.client.host
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get employee and their PIN hash
        cursor.execute('''
            SELECT employee_id, name, active, pin_hash
            FROM employees 
            WHERE employee_id = ?
        ''', (request.employee_id,))
        
        employee = cursor.fetchone()
        
        if not employee:
            logger.warning(f"PIN validation failed - Employee {request.employee_id} not found (IP: {client_ip})")
            raise HTTPException(status_code=404, detail="Employee not found")
        
        if not employee['active']:
            logger.warning(f"PIN validation failed - Employee {request.employee_id} inactive (IP: {client_ip})")
            raise HTTPException(status_code=403, detail="Employee account is inactive")
        
        if not employee['pin_hash']:
            logger.warning(f"PIN validation failed - No PIN set for employee {request.employee_id} (IP: {client_ip})")
            raise HTTPException(status_code=400, detail="No PIN set for this employee")
        
        # Generate salt and hash the provided PIN
        salt = generate_salt(request.employee_id)
        provided_pin_hash = hash_pin(request.pin, salt)
        
        # Compare hashes
        is_valid = hmac.compare_digest(employee['pin_hash'], provided_pin_hash)
        
        # Log the attempt
        cursor.execute('''
            INSERT INTO pin_attempts (employee_id, success, ip_address, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (request.employee_id, is_valid, client_ip, datetime.now()))
        
        conn.commit()
        
        if is_valid:
            logger.info(f"PIN validation SUCCESS for employee {employee['name']} ({request.employee_id}) from {client_ip}")
            return PINValidationResponse(
                success=True,
                employee_name=employee['name'],
                employee_id=request.employee_id,
                message="PIN validated successfully"
            )
        else:
            logger.warning(f"PIN validation FAILED for employee {employee['name']} ({request.employee_id}) from {client_ip}")
            raise HTTPException(status_code=401, detail="Invalid PIN")

@router.post("/clock/pin-request", response_model=ClockResponse)
async def clock_with_pin_validation(request: PINClockRequest, client_request: Request):
    """Clock operation with PIN validation"""
    
    # First validate the PIN
    pin_request = PINValidationRequest(employee_id=request.employee_id, pin=request.pin)
    pin_response = await validate_employee_pin(pin_request, client_request)
    
    if not pin_response.success:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    # Now perform the clock operation (reuse existing logic)
    clock_request = ClockRequest(
        employee_id=request.employee_id,
        wifi_ssid=request.wifi_ssid,
        wifi_verification_required=request.wifi_verification_required
    )
    
    return await request_clock_operation(clock_request, client_request)

@router.post("/admin/set-pin")
async def set_employee_pin(request: SetPINRequest):
    """Set or update an employee's PIN (admin only)"""
    
    # Verify admin secret
    if request.admin_secret != ServerConfig.ADMIN_SECRET:
        logger.warning(f"Unauthorized PIN set attempt for employee {request.employee_id}")
        raise HTTPException(status_code=403, detail="Invalid admin credentials")
    
    # Validate PIN format (4 digits)
    if not request.new_pin.isdigit() or len(request.new_pin) != 4:
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify employee exists
        cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (request.employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Generate salt and hash the PIN
        salt = generate_salt(request.employee_id)
        pin_hash = hash_pin(request.new_pin, salt)
        
        # Update employee's PIN
        cursor.execute('''
            UPDATE employees 
            SET pin_hash = ?, pin_set_at = ?
            WHERE employee_id = ?
        ''', (pin_hash, datetime.now(), request.employee_id))
        
        conn.commit()
        
        logger.info(f"PIN set for employee {employee['name']} ({request.employee_id})")
        
        return {
            "success": True,
            "message": f"PIN set for {employee['name']}",
            "employee_id": request.employee_id
        }
