import uvicorn
import logging
from app.main import app # Import the FastAPI app instance from app.main
from app.core.config import ServerConfig # Import ServerConfig
from app.api.endpoints.general import generate_self_signed_cert_util

# Configure logging for the main entry point
log_level = getattr(logging, ServerConfig.LOG_LEVEL.upper())
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if ServerConfig.USE_HTTPS:
        logger.info("Attempting to ensure SSL certification...")
        generated_cert_file, generated_key_file = generate_self_signed_cert_util()
        
        if not generated_cert_file or not generated_key_file:
            logger.error("Failed to generate or find SSL certificates, falling back to HTTP")
            ServerConfig.USE_HTTPS = False
        else:
            pass
        
        # Note: SSL context creation is now handled by the lifespan in app.main
        # We just need to pass the paths to uvicorn, which are already updated in ServerConfig
        
        logger.info(f"Starting HTTPS server on port {ServerConfig.SSL_PORT}...")
        logger.info(f"API Documentation: https://localhost:{ServerConfig.SSL_PORT}/docs")
        logger.info(f"Mobile apps should connect to: https://your-pi-ip:{ServerConfig.SSL_PORT}")
        logger.info(f"WiFi Config Admin: https://localhost:{ServerConfig.SSL_PORT}/admin/wifi-config")
        logger.info("⚠️  You'll need to accept the self-signed certificate warning")
        
        uvicorn.run(
            app, 
            host=ServerConfig.HOST, 
            port=ServerConfig.SSL_PORT,
            ssl_keyfile=ServerConfig.SSL_KEY_FILE,
            ssl_certfile=ServerConfig.SSL_CERT_FILE,
            log_level=ServerConfig.LOG_LEVEL.lower(),
            workers=ServerConfig.WORKERS if ServerConfig.WORKERS > 1 else None
        )
    else:
        logger.info(f"Starting HTTP server on port {ServerConfig.PORT}...")
        logger.info(f"API Documentation: http://localhost:{ServerConfig.PORT}/docs")
        logger.info(f"WiFi Config Admin: http://localhost:{ServerConfig.PORT}/admin/wifi-config")
        logger.warning("⚠️  HTTP mode - mobile apps may have connection issues")
        
        uvicorn.run(
            app, 
            host=ServerConfig.HOST, 
            port=ServerConfig.PORT, 
            log_level=ServerConfig.LOG_LEVEL.lower(),
            workers=ServerConfig.WORKERS if ServerConfig.WORKERS > 1 else None
        )
