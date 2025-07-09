import logging
import ssl
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from app.core.config import ServerConfig, WiFiConfig # Import configs
from app.core.database import get_db # Import get_db
from app.services.wifi_service import validate_workplace_location # Import validate_workplace_location

router = APIRouter()
logger = logging.getLogger(__name__)

# Utility for certificate generation (can be moved to a separate file if needed for more complex ops)
def generate_self_signed_cert_util():
    """Generate self-signed certificate for HTTPS"""
    CERT_DIR = Path(ServerConfig.SSL_CERT_FILE).parent
    CERT_DIR.mkdir(exist_ok=True, mode=0o755)
    cert_file = CERT_DIR / "cert.pem"
    key_file = CERT_DIR / "key.pem"

    if cert_file.exists() and key_file.exists():
        logger.info(f"Using existing SSL certificates")
        return str(cert_file), str(key_file)

    try:
        subject = f"/C={ServerConfig.SSL_CERT_COUNTRY}/ST={ServerConfig.SSL_CERT_STATE}/L={ServerConfig.SSL_CERT_CITY}/O={ServerConfig.SSL_CERT_ORG}/CN={ServerConfig.SSL_CERT_CN}"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:4096",
            "-keyout", str(key_file), "-out", str(cert_file),
            "-days", str(ServerConfig.SSL_CERT_DAYS), "-nodes", "-subj", subject
        ], check=True, capture_output=True, text=True)

        return str(cert_file), str(key_file)

    except subprocess.CalledProcessError as e:
        logger.error(f"OpenSSL command failed with error code {e.returncode}: {e}")
        logger.error(f"OpenSSL stdout: {e.stdout}")
        logger.error(f"OpenSSL stderr: {e.stderr}")
        logger.error("Install OpenSSL with: sudo apt-get install openssl")
        return None, None
    except FileNotFoundError as e:
        logger.error(f"OpenSSL executable not found: {e}")
        logger.error("Install OpenSSL with: sudo apt-get install openssl")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred during certificate generation: {e}")
        return None, None

@router.get("/")
async def root():
    return {
        "message": ServerConfig.APP_NAME,
        "version": ServerConfig.APP_VERSION,
        "description": ServerConfig.APP_DESCRIPTION,
        "status": "running",
        "https_enabled": ServerConfig.USE_HTTPS,
        "wifi_verification_enabled": WiFiConfig.WIFI_VERIFICATION_ENABLED,
        "approved_networks_count": len(WiFiConfig.APPROVED_WORKPLACE_NETWORKS),
    }

@router.get("/config")
async def get_public_config():
    """Get public configuration information"""
    return {
        "app_name": ServerConfig.APP_NAME,
        "app_version": ServerConfig.APP_VERSION,
        "wifi_verification_enabled": WiFiConfig.WIFI_VERIFICATION_ENABLED,
        "approved_networks": WiFiConfig.APPROVED_WORKPLACE_NETWORKS if WiFiConfig.WIFI_VERIFICATION_ENABLED else "disabled",
        "pattern_matching_enabled": WiFiConfig.WIFI_PATTERN_MATCHING_ENABLED,
        "https_enabled": ServerConfig.USE_HTTPS,
        "development_mode": ServerConfig.DEVELOPMENT_MODE,
    }

@router.get("/health")
async def health_check():
    """Enhanced health check with WiFi configuration info"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.execute("SELECT COUNT(*) FROM employees WHERE active = TRUE")
            employee_count = cursor.fetchone()[0]
            
            return {
                "status": "healthy", 
                "database": "connected",
                "active_employees": employee_count,
                "wifi_verification": WiFiConfig.WIFI_VERIFICATION_ENABLED,
                "approved_networks": WiFiConfig.APPROVED_WORKPLACE_NETWORKS if WiFiConfig.WIFI_VERIFICATION_ENABLED else "disabled"
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

@router.get("/debug/test-wifi")
async def test_wifi_validation(ssid: str = "TestNetwork"):
    """Test endpoint to check WiFi validation logic"""
    if not ServerConfig.ENABLE_DEBUG_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Debug endpoints disabled")
        
    is_valid, message, verified_network = validate_workplace_location(ssid)
    
    return {
        "ssid_tested": ssid,
        "is_valid": is_valid,
        "message": message,
        "verified_network": verified_network,
        "wifi_verification_enabled": WiFiConfig.WIFI_VERIFICATION_ENABLED,
        "approved_networks": WiFiConfig.APPROVED_WORKPLACE_NETWORKS,
        "approved_patterns": WiFiConfig.APPROVED_NETWORK_PATTERNS,
    }
