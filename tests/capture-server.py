#!/usr/bin/env python3
"""Stands in for a JetDirect printer: accepts one job and writes it to a file."""

import socket
import sys

host, port, output = sys.argv[1], int(sys.argv[2]), sys.argv[3]

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((host, port))
server.listen(1)
server.settimeout(60)

print(f"capture server listening on {host}:{port}", flush=True)

conn, _ = server.accept()
with open(output, "wb") as handle:
    while True:
        chunk = conn.recv(65536)
        if not chunk:
            break
        handle.write(chunk)
conn.close()
server.close()
print("capture complete", flush=True)
