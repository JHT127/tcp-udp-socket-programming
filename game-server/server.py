import socket
import random
import threading
import time
import collections

tcp_port = 6000
udp_port = 6001
server_name = '0.0.0.0'
min_players = 2
max_players = 4
to_enter_your_guess = 10
game_duration = 60

connected_players = {}
player_guesses = {}
player_scores = collections.defaultdict(int)
game_active = False
current_secret_number = 0
range_min = 1
range_max = 100

tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcp_server.bind((server_name, tcp_port))
tcp_server.listen(max_players)

udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_server.bind((server_name, udp_port))


def broadcast_tcp_message(message):
    for player_name, (conn, _, _) in connected_players.items():
        try:
            conn.send(message.encode())
            print(f"[TCP] Sent to {player_name}: {message}")
        except:
            print(f"[TCP] Failed to send message to {player_name}")


def send_tcp_message(player_name, message):
    conn, _, _ = connected_players[player_name]
    try:
        conn.send(message.encode())
        print(f"[TCP] Sent to {player_name}: {message}")
    except:
        print(f"[TCP] Failed to send message to {player_name}")


def handle_tcp_client(conn, addr):
    global game_active

    conn.send("Welcome to Number Guessing Game!\nEnter your name: ".encode())
    print(f"[TCP] Sent welcome message to {addr}")

    player_name = conn.recv(1024).decode().strip()
    print(f"[TCP] Received name '{player_name}' from {addr}")

    if player_name in connected_players:
        conn.send("Name already taken. Please use another player name.".encode())
        print(f"[TCP] Rejected {addr} - name '{player_name}' already taken")
        conn.close()
        return

    if len(connected_players) >= max_players:
        conn.send(f"Game is full (max {max_players} players). Try again later.".encode())
        print(f"[TCP] Rejected {addr} - game is full")
        conn.close()
        return

    connected_players[player_name] = (conn, addr, None)
    print(f"[TCP] Player {player_name} joined from {addr}")

    players_needed = max(0, min_players - len(connected_players))
    welcome_msg = f"Welcome {player_name}! Waiting for {players_needed} more players to start the game.\n"
    conn.send(welcome_msg.encode())
    print(f"[TCP] Sent welcome to {player_name}, waiting for {players_needed} more players")

    broadcast_tcp_message(f"Player {player_name} has joined the game.")

    if len(connected_players) >= min_players and not game_active:
        start_game()

    while True:
        try:
            message = conn.recv(1024).decode()
            if not message:
                print(f"[TCP] Empty message from {player_name}, assuming disconnection")
                break

            if message.startswith("UDP_PORT:"):
                udp_port_str = message.split(":")[1].strip()
                try:
                    udp_port_num = int(udp_port_str)
                    player_udp_addr = (addr[0], udp_port_num)
                    connected_players[player_name] = (conn, addr, player_udp_addr)
                    print(f"[TCP] Registered UDP address for {player_name}: {player_udp_addr}")
                except:
                    print(f"[TCP] Invalid UDP port from {player_name}: {udp_port_str}")

        except ConnectionResetError:
            print(f"[TCP] Connection reset by {player_name}")
            break

    handle_player_disconnect(player_name)


def handle_player_disconnect(player_name):
    global game_active

    if player_name in connected_players:
        print(f"[TCP] Player {player_name} disconnected")
        conn, _, _ = connected_players[player_name]
        try:
            conn.close()
        except:
            pass
        del connected_players[player_name]
        broadcast_tcp_message(f"Player {player_name} has left the game.")

        if len(connected_players) < min_players and game_active:
            game_active = False
            broadcast_tcp_message("Not enough players. Game paused until more players join.")
            print(f"[Game] Game paused - not enough players after {player_name} left")


def start_game():
    global game_active, current_secret_number, range_min, range_max

    game_active = True
    current_secret_number = random.randint(range_min, range_max)

    player_names = ", ".join(connected_players.keys())
    broadcast_tcp_message(f"Game started with players: {player_names}")
    broadcast_tcp_message(
        f"Rules: Guess a number between {range_min} and {range_max}. You have {to_enter_your_guess} seconds per guess.")
    broadcast_tcp_message(f"Send your guesses to UDP port {udp_port}. First to guess correctly wins!")

    print(f"[Game] Started new game with secret number: {current_secret_number}")
    print(f"[Game] Active players: {player_names}")

    game_thread = threading.Thread(target=game_loop)
    game_thread.daemon = True
    game_thread.start()


def game_loop():
    global game_active, current_secret_number

    start_time = time.time()
    print(f"[Game] Game loop started, duration: {game_duration} seconds")

    while game_active and time.time() - start_time < game_duration:
        if len(connected_players) < min_players:
            game_active = False
            broadcast_tcp_message("Game ended: Not enough players")
            print(f"[Game] Ended - player count fell below minimum ({min_players})")
            break

        time.sleep(0.1)

    if game_active:
        game_active = False
        broadcast_tcp_message(f"Game over! Time limit reached. The secret number was {current_secret_number}.")
        print(f"[Game] Ended - time limit reached. Secret was: {current_secret_number}")

        time.sleep(5)
        if len(connected_players) >= min_players:
            print(f"[Game] Starting new round after timeout")
            start_game()


def handle_udp_messages():
    while True:
        try:
            data, addr = udp_server.recvfrom(1024)
            message = data.decode()
            print(f"[UDP] Received from {addr}: {message}")

            if not game_active:
                print(f"[UDP] Ignored guess from {addr} - game not active")
                continue

            player_name = None
            for name, (_, _, udp_addr) in connected_players.items():
                if udp_addr and udp_addr[0] == addr[0] and udp_addr[1] == addr[1]:
                    player_name = name
                    break

            if not player_name:
                print(f"[UDP] Received guess from unknown player at {addr}")
                continue

            try:
                guess = int(message)
                print(f"[UDP] Player {player_name} guessed: {guess}")

                if guess < range_min or guess > range_max:
                    warning = f"Please guess between {range_min} and {range_max}"
                    udp_server.sendto(warning.encode(), addr)
                    print(f"[UDP] Warning to {player_name}: {warning}")
                    continue

                if guess < current_secret_number:
                    udp_server.sendto("Higher".encode(), addr)
                    print(f"[UDP] Sent to {player_name}: Higher")
                elif guess > current_secret_number:
                    udp_server.sendto("Lower".encode(), addr)
                    print(f"[UDP] Sent to {player_name}: Lower")
                else:
                    udp_server.sendto("Correct".encode(), addr)
                    print(f"[UDP] Sent to {player_name}: Correct")
                    handle_correct_guess(player_name)

            except ValueError:
                invalid_msg = "Invalid guess. Please enter a number."
                udp_server.sendto(invalid_msg.encode(), addr)
                print(f"[UDP] Warning to {player_name}: {invalid_msg}")

        except Exception as e:
            print(f"[UDP] Error: {e}")


def handle_correct_guess(player_name):
    global game_active, current_secret_number

    game_active = False
    player_scores[player_name] += 1
    print(f"[Game] Player {player_name} guessed correctly: {current_secret_number}")

    broadcast_tcp_message(f"{player_name} guessed the correct number: {current_secret_number}!")

    score_message = "Current scores:\n"
    for name, score in player_scores.items():
        score_message += f"{name}: {score}\n"
    broadcast_tcp_message(score_message)
    print(f"[Game] Updated scores: {dict(player_scores)}")

    broadcast_tcp_message("New round starting in 5 seconds...")
    print(f"[Game] Starting new round in 5 seconds")
    time.sleep(5)

    if len(connected_players) >= min_players:
        start_game()


def main():
    print(f"[Server] TCP server started on {server_name}:{tcp_port}")
    print(f"[Server] UDP server started on {server_name}:{udp_port}")

    udp_thread = threading.Thread(target=handle_udp_messages)
    udp_thread.daemon = True
    udp_thread.start()

    try:
        while True:
            conn, addr = tcp_server.accept()
            print(f"[TCP] New connection from {addr}")
            client_thread = threading.Thread(target=handle_tcp_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
    finally:
        tcp_server.close()
        udp_server.close()


if __name__ == "__main__":
    main()