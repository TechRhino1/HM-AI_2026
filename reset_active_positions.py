"""
Script to wipe all open paper positions in MT5Client and sync StateManager.
"""
from jarvis.execution.mt5_client import MT5Client
from jarvis.application.state_manager import GLOBAL_STATE

def reset_positions():
    client = MT5Client(mode="live")
    results = client.close_all_positions()
    print(f"Closed {len(results)} open positions.")
    
    acc = client.get_account_snapshot()
    pos = client.get_open_positions()
    GLOBAL_STATE.sync_broker_state(acc, pos)
    print("Central StateManager updated. Open positions count:", len(pos))

if __name__ == "__main__":
    reset_positions()
