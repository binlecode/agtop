import subprocess
import sys
import time

def test_agtop_runs_and_handles_sigint():
    # Run agtop via subprocess, send SIGINT (Ctrl+C) and check it exits cleanly
    process = subprocess.Popen(
        [sys.executable, "-m", "agtop.agtop", "--interval", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Give it a bit more time to initialize and render the first frame
        time.sleep(4)
        
        # Send SIGINT to simulate Ctrl+C
        process.send_signal(subprocess.signal.SIGINT)
        
        # Wait for it to quit gracefully
        stdout, stderr = process.communicate(timeout=3)
        
        # Python unhandled KeyboardInterrupt normally exits with 130 (128 + SIGINT)
        # agtop has a finally block to reset terminal, so this is expected
        assert process.returncode in (0, 130)
        
        # Verify it outputted something real (the UI)
        assert "E-CPU" in stdout or "P-CPU" in stdout or "GPU" in stdout
        
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        assert False, f"agtop did not quit within timeout after SIGINT. stderr: {stderr}"

