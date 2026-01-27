"""Pretty logger wrapper."""

def log_info(msg):
    print(f"\033[32m[INFO]\033[0m {msg}", flush=True)
def log_warn(msg):
    print(f"\033[33m[WARN]\033[0m {msg}", flush=True)
def log_error(msg):
    print(f"\033[31m[ERROR]\033[0m {msg}", flush=True)