#!/bin/bash
# Lambda Web Adapter startup script.
# LWA calls this as the Lambda handler; it starts uvicorn on the port LWA expects.
exec python3 -m uvicorn handler.app:app --host 0.0.0.0 --port "${PORT:-8080}"
