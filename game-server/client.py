import socket
import threading
import time
import random

tcp_server_host = "localhost"
tcp_server_port = 6000
udp_server_port = 6001

tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

udp_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_client.bind(('', 0))
my_udp_port = udp_client.getsockname()[1]

running = True
game_active = False
player_joined = False

def receive_tcp_messages():
    global running, game_active, player_joined

    while running:
        try:
            message = tcp_client.recv(1024).decode()
            if not message:
                print("Server connection closed.")
                running = False
                break

            print(message)

            if player_joined and "Game started with players" in message:
                game_active = True
            elif player_joined and "New round starting" in message:
                game_active = True
            elif "Game over" in message or "guessed the correct number" in message:
                game_active = False
            elif "Welcome" in message and "!" in message:
                player_joined = True

        except ConnectionResetError:
            print("Lost connection to server.")
            running = False
            break
        except Exception as e:
            print(f"Error receiving TCP message: {e}")
            running = False
            break

def receive_udp_messages():
    global running

    udp_client.settimeout(1.0)

    while running:
        try:
            data, addr = udp_client.recvfrom(1024)
            feedback = data.decode()
            print(f"Feedback: {feedback}")
        except socket.timeout:
            pass
        except Exception as e:
            print(f"UDP error: {e}")

def send_guesses():
    global running, game_active

    while running:
        if game_active:
            try:
                guess = input("Enter your guess (or 'quit' to exit): ")

                if guess.lower() == 'quit':
                    running = False
                    break

                udp_client.sendto(guess.encode(), (tcp_server_host, udp_server_port))

            except Exception as e:
                print(f"Error sending guess: {e}")
        else:
            time.sleep(0.5)

def main():
    global running, tcp_server_host, tcp_server_port

    try:
        tcp_server_host = input("Enter server IP (or press Enter for localhost): ")
        if not tcp_server_host:
            tcp_server_host = "localhost"

        port_input = input("Enter server TCP port (or press Enter for 6000): ")
        if port_input:
            tcp_server_port = int(port_input)

        print(f"Connecting to {tcp_server_host}:{tcp_server_port}...")
        tcp_client.connect((tcp_server_host, tcp_server_port))

        tcp_thread = threading.Thread(target=receive_tcp_messages)
        tcp_thread.daemon = True
        tcp_thread.start()

        udp_thread = threading.Thread(target=receive_udp_messages)
        udp_thread.daemon = True
        udp_thread.start()

        time.sleep(0.5)

        player_name = input("Enter your name: ")
        tcp_client.send(player_name.encode())

        time.sleep(0.5)
        tcp_client.send(f"UDP_PORT:{my_udp_port}".encode())
        print(f"Registered UDP port: {my_udp_port}")

        guess_thread = threading.Thread(target=send_guesses)
        guess_thread.daemon = True
        guess_thread.start()

        while running:
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        running = False
        try:
            tcp_client.close()
        except:
            pass
        try:
            udp_client.close()
        except:
            pass

if __name__ == "__main__":
    main()