import subprocess
import os
import sys

def run_verify():
    print(f"Current PID: {os.getpid()}")
    print(f"Current Dir: {os.getcwd()}")
    
    try:
        # Run verify_routes.py
        result = subprocess.run(['python', 'verify_routes.py'], capture_output=True, text=True)
        
        with open("verify_final_out.txt", "w") as f:
            f.write("--- STDOUT ---\n")
            f.write(result.stdout)
            f.write("\n--- STDERR ---\n")
            f.write(result.stderr)
            
        print("Verification completed and saved to verify_final_out.txt")
        sys.stdout.flush()
    except Exception as e:
        print(f"Failed to run verification: {str(e)}")
        sys.stdout.flush()

if __name__ == "__main__":
    run_verify()
