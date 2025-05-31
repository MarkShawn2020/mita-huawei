import asyncio
import websockets
import json
import os
import datetime
import httpx  # Using httpx for async HTTP requests
import dotenv
dotenv.load_dotenv()

# --- Alibaba Cloud Configuration ---
# Best to use environment variables or a config file for these
ALIBABA_CLOUD_ACCESS_KEY_ID = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID')
ALIBABA_CLOUD_ACCESS_KEY_SECRET = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
APP_KEY = os.environ.get('TINGWU_APP_KEY') # Replace with your AppKey from Tingwu console
TINGWU_REGION = "cn-beijing" # Or your service region
TINGWU_API_ENDPOINT = f"tingwu.{TINGWU_REGION}.aliyuncs.com"
TINGWU_API_VERSION = "2023-09-30"

# --- Global State for Alibaba Connection (Simplified for one client) ---
alibaba_ws_connection = None
alibaba_task_id = None
alibaba_meeting_join_url = None

# --- Helper for Alibaba Cloud HTTP API calls ---
# Note: For production, you'd use the Alibaba Cloud SDK for proper signature generation.
# This is a simplified version for CreateTask and StopTask.
# The SDK handles signing which is complex.
# For this minimal example, we might hit issues if direct HTTP calls without SDK signing are not permitted
# or if the SDK is mandatory for authentication.
# The Python SDK example from the docs uses `aliyunsdkcore.client.AcsClient` which handles signing.
# Replicating that signing here is complex. Let's assume for now we can get away with a simple signed request
# or focus on the WebSocket part, assuming Task creation might be done manually or via another script for pure minimal WS test.

# For a TRULY minimal test of the WSS part, you might manually create a task using their example Python script
# (from 实时语音 api.md) and then paste the MeetingJoinUrl directly into this proxy.
# But let's try to include task creation.

async def create_tingwu_task():
    global alibaba_task_id, alibaba_meeting_join_url

    url = f"https://{TINGWU_API_ENDPOINT}/openapi/tingwu/v2/tasks?type=realtime"
    
    # Body from the Alibaba documentation
    body = {
        'AppKey': APP_KEY,
        'Input': {
            'Format': 'pcm',  # We'll send PCM from TouchDesigner
            'SampleRate': 16000, # Standard for speech
            'SourceLanguage': 'cn', # Or 'en', 'yue', etc.
            'TaskKey': 'td_task_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
            'ProgressiveCallbacksEnabled': False # Keep it simple
        },
        'Parameters': {
            'Transcription': {
                'DiarizationEnabled': False, # Keep it simple
                'OutputLevel': 2 # Get intermediate results
            },
            # 'TranslationEnabled': False # Optional
        }
    }

    # This is where the official SDK would handle authentication and signing.
    # Doing it manually with httpx is tricky.
    # For a quick test, consider using the Alibaba Python SDK directly to create the task
    # and then just use the MeetingJoinUrl in this script.
    # If you must use httpx, you'd need to implement the signing process:
    # https://help.aliyun.com/document_detail/29475.html (older, but gives idea)
    # For simplicity, let's assume you'll get MeetingJoinUrl from their Python example first.
    
    # --- Placeholder: Manually get MeetingJoinUrl and TaskId for now ---
    # print("Please run the Alibaba `CreateTask` Python script from their docs.")
    # alibaba_meeting_join_url = input("Paste MeetingJoinUrl (wss://...): ")
    # alibaba_task_id = input("Paste TaskId: ")
    # if not (alibaba_meeting_join_url and alibaba_task_id):
    #     print("MeetingJoinUrl and TaskId are required.")
    #     return False
    # print(f"Using MeetingJoinUrl: {alibaba_meeting_join_url}")
    # print(f"Using TaskId: {alibaba_task_id}")
    # return True
    # --- End Placeholder ---

    # --- Attempting with httpx (will likely fail without proper signing) ---
    # You'd need to build a proper signed request if not using the SDK
    # For this example, let's focus on getting the WSS part working assuming you have the URL.
    # To make this example runnable, I'll skip the actual HTTP call for task creation.
    # You should run the Python example from "实时语音 api.md" to get the URL.
    
    print("ERROR: HTTP Task Creation with raw httpx is complex due to signing.")
    print("Please run the `CreateTask` Python script from '实时语音 api.md' using the Alibaba SDK.")
    print("Then, hardcode or input the `MeetingJoinUrl` and `TaskId` below.")
    # Example (replace with actual values after running their script):
    # alibaba_meeting_join_url = "wss://tingwu-realtime-cn-beijing.aliyuncs.com/api/ws/v1?mc=......."
    # alibaba_task_id = "your_task_id_from_create_task_response"
    
    # --- For this demo, you MUST get these values by running the official SDK script ---
    # --- and paste them here or modify the script to input them ---
    if not ALIBABA_CLOUD_ACCESS_KEY_ID or not ALIBABA_CLOUD_ACCESS_KEY_SECRET or APP_KEY == "YOUR_TINGWU_APP_KEY":
        print("ERROR: Alibaba Cloud credentials or AppKey not set. Please configure them.")
        return False
        
    temp_meeting_join_url = input("Paste the MeetingJoinUrl obtained from Alibaba's CreateTask SDK script: ")
    temp_task_id = input("Paste the TaskId obtained: ")

    if not temp_meeting_join_url.startswith("wss://") or not temp_task_id:
        print("Invalid MeetingJoinUrl or TaskId provided.")
        return False
    
    alibaba_meeting_join_url = temp_meeting_join_url
    alibaba_task_id = temp_task_id
    print(f"Proceeding with manually entered MeetingJoinUrl: {alibaba_meeting_join_url}")
    return True
    # --- End of section requiring manual input ---


async def stop_tingwu_task():
    global alibaba_task_id
    if not alibaba_task_id:
        print("No active task to stop.")
        return True # Or false if you want to indicate an issue

    print(f"Stopping Tingwu Task: {alibaba_task_id}")
    # Similar to CreateTask, stopping also requires a signed HTTP PUT request.
    # Again, the Alibaba SDK is the recommended way.
    # url = f"https://{TINGWU_API_ENDPOINT}/openapi/tingwu/v2/tasks?type=realtime&operation=stop"
    # body = {
    #     'AppKey': APP_KEY,
    #     'Input': {
    #         'TaskId': alibaba_task_id
    #     }
    # }
    # For now, we'll just log it. You should implement this with the SDK.
    print("StopTask HTTP call placeholder. Implement with Alibaba SDK if needed.")
    print("Run the 'End Task' Python script from '实时语音 api.md' with the TaskId if you need to formally stop it.")
    return True


async def alibaba_client_handler(td_websocket):
    """Manages the WebSocket connection to Alibaba Cloud."""
    global alibaba_ws_connection, alibaba_task_id, alibaba_meeting_join_url

    if not alibaba_meeting_join_url:
        print("Alibaba MeetingJoinUrl not available. Cannot connect.")
        return

    try:
        async with websockets.connect(alibaba_meeting_join_url, ssl=True) as ali_ws:
            alibaba_ws_connection = ali_ws
            print(f"Connected to Alibaba: {alibaba_meeting_join_url}")

            # 1. Send StartTranscription
            start_transcription_msg = {
                "header": {
                    "name": "StartTranscription",
                    "namespace": "SpeechTranscriber",
                },
                "payload": {
                    "format": "pcm", # Must match what CreateTask specified and what TD sends
                    "sample_rate": 16000, # Must match
                    # Add other params from docs if needed, e.g., enable_intermediate_result
                }
            }
            await ali_ws.send(json.dumps(start_transcription_msg))
            print("Sent StartTranscription to Alibaba.")

            # 2. Listen for messages from Alibaba and forward to TouchDesigner
            #    AND listen for audio from TouchDesigner and forward to Alibaba
            async def forward_audio_to_alibaba():
                # This task will be cancelled when the outer handler finishes
                try:
                    while True:
                        # This is a conceptual loop. The actual audio comes from td_websocket_handler
                        # We need a queue or shared mechanism here.
                        # For simplicity, we'll have td_websocket_handler send directly.
                        await asyncio.sleep(0.01) # Keep alive, but logic is in td_websocket_handler
                except asyncio.CancelledError:
                    print("forward_audio_to_alibaba task cancelled.")

            async def listen_to_alibaba_and_forward_to_td():
                try:
                    async for message_str in ali_ws:
                        print(f"Alibaba < {message_str[:200]}...") # Log snippet
                        try:
                            # Forward to TouchDesigner client
                            await td_websocket.send(message_str)
                        except websockets.exceptions.ConnectionClosed:
                            print("TouchDesigner connection closed while trying to send Alibaba message.")
                            break
                        except Exception as e:
                            print(f"Error forwarding message to TouchDesigner: {e}")
                except websockets.exceptions.ConnectionClosedError as e:
                    print(f"Alibaba connection closed unexpectedly (read): {e.code} {e.reason}")
                except websockets.exceptions.ConnectionClosedOK:
                    print("Alibaba connection closed normally (read).")
                except asyncio.CancelledError:
                    print("listen_to_alibaba_and_forward_to_td task cancelled.")
                except Exception as e:
                    print(f"Error in listen_to_alibaba_and_forward_to_td: {e}")


            # Run both tasks concurrently
            listener_task = asyncio.create_task(listen_to_alibaba_and_forward_to_td())
            # audio_forwarder_task = asyncio.create_task(forward_audio_to_alibaba())
            # await asyncio.gather(listener_task, audio_forwarder_task)
            await listener_task # Audio is sent directly by td_websocket_handler

    except websockets.exceptions.InvalidURI:
        print(f"Invalid Alibaba WebSocket URI: {alibaba_meeting_join_url}")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Alibaba connection closed unexpectedly (connect): {e.code} {e.reason}")
    except ConnectionRefusedError:
        print(f"Alibaba connection refused: {alibaba_meeting_join_url}")
    except Exception as e:
        print(f"Error connecting to or handling Alibaba WebSocket: {e}")
    finally:
        if alibaba_ws_connection and alibaba_ws_connection.open:
            stop_transcription_msg = {
                "header": {
                    "name": "StopTranscription",
                    "namespace": "SpeechTranscriber",
                },
                "payload": {}
            }
            print("Sending StopTranscription to Alibaba.")
            await alibaba_ws_connection.send(json.dumps(stop_transcription_msg))
            await alibaba_ws_connection.close()
        alibaba_ws_connection = None
        print("Alibaba client handler finished.")


async def td_websocket_handler(websocket, path):
    """Handles WebSocket connection from TouchDesigner."""
    global alibaba_ws_connection, alibaba_task_id

    print(f"TouchDesigner client connected from {websocket.remote_address}")
    alibaba_handler_task = None

    try:
        async for message in websocket:
            if isinstance(message, str):
                print(f"TD < (str): {message}")
                try:
                    data = json.loads(message)
                    if data.get("command") == "start":
                        print("TD requested START")
                        if not alibaba_task_id: # Create task if not already done
                            if not await create_tingwu_task():
                                await websocket.send(json.dumps({"error": "Failed to create Tingwu task."}))
                                return
                        
                        if alibaba_ws_connection and alibaba_ws_connection.open:
                            print("Already connected to Alibaba. Re-sending StartTranscription might be needed if it was a pause.")
                        else:
                            if alibaba_handler_task: # Clean up old task if any
                                alibaba_handler_task.cancel()
                                try:
                                    await alibaba_handler_task
                                except asyncio.CancelledError:
                                    pass
                            # Start the Alibaba client connection
                            alibaba_handler_task = asyncio.create_task(alibaba_client_handler(websocket))
                        await websocket.send(json.dumps({"status": "Alibaba connection process initiated."}))

                    elif data.get("command") == "stop":
                        print("TD requested STOP")
                        if alibaba_handler_task:
                            alibaba_handler_task.cancel()
                            try:
                                await alibaba_handler_task # Allow cleanup within alibaba_client_handler
                            except asyncio.CancelledError:
                                print("Alibaba handler task was cancelled by TD stop.")
                            alibaba_handler_task = None # Reset
                        # Formally stop the task on Alibaba's side (HTTP)
                        # await stop_tingwu_task() # This is a placeholder for SDK call
                        # alibaba_task_id = None # Reset task ID
                        # alibaba_meeting_join_url = None
                        print("Stop command processed. If task was running, it should be stopping/stopped.")
                        await websocket.send(json.dumps({"status": "Stop command processed."}))
                        # For a full stop and ability to restart, you might need to clear alibaba_task_id etc.
                        # and re-run CreateTask. The current logic is more like a pause/resume.
                        # For a true stop, you'd close the ali_ws and then call the StopTask HTTP endpoint.

                except json.JSONDecodeError:
                    print(f"TD < (str, not JSON): {message}")
                except Exception as e:
                    print(f"Error processing TD string message: {e}")

            elif isinstance(message, bytes):
                # This is audio data from TouchDesigner
                # print(f"TD < (bytes): {len(message)} bytes")
                if alibaba_ws_connection and alibaba_ws_connection.open:
                    try:
                        await alibaba_ws_connection.send(message)
                    except websockets.exceptions.ConnectionClosed:
                        print("Alibaba connection closed. Cannot send audio.")
                        # Optionally try to reconnect or notify TD
                        if alibaba_handler_task: alibaba_handler_task.cancel() # Stop this handler
                        alibaba_handler_task = None
                        await websocket.send(json.dumps({"error": "Alibaba connection lost."}))
                        break # Exit this client's loop
                # else:
                #     print("Alibaba WS not connected. Discarding audio.")
    
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"TouchDesigner connection closed: {e.code} {e.reason}")
    except websockets.exceptions.ConnectionClosedOK:
        print("TouchDesigner connection closed normally.")
    except Exception as e:
        print(f"Error in TouchDesigner handler: {e}")
    finally:
        print("TouchDesigner client disconnected.")
        if alibaba_handler_task:
            print("Cleaning up Alibaba handler task due to TD disconnect.")
            alibaba_handler_task.cancel()
            try:
                await alibaba_handler_task
            except asyncio.CancelledError:
                pass
        # If TD disconnects, we might want to stop the Alibaba task too,
        # or leave it running for a bit for potential reconnection.
        # For simplicity, here it stops the current ali_ws stream.
        # To fully stop the billable task, call stop_tingwu_task().

async def main():
    # --- IMPORTANT ---
    # Set these environment variables before running, or hardcode them (not recommended for secrets)
    # export ALIBABA_CLOUD_ACCESS_KEY_ID="YOUR_ID"
    # export ALIBABA_CLOUD_ACCESS_KEY_SECRET="YOUR_SECRET"
    # And ensure APP_KEY is set above.
    if not ALIBABA_CLOUD_ACCESS_KEY_ID or not ALIBABA_CLOUD_ACCESS_KEY_SECRET or APP_KEY == "YOUR_TINGWU_APP_KEY":
        print("CRITICAL ERROR: Missing Alibaba Cloud credentials or AppKey.")
        print("Please set ALIBABA_CLOUD_ACCESS_KEY_ID and ALIBABA_CLOUD_ACCESS_KEY_SECRET environment variables,")
        print("and update the APP_KEY in the script.")
        return

    host = "localhost"
    port = 8765 # Port for TouchDesigner to connect to
    
    print(f"Starting WebSocket proxy server on ws://{host}:{port}")
    server = await websockets.serve(td_websocket_handler, host, port)
    await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped manually.")