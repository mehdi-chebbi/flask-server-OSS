from http.server import SimpleHTTPRequestHandler, HTTPServer
import socket

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == "__main__":
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    print(f"Serving HTTP on {ip_address} port 8080 (http://{ip_address}:8080/)...")
    httpd.serve_forever()
