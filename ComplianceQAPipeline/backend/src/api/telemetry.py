import os           # Access environment variables (like API keys)
import logging      # Python's built-in logging system

# Azure's OpenTelemetry integration - tracks app performance, errors, requests
from azure.monitor.opentelemetry import configure_azure_monitor  

# ========== CREATING A DEDICATED LOGGER ==========
# Creating named logger specifically for telemetry-related messages
# This separates telemetry logs from your main application logs
logger = logging.getLogger("vidaudit-telemetry")
# Example log output: "vidaudit-telemetry - INFO - Azure Monitor enabled"


def setup_telemetry():
    """
    Initializes Azure Monitor OpenTelemetry.
    
    What is OpenTelemetry?
    - Industry-standard observability framework
    - Tracks: HTTP requests, database queries, errors, performance metrics
    - Sends this data to Azure Monitor (like a "flight data recorder" for your app)
    
    What does "hooks into FastAPI automatically" mean?
    - Once configured, it auto-captures every API request/response
    - No need to manually log each endpoint
    - Tracks response times, error rates, dependencies (like Azure Search calls)
    """
    
    # ========== STEP 1: RETRIEVING CONNECTION STRING ==========
    # Reading  Azure Monitor connection string from environment variables
    # Example: "InstrumentationKey=abc123;IngestionEndpoint=https://..."
    # This is like "phone number" to send telemetry data to Azure workspace
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    
    # ========== STEP 2: CHECKING IF CONFIGURED ==========
    if not connection_string:
        # If environment variable is missing/empty, telemetry won't work
        logger.warning("No Instrumentation Key found. Telemetry is DISABLED.")
        return  # Exit function early - don't try to configure Azure Monitor

    # ========== STEP 3: CONFIGURING AZURE MONITOR ==========
    try:
        # configure_azure_monitor() does the heavy lifting:
        # 1. Registers automatic instrumentation for:
        #    - HTTP requests (FastAPI endpoints)
        #    - Database calls (Azure Search queries)
        #    - Logging events
        # 2. Starts background thread to send data to Azure
        configure_azure_monitor(
            connection_string=connection_string,  # Where to send data
            logger_name="vidaudit-tracer"   # Optional: custom tracer name
        )
        # 
        logger.info(" Azure Monitor Tracking Enabled & Connected!")
        
    except Exception as e:
        # ========== ERROR HANDLING ==========
        # If configuration fails (bad connection string, network issue, etc.)
        logger.error(f"Failed to initialize Azure Monitor: {e}")
        # Note: Function doesn't raise the error - telemetry failure shouldn't crash the app