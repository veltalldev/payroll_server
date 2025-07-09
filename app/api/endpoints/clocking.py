import logging
import hashlib
import qrcode
import io
import base64
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from app.core.config import ServerConfig, WiFiConfig # Import configs
from app.core.database import get_db # Import get_db
from app.models.common import ClockRequest, ClockResponse, QRResponse, ClockValidation, ClockValidationResponse # Import models
from app.services.wifi_service import validate_workplace_location, log_location_attempt # Import services

router = APIRouter()
logger = logging.getLogger(__name__)

# Utility functions (can be moved to a shared utils file if many grow)
def generate_qr_code_content(employee_id: int, timestamp: datetime) -> str:
    """Generate a unique QR code content based on employee and timestamp"""
    content = f"{employee_id}:{timestamp.isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def create_qr_image(content: str) -> str:
    """Create QR code image and return as base64 string"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(content)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str

def cleanup_expired_sessions():
    """Remove expired QR sessions from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM qr_sessions WHERE expires_at < ?",
            (datetime.now(),)
        )
        conn.commit()

@router.post("/clock/request", response_model=ClockResponse)
async def request_clock_operation(clock_request: ClockRequest, request: Request):
    """Process clock operation with WiFi location verification (no QR needed)"""
    
    # Get client IP for logging
    client_ip = request.client.host
    
    # Verify employee exists and is active
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT employee_id, active, name FROM employees WHERE employee_id = ?",
            (clock_request.employee_id,)
        )
        employee = cursor.fetchone()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        if not employee['active']:
            raise HTTPException(status_code=403, detail="Employee account is inactive")
    
    employee_name = employee['name']
    
    # WiFi location validation
    verified_network = None
    if clock_request.wifi_verification_required and WiFiConfig.WIFI_VERIFICATION_ENABLED:
        is_valid, message, verified_network = validate_workplace_location(clock_request.wifi_ssid)
        
        # Log the attempt (both success and failure)
        log_location_attempt(
            employee_id=clock_request.employee_id,
            employee_name=employee_name,
            wifi_ssid=clock_request.wifi_ssid,
            success=is_valid,
            message=message,
            ip_address=client_ip
        )
        
        if not is_valid:
            raise HTTPException(status_code=403, detail=message)
    
    # Determine clock type based on last entry
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT clock_type FROM time_entries 
            WHERE employee_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (clock_request.employee_id,))
        
        last_entry = cursor.fetchone()
        clock_type = "IN" if not last_entry or last_entry['clock_type'] == "OUT" else "OUT"
        
        # Create time entry directly (no QR session needed)
        timestamp = datetime.now()
        clock_record_id = f"WIFI_CLOCK_{clock_request.employee_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        cursor.execute('''
            INSERT INTO time_entries (employee_id, clock_type, qr_code_used, wifi_network, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (clock_request.employee_id, clock_type, clock_record_id, verified_network, timestamp))
        
        conn.commit()
        
        logger.info(f"WiFi Clock {clock_type} processed for employee {employee_name} ({clock_request.employee_id}) from network '{verified_network}' at {timestamp}")
        
        return ClockResponse(
            success=True,
            employee_name=employee_name,
            clock_type=clock_type,
            timestamp=timestamp,
            message=f"Successfully clocked {clock_type.lower()} at {timestamp.strftime('%I:%M %p')}",
            location_verified=verified_network is not None,
            wifi_network=verified_network
        )

@router.post("/clock/qr-request", response_model=QRResponse)
async def request_qr_clock_operation(clock_request: ClockRequest, request: Request):
    """Legacy QR generation endpoint (for backward compatibility)"""
    
    # Clean up expired sessions first
    cleanup_expired_sessions()
    
    # Get client IP for logging
    client_ip = request.client.host
    
    # Verify employee exists and is active
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT employee_id, active, name FROM employees WHERE employee_id = ?",
            (clock_request.employee_id,)
        )
        employee = cursor.fetchone()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        if not employee['active']:
            raise HTTPException(status_code=403, detail="Employee account is inactive")
    
    employee_name = employee['name']
    
    # WiFi location validation
    verified_network = None
    if clock_request.wifi_verification_required and WiFiConfig.WIFI_VERIFICATION_ENABLED:
        is_valid, message, verified_network = validate_workplace_location(clock_request.wifi_ssid)
        
        # Log the attempt
        log_location_attempt(
            employee_id=clock_request.employee_id,
            employee_name=employee_name,
            wifi_ssid=clock_request.wifi_ssid,
            success=is_valid,
            message=message,
            ip_address=client_ip
        )
        
        if not is_valid:
            raise HTTPException(status_code=403, detail=message)
    
    # Generate QR session
    timestamp = datetime.now()
    expires_at = timestamp + timedelta(minutes=ServerConfig.QR_CODE_EXPIRY_MINUTES)
    qr_content = generate_qr_code_content(clock_request.employee_id, timestamp)
    session_id = hashlib.sha256(f"{clock_request.employee_id}:{timestamp.isoformat()}:{clock_request.clock_type}".encode()).hexdigest()[:16]
    
    # Store session in database
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO qr_sessions (session_id, employee_id, qr_code, expires_at, wifi_network)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, clock_request.employee_id, qr_content, expires_at, verified_network))
        conn.commit()
    
    # Generate QR code image
    qr_image_base64 = create_qr_image(qr_content)
    
    logger.info(f"Legacy QR code generated for employee {employee_name} ({clock_request.employee_id}) from network '{verified_network}', expires at {expires_at}")
    
    return QRResponse(
        qr_code=qr_content,
        qr_image_base64=qr_image_base64,
        expires_at=expires_at,
        session_id=session_id,
        location_verified=verified_network is not None,
        wifi_network=verified_network
    )

@router.post("/clock/validate")
async def validate_clock_operation(validation: ClockValidation):
    """Legacy QR validation endpoint (for backward compatibility)"""
    # Clean up expired sessions
    cleanup_expired_sessions()
    
    # Find and validate session
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.session_id, s.employee_id, s.qr_code, s.expires_at, s.used, s.wifi_network, e.name
            FROM qr_sessions s
            JOIN employees e ON s.employee_id = e.employee_id
            WHERE s.session_id = ? AND s.qr_code = ?
        ''', (validation.session_id, validation.scanned_qr_code))
        
        session = cursor.fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail="Invalid QR code or session")
        
        if session['used']:
            raise HTTPException(status_code=409, detail="QR code already used")
        
        if datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00')) < datetime.now():
            raise HTTPException(status_code=410, detail="QR code expired")
        
        # Determine clock type based on last entry
        cursor.execute('''
            SELECT clock_type FROM time_entries 
            WHERE employee_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (session['employee_id'],))
        
        last_entry = cursor.fetchone()
        clock_type = "IN" if not last_entry or last_entry['clock_type'] == "OUT" else "OUT"
        
        # Create time entry
        cursor.execute('''
            INSERT INTO time_entries (employee_id, clock_type, qr_code_used, wifi_network)
            VALUES (?, ?, ?, ?)
        ''', (session['employee_id'], clock_type, validation.scanned_qr_code, session['wifi_network']))
        
        # Mark session as used
        cursor.execute('''
            UPDATE qr_sessions SET used = TRUE WHERE session_id = ?
        ''', (validation.session_id,))
        
        conn.commit()
        
        logger.info(f"Legacy QR Clock {clock_type} processed for employee {session['employee_id']} ({session['name']}) from network '{session['wifi_network']}'")
        
        return ClockValidationResponse(
            success=True,
            employee_name=session['name'],
            clock_type=clock_type,
            timestamp=datetime.now(),
            message=f"Successfully clocked {clock_type.lower()}",
            location_verified=session['wifi_network'] is not None,
            wifi_network=session['wifi_network']
        )
