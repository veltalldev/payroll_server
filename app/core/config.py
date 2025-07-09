
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def parse_list_env(env_var: str, default: List[str] = None) -> List[str]:
    """Parse comma-separated environment variable into list"""
    if default is None:
        default = []
        
    value = os.getenv(env_var, "")
    if not value.strip():
        return default
        
    # Split by comma and strip whitespace
    return [item.strip() for item in value.split(",") if item.strip()]

def parse_bool_env(env_var: str, default: bool = False) -> bool:
    """Parse boolean environment variable"""
    return os.getenv(env_var, str(default)).lower() in ("true", "1", "yes", "on")

class WiFiConfig:
    """WiFi Location Verification Settings from Environment"""
    
    # Enable/disable WiFi verification
    WIFI_VERIFICATION_ENABLED = parse_bool_env("WIFI_VERIFICATION_ENABLED", True)
    
    # Approved workplace networks from environment
    APPROVED_WORKPLACE_NETWORKS = parse_list_env(
        "APPROVED_WORKPLACE_NETWORKS", 
        ["YourCompanyWiFi", "YourCompanyWiFi-5G", "CompanyGuest"]
    )
    
    # Pattern matching settings
    WIFI_PATTERN_MATCHING_ENABLED = parse_bool_env("WIFI_PATTERN_MATCHING_ENABLED", True)
    APPROVED_NETWORK_PATTERNS = parse_list_env(
        "APPROVED_NETWORK_PATTERNS",
        ["YourCompany*", "Office*"]
    )
    
    # Graceful degradation settings
    ALLOW_MANUAL_OVERRIDE = parse_bool_env("ALLOW_MANUAL_OVERRIDE", True)
    NETWORK_TIMEOUT_SECONDS = int(os.getenv("NETWORK_TIMEOUT_SECONDS", "5"))
    
    # Logging settings
    LOG_ALL_WIFI_ATTEMPTS = parse_bool_env("LOG_ALL_WIFI_ATTEMPTS", True)
    ALERT_ON_FAILED_ATTEMPTS = parse_bool_env("ALERT_ON_FAILED_ATTEMPTS", True)

class ServerConfig:
    """Server Configuration from Environment"""
    
    # Server settings
    HOST = os.getenv("TIMECLOCK_HOST", "0.0.0.0")
    PORT = int(os.getenv("TIMECLOCK_PORT", "8000"))
    SSL_PORT = int(os.getenv("TIMECLOCK_SSL_PORT", "8443"))
    WORKERS = int(os.getenv("TIMECLOCK_WORKERS", "1"))
    LOG_LEVEL = os.getenv("TIMECLOCK_LOG_LEVEL", "info")
    
    # SSL/HTTPS settings
    USE_HTTPS = parse_bool_env("USE_HTTPS", True)
    SSL_CERT_FILE = os.getenv("SSL_CERT_FILE", "./certs/cert.pem")
    SSL_KEY_FILE = os.getenv("SSL_KEY_FILE", "./certs/key.pem")
    
    # SSL certificate generation settings
    SSL_CERT_DAYS = int(os.getenv("SSL_CERT_DAYS", "365"))
    SSL_CERT_COUNTRY = os.getenv("SSL_CERT_COUNTRY", "US")
    SSL_CERT_STATE = os.getenv("SSL_CERT_STATE", "CA")
    SSL_CERT_CITY = os.getenv("SSL_CERT_CITY", "City")
    SSL_CERT_ORG = os.getenv("SSL_CERT_ORG", "Timeclock")
    SSL_CERT_CN = os.getenv("SSL_CERT_CN", "timeclock.local")
    
    # Security settings
    ADMIN_SECRET = os.getenv("TIMECLOCK_ADMIN_SECRET", "your-secret-key-here")
    LOCALHOST_ONLY_ADMIN = parse_bool_env("LOCALHOST_ONLY_ADMIN", True)
    
    # Database settings
    DATABASE_PATH = os.getenv("DATABASE_PATH", "timeclock.db")
    QR_CODE_EXPIRY_MINUTES = int(os.getenv("QR_CODE_EXPIRY_MINUTES", "3"))
    
    # Development settings
    SEED_TEST_DATA = parse_bool_env("SEED_TEST_DATA", True)
    DEVELOPMENT_MODE = parse_bool_env("DEVELOPMENT_MODE", False)
    ENABLE_DEBUG_ENDPOINTS = parse_bool_env("ENABLE_DEBUG_ENDPOINTS", True)
    ENABLE_API_DOCS = parse_bool_env("ENABLE_API_DOCS", True)
    
    # CORS settings
    CORS_ORIGINS = parse_list_env("CORS_ORIGINS", ["*"])
    CORS_ALLOW_CREDENTIALS = parse_bool_env("CORS_ALLOW_CREDENTIALS", True)
    
    # App metadata
    APP_NAME = os.getenv("APP_NAME", "Timeclock System")
    APP_VERSION = os.getenv("APP_VERSION", "1.1.0")
    APP_DESCRIPTION = os.getenv("APP_DESCRIPTION", "Employee Time Tracking with WiFi Verification")

