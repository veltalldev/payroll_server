import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import ServerConfig, WiFiConfig # Import ServerConfig
from app.core.database import init_database, seed_test_data # Import database functions
from app.api.endpoints import general, clocking, employees, payroll, admin, pin_auth # Import all endpoint routers including pin_auth
from app.api.endpoints.general import generate_self_signed_cert_util # Import for lifespan cert generation

# Configure logging
log_level = getattr(logging, ServerConfig.LOG_LEVEL.upper())
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("=" * 60)
    logger.info(f"🚀 {ServerConfig.APP_NAME.upper()}")
    logger.info(f"Version: {ServerConfig.APP_VERSION}")
    logger.info("=" * 60)
    
    # Initialize database
    init_database()
    
    # Add test data for development
    if ServerConfig.SEED_TEST_DATA:
        from app.core.database import seed_test_pins  # Import here to avoid circular imports
        seed_test_data()
        seed_test_pins()  # NEW - Add test PINs
    
    # Log configuration
    wifi_status = "ENABLED" if WiFiConfig.WIFI_VERIFICATION_ENABLED else "DISABLED"
    logger.info(f"WiFi Verification: {wifi_status}")
    
    if WiFiConfig.WIFI_VERIFICATION_ENABLED:
        logger.info(f"Approved Networks: {WiFiConfig.APPROVED_WORKPLACE_NETWORKS}")
        logger.info(f"Pattern Matching: {'ENABLED' if WiFiConfig.WIFI_PATTERN_MATCHING_ENABLED else 'DISABLED'}")
        if WiFiConfig.WIFI_PATTERN_MATCHING_ENABLED:
            logger.info(f"Approved Patterns: {WiFiConfig.APPROVED_NETWORK_PATTERNS}")
    else:
        logger.warning("⚠️  WiFi verification is DISABLED - all locations allowed")
    
    if ServerConfig.USE_HTTPS:
        logger.info("Attempting to ensure SSL certification")
        generated_cert_file, generated_key_file = generate_self_signed_cert_util()

        if not generated_cert_file or not generated_key_file:
            logger.error("Failed to generate or find SSL certificates during startup")
            # If cert generation fails, we might want to disable HTTPS or exit
            ServerConfig.USE_HTTPS = False # Update the global config flag
        else:
            # Update paths in ServerConfig if they were generated/confirmed
            ServerConfig.SSL_CERT_FILE = generated_cert_file
            ServerConfig.SSL_KEY_FILE = generated_key_file
    
    logger.info(f"Database: {ServerConfig.DATABASE_PATH}")
    logger.info(f"HTTPS: {'ENABLED' if ServerConfig.USE_HTTPS else 'DISABLED'}")
    logger.info("=" * 60)
    logger.info("FastAPI Timeclock Server started successfully!")
    
    yield  # Server is running
    
    # Shutdown logic
    logger.info("Shutting down Timeclock Server...")


app = FastAPI(
    title=ServerConfig.APP_NAME,
    version=ServerConfig.APP_VERSION,
    description=ServerConfig.APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs" if ServerConfig.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ServerConfig.ENABLE_API_DOCS else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ServerConfig.CORS_ORIGINS,
    allow_credentials=ServerConfig.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(general.router, tags=["General"])
app.include_router(clocking.router, tags=["Clocking"])
app.include_router(employees.router, tags=["Employees"])
app.include_router(payroll.router, tags=["Payroll"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"]) # Admin endpoints typically prefixed
app.include_router(pin_auth.router, tags=["PIN Authentication"])  # NEW
