#!/usr/bin/env python3
"""Simple TCP port forwarder.

Usage: port_forward.py <local_port> <remote_host> <remote_port>

Listens on localhost:<local_port> and forwards incoming connections to
<remote_host>:<remote_port>.

This helper is used by `start_xcom_rx.sh` to open a local port that forwards
to the Adafruit device when `ADAFRUIT_IP` is set.
"""
import sys
import socket
import threading


def handle_client(client_sock, remote_host, remote_port):
    try:
        remote = socket.create_connection((remote_host, remote_port))
    except Exception as e:
        print(f"[port_forward] Failed to connect to {remote_host}:{remote_port}: {e}")
        client_sock.close()
        return

    def forward(src, dst):
        try:
            while True:
                data = src.recv(4096)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass

    t1 = threading.Thread(target=forward, args=(client_sock, remote), daemon=True)
    t2 = threading.Thread(target=forward, args=(remote, client_sock), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    try:
        client_sock.close()
    except Exception:
        pass
    try:
        remote.close()
    except Exception:
        pass


def serve(local_port, remote_host, remote_port):
    listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind(('127.0.0.1', local_port))
    listen.listen(5)
    print(f"[port_forward] Forwarding localhost:{local_port} -> {remote_host}:{remote_port}")
    try:
        while True:
            client, addr = listen.accept()
            thr = threading.Thread(target=handle_client, args=(client, remote_host, remote_port), daemon=True)
            thr.start()
    except KeyboardInterrupt:
        print("[port_forward] Stopping")
    finally:
        try:
            listen.close()
        except Exception:
            pass


def main():
    if len(sys.argv) < 4:
        print("Usage: port_forward.py <local_port> <remote_host> <remote_port>")
        sys.exit(2)
    try:
        local_port = int(sys.argv[1])
        remote_host = sys.argv[2]
        remote_port = int(sys.argv[3])
    except Exception as e:
        print(f"Invalid args: {e}")
        sys.exit(2)
    serve(local_port, remote_host, remote_port)


if __name__ == '__main__':
    main()
