import os
import time
import logging

# Configure professional logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MeetingIntelUtils")

class MeetingUtils:
    @staticmethod
    def ensure_storage_exists(directory_path: str):
        try:
            if not os.path.exists(directory_path):
                os.makedirs(directory_path)
                logger.info(f"Created storage directory: {directory_path}")
        except Exception as e:
            logger.error(f"Failed to create storage: {str(e)}")
            raise

    @staticmethod
    def clean_old_files(directory_path: str, max_age_seconds: int = 3600):
        """
        Deletes files older than max_age_seconds to ensure privacy compliance.
        """
        try:
            current_time = time.time()
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                if os.path.getmtime(file_path) < current_time - max_age_seconds:
                    os.remove(file_path)
                    logger.info(f"Cleaned up expired file: {filename}")
        except Exception as e:
            logger.warning(f"Cleanup error: {str(e)}")

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """
        Converts float seconds to HH:MM:SS format for MOM reporting.
        """
        try:
            return time.strftime('%H:%M:%S', time.gmtime(seconds))
        except Exception:
            return "00:00:00"