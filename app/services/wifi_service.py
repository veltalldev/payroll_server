import logging
from typing import Optional, Tuple
from datetime import datetime
from app.core.config import WiFiConfig # Import WiFiConfig
from app.core.database import get_db # Import get_db

logger = logging.getLogger(__name__)

def validate_workplace_location(wifi_ssid: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """Validate if WiFi SSID indicates workplace presence"""
    if not WiFiConfig.WIFI_VERIFICATION_ENABLED:
        logger.info("WiFi verification disabled - allowing all locations")
        return True, "WiFi verification disabled", None
        
    if not wifi_ssid:
        return False, "WiFi network information required for clock operations", None
    
    # Clean SSID
    clean_ssid = clean_wifi_ssid(wifi_ssid)
    
    if not clean_ssid:
        return False, "Invalid WiFi network information", None
    
    # Direct match against approved networks
    if clean_ssid in WiFiConfig.APPROVED_WORKPLACE_NETWORKS:
        logger.info(f"WiFi validation success: Direct match for '{clean_ssid}'")
        return True, f"Location verified at workplace network", clean_ssid
    
    # Pattern matching if enabled
    if WiFiConfig.WIFI_PATTERN_MATCHING_ENABLED:
        for pattern in WiFiConfig.APPROVED_NETWORK_PATTERNS:
            if pattern.endswith('*') and clean_ssid.startswith(pattern[:-1]):
                logger.info(f"WiFi validation success: Pattern match '{pattern}' for '{clean_ssid}'")
                return True, f"Location verified at workplace network", clean_ssid
    
    # Network not approved
    approved_list = ", ".join(WiFiConfig.APPROVED_WORKPLACE_NETWORKS)
    error_msg = f"Clock operations only allowed from workplace networks. Current network '{clean_ssid}' not approved. Approved networks: {approved_list}"
    logger.warning(f"WiFi validation failed: '{clean_ssid}' not in approved networks")
    return False, error_msg, None

def clean_wifi_ssid(raw_ssid: str) -> Optional[str]:
    """Clean SSID string (remove quotes, whitespace, etc.)"""
    if not raw_ssid:
        return None
        
    # Remove surrounding quotes and whitespace
    cleaned = raw_ssid.strip()
    
    # Remove double quotes
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]
    
    # Remove single quotes
    if cleaned.startswith("'") and cleaned.endswith("'"):
        cleaned = cleaned[1:-1]
    
    # Remove any remaining whitespace
    cleaned = cleaned.strip()
    
    # Return None if empty after cleaning
    return cleaned if cleaned else None

def log_location_attempt(employee_id: int, employee_name: str, wifi_ssid: Optional[str], 
                         success: bool, message: str, ip_address: Optional[str] = None):
    """Log all location verification attempts for audit purposes"""
    
    if WiFiConfig.LOG_ALL_WIFI_ATTEMPTS:
        if success:
            logger.info(f"Location verification SUCCESS - Employee: {employee_name} ({employee_id}), WiFi: '{wifi_ssid}', IP: {ip_address}")
        else:
            logger.warning(f"Location verification FAILED - Employee: {employee_name} ({employee_id}), WiFi: '{wifi_ssid}', Message: {message}, IP: {ip_address}")
    
    # Store in database for audit trail
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO wifi_verification_log 
                (employee_id, wifi_ssid, success, message, ip_address, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (employee_id, wifi_ssid, success, message, ip_address, datetime.now()))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to log WiFi verification attempt: {e}")
