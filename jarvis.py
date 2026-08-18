import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.jarvis_supervisor import JARVISProcessSupervisor

def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "start"
    supervisor = JARVISProcessSupervisor()

    if cmd in ["start", "launch", "run"]:
        supervisor.start_all()
    elif cmd in ["status", "health", "info"]:
        supervisor.print_status()
    elif cmd in ["stop", "kill", "down"]:
        supervisor.stop_all()
    elif cmd in ["restart", "reload"]:
        supervisor.stop_all()
        supervisor.start_all()
    elif cmd in ["logs", "log"]:
        supervisor.print_logs()
    elif cmd in ["safe-mode", "safemode", "safe"]:
        supervisor.toggle_safe_mode()
    else:
        print(f"Unknown command: '{cmd}'")
        print("Supported commands:")
        print("  JARVIS            -> Start platform and services")
        print("  JARVIS status     -> Display service health & system metrics")
        print("  JARVIS stop       -> Safely shutdown all services")
        print("  JARVIS restart    -> Clean restart platform")
        print("  JARVIS logs       -> View live supervisor logs")
        print("  JARVIS safe-mode  -> Toggle trade execution pause")

if __name__ == "__main__":
    main()
