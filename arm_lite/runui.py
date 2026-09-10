import os
import sys
import psutil, signal, socket
import importlib.util

#the PATH to /ARM_LITE v2/arm-lite, so we can handle imports properly
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_NAME = "arm_lite"
_INIT_PATH = os.path.join(_THIS_DIR, "__init__.py")
if not os.path.isfile(_INIT_PATH):
    sys.exit(
        f"[runui] Unable to locate {_INIT_PATH}\n"
        f"[runui] Folder may be missing files, e.g. from a "
        f"partial extraction/copy."
    )
if _PACKAGE_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _PACKAGE_NAME, _INIT_PATH, submodule_search_locations=[_THIS_DIR]
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_PACKAGE_NAME] = _module
    _spec.loader.exec_module(_module)

import arm_lite.config.config as cfg
from arm_lite.ui import app, db

shdwn_requested = False
def handle_shutdown(signum, frame):
    """ARM handle SIGTERM/SIGINT for graceful shutdown"""
    global shdwn_requested
    shdwn_requested = True
    app.logger.info(f"Received shutdown signal ({signum}). Shutting down ARM_Lite.")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)    # systemd shutdown command
signal.signal(signal.SIGINT, handle_shutdown)     # keyboard interrupt

host = cfg.arm_config.get("WEBSERVER_IP")
if host == "x.x.x.x":
    ip_list = []
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET:    # AF_INET
                ip = addr.address
                if ip != "127.0.0.1":
                    ip_list.append(addr.address)
    host = ip_list[2] if ip_list else "127.0.0.1"

if __name__ == "__main__":
    port = cfg.arm_config.get("WEBSERVER_PORT")
    debug_mode = cfg.arm_config.get("DEBUG_MODE", False)
    try:
        app.logger.info(f"Starting ARM_Lite on interface address: {host}:{port}")
        with app.app_context():
            db.create_all()
        app.run(host=host, port=port, debug=debug_mode, use_reloader=False)
    except KeyboardInterrupt:
        app.logger.info("Keyboard Interrupt received, shutting down...")
    finally:
        app.logger.info("Shutdown Complete.")
