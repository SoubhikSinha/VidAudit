import operator
from typing import Annotated, List, Dict, Optional, Any, TypedDict

# Defining Schema for Single Compliance Result
class ComplianceIssue(TypedDict):
  category: str 
  description: str # Specific detail of violation
  severity: str # CRITICAL | WARNING
  timestamp: Optional[str]

'''
"ComplianceIssue" Class --> This will prevent LLM to return unstructud data. It will enforce the LLM to return structured data in the form of ComplianceIssue.
'''

# Defining the Global Graph State
'''
This defines state that gets passed around agentic workflows.
'''
class VideoAuditState(TypedDict):
  '''
  Defines the data schema for langraph execution
  This is the main container : From Initial URL to Final Report.
  '''
   # --- Input Parameters ---
  video_url: str
  video_id: str

  # --- Ingestion & Extraction Data ---
  # Optional because they are populated asynchronously by Indexer Node.
  local_file_path: Optional[str]  
  video_metadata: Dict[str, Any]  # e.g., {"duration": 15, "resolution": "1080p"}
  transcript: Optional[str]       # Full extracted speech-to-text
  ocr_text: List[str]             # List of recognized on-screen text

  # --- Analysis Output ---
  # annotated with operator.add to allow append-only updates from multiple nodes.
  # STORES THE LIST OF ALL VIOLATIONS FOUND BY AI
  compliance_results: Annotated[List[ComplianceIssue], operator.add]
  
  # --- Final Deliverables ---
  final_status: str               # "PASS" | "FAIL"
  final_report: str               # Markdown summary for frontend
  
  # --- System Observability ---
  # Appends system-level errors / crashes (e.g., API timeouts) without halting execution logic.
  errors: Annotated[List[str], operator.add]