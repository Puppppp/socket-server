import socket
import os
from datetime import datetime
from email.parser import BytesParser
from email.policy import default


HOST = "127.0.0.1"
PORT = 8000

REQUEST_DIR = "request"
IMAGE_DIR = "images"


os.makedirs(REQUEST_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)


def save_request(data):
    """Save the complete HTTP request as a binary file."""

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    filename = os.path.join(REQUEST_DIR, timestamp + ".bin")

    # Avoid overwriting if two requests arrive during the same second
    counter = 1
    original_filename = filename

    while os.path.exists(filename):
        filename = os.path.join(
            REQUEST_DIR,
            f"{timestamp}-{counter}.bin"
        )
        counter += 1

    with open(filename, "wb") as f:
        f.write(data)

    print(f"[+] Request saved: {filename}")

    return filename


def find_header(data, header_name):
    """Find a header in the raw HTTP request."""

    header_end = data.find(b"\r\n\r\n")

    if header_end == -1:
        return None

    headers = data[:header_end].decode("iso-8859-1")

    for line in headers.split("\r\n"):
        if line.lower().startswith(header_name.lower() + ":"):
            return line.split(":", 1)[1].strip()

    return None


def extract_image(data):
    """Extract an image from a multipart/form-data request."""

    header_end = data.find(b"\r\n\r\n")

    if header_end == -1:
        print("[-] Could not find HTTP header/body separator.")
        return None

    header_bytes = data[:header_end]
    body = data[header_end + 4:]

    content_type = find_header(data, "Content-Type")

    if not content_type:
        print("[-] Content-Type header not found.")
        return None

    print(f"[*] Content-Type: {content_type}")

    # We only handle multipart/form-data
    if "multipart/form-data" not in content_type.lower():
        print("[-] Request is not multipart/form-data.")
        return None

    # Extract boundary
    boundary = None

    for part in content_type.split(";"):
        part = part.strip()

        if part.startswith("boundary="):
            boundary = part.split("=", 1)[1]

            if boundary.startswith('"') and boundary.endswith('"'):
                boundary = boundary[1:-1]

            break

    if not boundary:
        print("[-] Multipart boundary not found.")
        return None

    print(f"[*] Boundary: {boundary}")

    # email.parser gives us a convenient multipart parser
    fake_headers = (
        b"Content-Type: " + content_type.encode("iso-8859-1") + b"\r\n"
        b"\r\n"
    )

    message = BytesParser(policy=default).parsebytes(
        fake_headers + body
    )

    if not message.is_multipart():
        print("[-] Could not parse multipart data.")
        return None

    for part in message.iter_parts():

        disposition = part.get("Content-Disposition", "")

        if "filename=" not in disposition:
            continue

        filename = part.get_filename()

        if not filename:
            continue

        content_type = part.get_content_type()

        if not content_type.startswith("image/"):
            continue

        image_data = part.get_payload(decode=True)

        if not image_data:
            continue

        # Keep only the filename, not any directory supplied by the client
        filename = os.path.basename(filename)

        output_path = os.path.join(IMAGE_DIR, filename)

        with open(output_path, "wb") as f:
            f.write(image_data)

        print(f"[+] Image saved: {output_path}")
        print(f"[+] Image size: {len(image_data)} bytes")

        return output_path

    print("[-] No image found.")
    return None


def send_response(client_socket):
    """Send a simple HTTP response to curl."""

    response_body = b'{"message":"Request received successfully"}'

    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(response_body)).encode() + b"\r\n"
        b"Connection: close\r\n"
        b"\r\n" +
        response_body
    )

    client_socket.sendall(response)


def receive_request(client_socket):
    """Receive the complete HTTP request."""

    data = b""

    # First receive until we have the HTTP headers
    while b"\r\n\r\n" not in data:
        chunk = client_socket.recv(4096)

        if not chunk:
            break

        data += chunk

    if b"\r\n\r\n" not in data:
        return data

    header_end = data.find(b"\r\n\r\n")

    header = data[:header_end]
    body = data[header_end + 4:]

    headers = header.decode("iso-8859-1")

    content_length = 0

    for line in headers.split("\r\n"):
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            break

    # Receive the rest of the body
    while len(body) < content_length:
        chunk = client_socket.recv(4096)

        if not chunk:
            break

        body += chunk

    return header + b"\r\n\r\n" + body


def main():

    print(f"[*] Starting socket server on {HOST}:{PORT}")

    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    print("[+] Server is waiting for requests...")
    print("[+] Press Ctrl+C to stop.")

    while True:

        client_socket, client_address = server_socket.accept()

        print()
        print(f"[+] Connection from {client_address}")

        try:
            request = receive_request(client_socket)

            print(f"[*] Received {len(request)} bytes")

            # 실습 1
            save_request(request)

            # 실습 2
            extract_image(request)

            send_response(client_socket)

        except Exception as e:
            print(f"[-] Error: {e}")

        finally:
            client_socket.close()


if __name__ == "__main__":
    main()