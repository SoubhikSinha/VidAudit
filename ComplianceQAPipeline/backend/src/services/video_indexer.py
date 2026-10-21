'''
This is a connector between PYTHON and AZURE VIDEO INDEXER.
'''

import os
import time
import logging
import requests
import yt_dlp  # For downloading YouTube videos
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("video-indexer")

class VideoIndexerService:
    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME", "vidaudit-vidindex")
        self.credential = DefaultAzureCredential()

    def get_access_token(self):
        """Generates an ARM Access Token."""
        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            return token_object.token
        except Exception as e:
            logger.error(f"Failed to get Azure Token: {e}")
            raise

    def get_account_token(self, arm_access_token):
        """Exchanges ARM token for Video Indexer Account Token.
        Args:
            arm_access_token (str): The ARM access token obtained from Azure AD.
        Returns:
            str: The Video Indexer account access token.
        """
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get VI Account Token: {response.text}")
        return response.json().get("accessToken")

    # --- NEW FUNCTION: Downloading Video from YouTube ---
    def download_youtube_video(self, url, output_path="temp_video.mp4"):
        """Downloads YouTube video to local file.
        Args:
            url (str): The YouTube video URL.
            output_path (str): The local path to save the downloaded video.
        Returns:
            str: The path to the downloaded video file.
        """
        logger.info(f"Downloading YouTube video: {url}")
        
        ydl_opts = {
         'format': 'best',
         'outtmpl': output_path, # output template
         'quiet': False,
         'no_warnings': False,
    # Adding options:
         'extractor_args': {'youtube': {'player_client': ['android', 'web']}}, # Force YouTube to use a specific player client (Android first then web if fails)
         'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

}
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logger.info("Download complete.")
            return output_path
        except Exception as e:
            raise Exception(f"YouTube Download Failed: {str(e)}")

    # --- UPDATED FUNCTION: Uploading Local File ---
    def upload_video(self, video_path, video_name):
        """Uploads LOCAL FILE to Azure Video Indexer.
        Args:
            video_path (str): The path to the local video file.
            video_name (str): The name to assign to the video in Azure.
        Returns:
            str: The Video ID assigned by Azure Video Indexer.  
          """
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        # Constructing the API URL for uploading the video
        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
        
        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
            # We removed "videoUrl" because we are sending a file payload instead
        }
        
        logger.info(f"Uploading file {video_path} to Azure...")
        
        # Openning file in binary mode and stream it to Azure
        with open(video_path, 'rb') as video_file:
            files = {'file': video_file}
            response = requests.post(api_url, params=params, files=files)
        
        if response.status_code != 200:
            raise Exception(f"Azure Upload Failed: {response.text}")
            
        return response.json().get("id")

    def wait_for_processing(self, video_id):
        """Polls status until complete.
        Args:
            video_id (str): The Video ID assigned by Azure Video Indexer.
        Returns:
            dict: The final JSON response from Azure Video Indexer once processing is complete."""
        logger.info(f"Waiting for video {video_id} to process...")
        while True:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)
            
            url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
            params = {"accessToken": vi_token}
            response = requests.get(url, params=params)
            data = response.json()
            
            state = data.get("state")
            if state == "Processed":
                return data
            elif state == "Failed":
                raise Exception("Video Indexing Failed in Azure.")
            elif state == "Quarantined":
                raise Exception("Video Quarantined (Copyright/Content Policy Violation).")
            
            logger.info(f"Status: {state}... waiting 30s")
            time.sleep(30)

    def extract_data(self, vi_json):
        """Parses the JSON into our State format.
        Args:
            vi_json (dict): The JSON response from Azure Video Indexer.
        Returns:
            dict: A dictionary containing transcript, OCR text, and video metadata."""
        transcript_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("transcript", []):
                transcript_lines.append(insight.get("text"))
        
        ocr_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("ocr", []):
                ocr_lines.append(insight.get("text"))
                
        return {
            "transcript": " ".join(transcript_lines),
            "ocr_text": ocr_lines,
            "video_metadata": {
                "duration": vi_json.get("summarizedInsights", {}).get("duration", {}).get("seconds"),
                "platform": "youtube"
            }
        }