import json
import os
import logging
import re  # <--- Added Regex for cleaning
from typing import Dict, Any, List

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

# Importing State schema .
from backend.src.graph.state import VideoAuditState, ComplianceIssue

# Importing Service
from backend.src.services.video_indexer import VideoIndexerService

# Configuring Logger
logger = logging.getLogger("brand-guardian")
logging.basicConfig(level=logging.INFO)

# --- NODE 1: THE INDEXER ---
# BELOW FUNCTION RESPONSIBLE FOR DOWNLOADING, UPLOADING, AND EXTRACTING INSIGHTS FROM VIDEO 
# In short : VIDEO --> TEXT
def index_video_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Downloads YouTube video, uploads to Azure VI (Video Indexer), and extracts insights.
    Args :
      - state: VideoAuditState - The current state of the video audit process.
    Returns:
      - Dict[str, Any]: A dictionary containing the extracted transcript, OCR text, and any errors encountered during processing.
    """
    video_url = state.get("video_url")
    video_id_input = state.get("video_id", "vid_demo")
    
    logger.info(f"--- [Node: Indexer] Processing: {video_url} ---")
    
    local_filename = "temp_audit_video.mp4"
    
    try:
        vi_service = VideoIndexerService()
        
        # 1. DOWNLOADING THE VIDEO
        if "youtube.com" in video_url or "youtu.be" in video_url: # Checking for valid YouTube URL
            local_path = vi_service.download_youtube_video(video_url, output_path=local_filename)
        else:
            raise Exception("Please provide a valid YouTube URL for this test.")

        # 2. UPLOADING TO AZURE VIDEO INDEXER
        azure_video_id = vi_service.upload_video(local_path, video_name=video_id_input)
        logger.info(f"Upload Success. Azure ID: {azure_video_id}")
        
        # 3. CLEANING UP
        if os.path.exists(local_path):
            os.remove(local_path) # Once video is uploaded to Azure, we can delete the local copy to save space.

        # 4. WAITING TIME FOR PROCESSING (ASYNC)
        raw_insights = vi_service.wait_for_processing(azure_video_id)
        
        # 5. EXTRACTING CLEAN DATA FROM RAW INSIGHTS
        clean_data = vi_service.extract_data(raw_insights)
        
        logger.info("--- [Node: Indexer] Extraction Complete ---")
        return clean_data

    except Exception as e:
        logger.error(f"Video Indexer Failed: {e}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
            "transcript": "", 
            "ocr_text": []
        }

# --- NODE 2: THE COMPLIANCE AUDITOR ---
def audit_content_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Performs Retrieval-Augmented Generation (RAG) to audit the content.
    Args:
      - state: VideoAuditState - The current state of the video audit process.
    Returns:
      - Dict[str, Any]: A dictionary containing the compliance results, final status, and final report. If an error occurs, it returns the error message and a FAIL status.
    """
    logger.info("--- [Node: Auditor] querying Knowledge Base & LLM ---")
    
    transcript = state.get("transcript", "")
    
    if not transcript:
        logger.warning("No transcript available. Skipping Audit.")
        return {
            "final_status": "FAIL",
            "final_report": "Audit skipped because video processing failed (No Transcript)."
        }

    # Initializing Azure Service Clients
    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.0
    )

    embeddings = AzureOpenAIEmbeddings(
        azure_deployment="text-embedding-3-small",
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )

    vector_store = AzureSearch(
        azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key=os.getenv("AZURE_SEARCH_API_KEY"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        embedding_function=embeddings.embed_query # We also need to embed the query (user message) for similarity search
    )
    
    # RAG Retrieval
    ocr_text = state.get("ocr_text", []) # Extracting OCR text from the state, defaulting to an empty list if not present
    query_text = f"{transcript} {' '.join(ocr_text)}"
    docs = vector_store.similarity_search(query_text, k=3) # k=3 : number of top documents to retrieve for context
    
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])
    
    # --- UPDATED PROMPT WITH STRICT SCHEMA ---
    system_prompt = f"""
    You are a Senior Brand Compliance Auditor.
    
    OFFICIAL REGULATORY RULES:
    {retrieved_rules}
    
    INSTRUCTIONS:
    1. Analyze the Transcript and OCR text below.
    2. Identify ANY violations of the rules.
    3. Return strictly JSON in the following format:
    
    {{
        "compliance_results": [
            {{
                "category": "Claim Validation",
                "severity": "CRITICAL",
                "description": "Explanation of the violation..."
            }}
        ],
        "status": "FAIL", 
        "final_report": "Summary of findings..."
    }}

    If no violations are found, set "status" to "PASS" and "compliance_results" to [].
    """

    user_message = f"""
    VIDEO METADATA: {state.get('video_metadata', {})}
    TRANSCRIPT: {transcript}
    ON-SCREEN TEXT (OCR): {ocr_text}
    """

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])
        
        # --- FIX: Cleaning Markdown if present (```json ... ```) ---
        content = response.content
        if "```" in content:
            # Regex to find JSON inside code blocks
            content = re.search(r"```(?:json)?(.*?)```", content, re.DOTALL).group(1)
            
        audit_data = json.loads(content.strip())
        
        return {
            "compliance_results": audit_data.get("compliance_results", []),
            "final_status": audit_data.get("status", "FAIL"),
            "final_report": audit_data.get("final_report", "No report generated.")
        }

    except Exception as e:
        logger.error(f"System Error in Auditor Node: {str(e)}")
        # Logging raw response to see what went wrong
        logger.error(f"Raw LLM Response: {response.content if 'response' in locals() else 'None'}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL"
        }