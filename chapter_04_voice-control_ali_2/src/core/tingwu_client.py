import os
import json
import asyncio
import websockets
import datetime
from dotenv import load_dotenv
from aliyunsdkcore.client import AcsClient
from aliyunsdktingwu.request.v20230930 import CreateTaskRequest # Using typed request


# Load environment variables from .env file located one level above src
# Adjust the path if your .env file is located elsewhere
DOTENV_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=DOTENV_PATH)

ACCESS_KEY_ID = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
ACCESS_KEY_SECRET = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
APP_KEY = os.getenv('TINGWU_APP_KEY')

# Tingwu API endpoint (confirm from latest documentation if necessary)
# Common endpoints: tingwu.cn-beijing.aliyuncs.com, tingwu.cn-beijing.aliyuncs.com
DEFAULT_REGION_ID = 'cn-beijing' # Or your project's region

# Global logger (placeholder, implement proper logging as per user rules)
def get_logger():
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

logger = get_logger()

async def create_tingwu_task():
    """Creates a Tingwu real-time transcription task."""
    if not all([ACCESS_KEY_ID, ACCESS_KEY_SECRET, APP_KEY]):
        logger.error("API keys or App Key not found. Check your .env file and variable names.")
        return None

    client = AcsClient(ACCESS_KEY_ID, ACCESS_KEY_SECRET, DEFAULT_REGION_ID)

    request = CreateTaskRequest.CreateTaskRequest() # Use the typed request object
    request.set_app_key(APP_KEY) # Corrected method name
    # Set Input parameters directly on the request object with corrected method names
    request.set_input_format('pcm')
    request.set_input_sample_rate(16000)
    request.set_input_source_language('cn')
    # request.set_Input_TaskKey('my_task_key_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')) # Optional

    # Optional: Set other parameters if needed for the specific task type
    # e.g., for real-time transcription features:
    # request.set_Parameters_Transcription_OutputLevel(2) # To get intermediate results
    # request.set_Parameters_AutoChaptersEnabled(False)

    try:
        response_str = client.do_action_with_exception(request)
        response_data = json.loads(response_str)
        logger.info(f"CreateTask Response: {json.dumps(response_data, indent=2)}")
        
        # Adjust parsing based on actual CommonRequest response structure for CreateTask
        # It might be directly response_data.get('TaskId') or nested under 'Data'
        data_field = response_data.get('Data', response_data) # Some APIs return data directly
        task_id = data_field.get('TaskId')
        meeting_join_url = data_field.get('MeetingJoinUrl')

        if not task_id or not meeting_join_url:
            logger.error(f"Failed to get TaskId or MeetingJoinUrl from response. Full response: {response_data}")
            return None
        
        return {'task_id': task_id, 'websocket_url': meeting_join_url}
    except Exception as e:
        logger.error(f"Error creating Tingwu task: {e}")
        return None

async def connect_to_websocket(websocket_url):
    """Connects to the Tingwu WebSocket and prints messages."""
    logger.info(f"Attempting to connect to WebSocket: {websocket_url}")
    try:
        async with websockets.connect(websocket_url) as websocket:
            logger.info(f"Successfully connected to WebSocket: {websocket_url}")
            # For this minimal test, we'll just listen for a few seconds
            # In a real scenario, you'd send audio data and continuously listen
            try:
                while True: # Keep connection open to listen
                    message = await websocket.recv()
                    logger.info(f"Received message: {message}")
                    # Add logic here to handle different types of messages from Tingwu
            except websockets.exceptions.ConnectionClosed as e:
                logger.info(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"Error during WebSocket communication: {e}")

    except Exception as e:
        logger.error(f"Failed to connect to WebSocket: {e}")

async def main():
    task_info = await create_tingwu_task()
    if task_info and task_info.get('websocket_url'):
        # The WebSocket URL from CreateTask might need modification or specific headers.
        # The documentation for "实时记录语音推流" should detail this.
        # For now, we assume it's a direct WebSocket URL.
        await connect_to_websocket(task_info['websocket_url'])
    else:
        logger.error("Failed to create Tingwu task or get WebSocket URL. Exiting.")

if __name__ == "__main__":
    logger.info("Starting Tingwu client minimal test...")
    asyncio.run(main())
