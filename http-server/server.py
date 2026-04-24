import os
from socket import *
from urllib.parse import unquote


def handle_response(connection_socket, status_code, content_type, content, location=None):
    if status_code.startswith("307"):
        response = f"HTTP/1.1 {status_code}\r\nContent-Type: {content_type}\r\nLocation: {location}\r\n\r\n"
    elif status_code.startswith("404"):
        response = f"HTTP/1.1 {status_code}\r\nContent-Type: {content_type}\r\n\r\n{content}"
    else:
        response = f"HTTP/1.1 {status_code}\r\nContent-Type: {content_type}\r\n\r\n"

    connection_socket.send(response.encode())

    if isinstance(content, bytes):
        connection_socket.send(content)
    elif hasattr(content, 'read'):
        connection_socket.send(content.read())


def handle_file_request(connection_socket, file_path, http_404_response_content, client_address, server_port):
    print(f"Request from {client_address[0]}:{client_address[1]} for {file_path}")
    if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            file_extension = file_path.split('.')[-1]
            content_type = content_types.get(file_extension, "application/octet-stream")
            print(
                f"200 OK - Serving {file_path} as {content_type} to {client_address[0]}:{client_address[1]} on server port {server_port}")
            handle_response(connection_socket, "200 OK", content_type, file)
    else:
        print(f"404 Not Found - {file_path} for {client_address[0]}:{client_address[1]} on server port {server_port}")
        error_content = f"""
        <html>
            <head>
                <title>Error 404</title>
            </head>
            <body>
                <p style="color:red;">The file is not found</p>
                <p>Client IP: {client_address[0]}</p>
                <p>Client Port: {client_address[1]}</p>
            </body>
        </html>
        """
        handle_response(connection_socket, "404 Not Found", "text/html", error_content)


content_types = {
    "html": "text/html",
    "css": "text/css",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "mp4": "video/mp4"
}

server_port = 9931
server_socket = socket(AF_INET, SOCK_STREAM)
server_socket.bind(('', server_port))
server_socket.listen(5)
print(f"Server started on port {server_port}")

html_dir = "html_files"
css_dir = "css_files"
imgs_dir = "images"

default_pages = ["/", "/en", "/index.html", "/main_en.html"]
default_pages_ar = ["/ar", "/main_ar.html"]

while True:
    connection_socket, client_address = server_socket.accept()
    http_request = connection_socket.recv(2048).decode()
    print(f"\nReceived request:\n{http_request}")

    if not http_request:
        connection_socket.close()
        continue

    request_lines = http_request.split('\n')
    if request_lines:
        request_line = request_lines[0].split()
        if len(request_line) >= 2:
            method, path = request_line[0], request_line[1]
            if path in default_pages:
                handle_file_request(connection_socket, os.path.join(html_dir, "main_en.html"),
                                    "", client_address, server_port)
            elif path in default_pages_ar:
                handle_file_request(connection_socket, os.path.join(html_dir, "main_ar.html"),
                                    "", client_address, server_port)
            elif path.split("?")[0] == "/myform.html" and method == "GET":
                if "?" in path:
                    query = path.split("?")[1]
                    params = query.split("&")
                    for param in params:
                        if param.startswith("image_name="):
                            file_name = unquote(param.split("=")[1])
                            file_name_lower = file_name.lower()
                            matching_files = [f for f in os.listdir(imgs_dir) if f.lower() == file_name_lower]
                            if matching_files:
                                file_path = os.path.join(imgs_dir, matching_files[0])
                                ext = matching_files[0].lower().split('.')[-1]
                                content_type = content_types.get(ext, "application/octet-stream")
                                print(
                                    f"200 OK - Serving {file_path} as {content_type} to {client_address[0]}:{client_address[1]} on server port {server_port}")
                                with open(file_path, "rb") as file:
                                    handle_response(connection_socket, "200 OK", content_type, file)
                            else:
                                if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
                                    redirect_url = f"https://www.google.com/search?tbm=isch&q={file_name}"
                                elif file_name.lower().endswith(".mp4"):
                                    redirect_url = f"https://www.google.com/search?tbm=vid&q={file_name}"
                                else:
                                    redirect_url = "https://www.google.com"
                                print(
                                    f"307 Temporary Redirect - {file_name} not found, redirecting {client_address[0]}:{client_address[1]} to {redirect_url} on server port {server_port}")
                                handle_response(connection_socket, "307 Temporary Redirect", "text/html", "",
                                                location=redirect_url)
            elif path.startswith("/css_files/"):
                file_path = os.path.normpath(os.path.join(css_dir, path[11:]))
                handle_file_request(connection_socket, file_path, "", client_address,
                                    server_port)
            elif path.startswith("/images/"):
                file_path = os.path.join(imgs_dir, path[8:])
                handle_file_request(connection_socket, file_path, "", client_address,
                                    server_port)
            else:
                file_path = os.path.join(html_dir, path[1:] if path.startswith("/") else path)
                handle_file_request(connection_socket, file_path, "", client_address,
                                    server_port)
    connection_socket.close()