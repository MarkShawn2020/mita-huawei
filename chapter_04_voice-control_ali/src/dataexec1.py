import struct

def onTableChange(dat):
    print(f"dataexec1.py: onTableChange triggered for DAT '{dat.name}' with {dat.numRows} rows, {dat.numCols} cols.")
    if dat.numRows == 0 or dat.numCols == 0:
        print(f"dataexec1.py: DAT '{dat.name}' is empty, returning.")
        return

    # Assuming audiodevin1 is set to 16000Hz, Mono, 16-bit Fixed
    # chopto1 will have one column of integer samples
    
    # We want to send small chunks, e.g., 100ms of audio
    # 16000 samples/sec * 0.1 sec = 1600 samples
    # Each sample is 2 bytes (16-bit)
    # So, 3200 bytes per 100ms chunk.
    # The Audio Device In CHOP might already be buffering this way.
    # Let's assume we get a block of samples from the CHOP
    
    # This part is tricky without knowing exactly how Audio Device In CHOP with "16-bit fixed" outputs
    # If it's giving you one sample per row in the DAT:
    byte_data = bytearray()
    for r in range(dat.numRows):
        try:
            sample_val = int(dat[r, 0].val) # Get the integer sample
            # Pack as little-endian signed short (16-bit)
            byte_data.extend(struct.pack("<h", sample_val))
        except ValueError:
            print(f"dataexec1.py: Warning - Could not convert DAT cell {r},0 to int: '{dat[r,0].val}'")
            continue # skip if not a valid number
    
    if byte_data:
        print(f"dataexec1.py: Generated {len(byte_data)} audio bytes from {dat.numRows} samples.")
        # Send to WebSocket DAT (named 'stt_websocket_client')
        # Ensure op('stt_websocket_client') exists and is the correct path to your WebSocket client DAT
        target_ws_client = op('stt_websocket_client')
        if target_ws_client:
            target_ws_client.sendBytes(bytes(byte_data))
            print(f"dataexec1.py: Sent {len(byte_data)} audio bytes to '{target_ws_client.name}'.")
        else:
            print(f"dataexec1.py: Error - WebSocket client DAT 'stt_websocket_client' not found.")
    else:
        print(f"dataexec1.py: No byte_data generated from DAT '{dat.name}'.")
    
    # Clear the DAT to process next chunk (optional, depends on how you trigger)
    # e.g., dat.clear()
    # dat.clear() 