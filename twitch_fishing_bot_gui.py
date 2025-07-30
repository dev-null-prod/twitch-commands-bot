import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import socket
import threading
import time
import random
import json
import webbrowser
import os

SETTINGS_FILE = "settings.json"
TOKEN_URL = "https://twitchtokengenerator.com/"

class TwitchFishingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Fishing Bot")

        # === SETTINGS VARIABLES ===
        self.nick = tk.StringVar()
        self.token = tk.StringVar()
        self.channel = tk.StringVar()
        self.fish_min_delay = tk.IntVar(value=10000)
        self.fish_max_delay = tk.IntVar(value=60000)
        self.join_min_delay = tk.IntVar(value=5000)
        self.join_max_delay = tk.IntVar(value=20000)
        self.connection_status = tk.StringVar(value="Disconnected")

        self.load_settings()

        # === GUI ===
        top_frame = tk.Frame(root)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        tk.Label(top_frame, text="Nickname:").grid(row=0, column=0, sticky='w')
        tk.Entry(top_frame, textvariable=self.nick).grid(row=0, column=1, sticky='we')

        tk.Label(top_frame, text="Channel:").grid(row=0, column=2, padx=(10, 0), sticky='w')
        tk.Entry(top_frame, textvariable=self.channel).grid(row=0, column=3, sticky='we')

        top_frame.columnconfigure(1, weight=1)
        top_frame.columnconfigure(3, weight=1)

        token_frame = tk.Frame(root)
        token_frame.pack(fill=tk.X, padx=10)
        tk.Label(token_frame, text="Access Token:").pack(side=tk.LEFT)
        tk.Entry(token_frame, textvariable=self.token).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(token_frame, text="Get Token", command=lambda: webbrowser.open(TOKEN_URL)).pack(side=tk.LEFT)

        delay_frame = tk.Frame(root)
        delay_frame.pack(padx=10, pady=5)

        tk.Label(delay_frame, text="!fish delay (ms):").grid(row=0, column=0, sticky='w')
        tk.Entry(delay_frame, textvariable=self.fish_min_delay, width=8).grid(row=0, column=1)
        tk.Label(delay_frame, text="to").grid(row=0, column=2)
        tk.Entry(delay_frame, textvariable=self.fish_max_delay, width=8).grid(row=0, column=3)

        tk.Label(delay_frame, text="!join delay (ms):").grid(row=1, column=0, sticky='w')
        tk.Entry(delay_frame, textvariable=self.join_min_delay, width=8).grid(row=1, column=1)
        tk.Label(delay_frame, text="to").grid(row=1, column=2)
        tk.Entry(delay_frame, textvariable=self.join_max_delay, width=8).grid(row=1, column=3)

        self.start_btn = tk.Button(root, text="Start Bot", command=self.toggle_bot, width=25)
        self.start_btn.pack(pady=5)

        tk.Label(root, textvariable=self.connection_status, fg="green").pack()

        self.log_output = ScrolledText(root, state="disabled", height=25, wrap=tk.WORD)
        self.log_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        input_frame = tk.Frame(root)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        self.message_entry = tk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind("<Return>", lambda event: self.send_custom_message())

        self.send_btn = tk.Button(input_frame, text="Send Message", command=self.send_custom_message)
        self.send_btn.pack(side=tk.LEFT, padx=(5, 0))

        self.sock = None
        self.bot_running = False

    def log(self, msg):
        self.log_output.configure(state="normal")
        if self.nick.get().lower() in msg.lower():
            self.log_output.insert(tk.END, msg + "\n", ("highlight",))
            self.log_output.tag_config("highlight", foreground="green")
        elif "[LOG]" in msg:
            self.log_output.insert(tk.END, msg + "\n", ("log",))
            self.log_output.tag_config("log", foreground="blue")
        else:
            self.log_output.insert(tk.END, msg + "\n")
        self.log_output.configure(state="disabled")
        self.log_output.yview(tk.END)

    def toggle_bot(self):
        if not self.bot_running:
            self.save_settings()
            threading.Thread(target=self.start_bot, daemon=True).start()
        else:
            self.stop_bot()

    def start_bot(self):
        try:
            token = self.token.get().strip()
            if not token.startswith("oauth:"):
                token = "oauth:" + token

            self.sock = socket.socket()
            self.sock.connect(("irc.chat.twitch.tv", 6667))
            self.sock.send(f"PASS {token}\r\n".encode("utf-8"))
            self.sock.send(f"NICK {self.nick.get()}\r\n".encode("utf-8"))
            self.sock.send(f"JOIN #{self.channel.get()}\r\n".encode("utf-8"))
            self.bot_running = True
            self.connection_status.set("Connected")
            self.log("[LOG] Connected to chat.")
            self.send_message("!fish")  # Send !fish on connect
            threading.Thread(target=self.listen, daemon=True).start()
        except Exception as e:
            self.log(f"[LOG] Connection error: {e}")
            self.connection_status.set("Disconnected")

    def stop_bot(self):
        self.bot_running = False
        if self.sock:
            self.sock.close()
        self.connection_status.set("Disconnected")
        self.log("[LOG] Bot stopped.")

    def listen(self):
        while self.bot_running:
            try:
                resp = self.sock.recv(2048).decode("utf-8", errors="ignore")
                if resp.startswith("PING"):
                    self.sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                    continue

                for line in resp.strip().split("\r\n"):
                    self.log(line)
                    if f"{self.channel.get().lower()}.tmi.twitch.tv privmsg #{self.channel.get().lower()} :@{self.nick.get().lower()} you caught a" in line.lower():
                        threading.Thread(target=self.delayed_fish, daemon=True).start()
                    elif "action pogchamp a multi-raffle has begun" in line.lower():
                        threading.Thread(target=self.delayed_join, daemon=True).start()
            except Exception as e:
                self.log(f"[LOG] Listen error: {e}")
                break

    def delayed_fish(self):
        delay = random.randint(self.fish_min_delay.get(), self.fish_max_delay.get()) / 1000.0
        self.log(f"[LOG] Scheduling !fish in {delay:.2f}s")
        time.sleep(delay)
        self.send_message("!fish")

    def delayed_join(self):
        delay = random.randint(self.join_min_delay.get(), self.join_max_delay.get()) / 1000.0
        self.log(f"[LOG] Scheduling !join in {delay:.2f}s")
        time.sleep(delay)
        self.send_message("!join")

    def send_message(self, msg):
        if self.sock:
            self.sock.send(f"PRIVMSG #{self.channel.get()} :{msg}\r\n".encode("utf-8"))
            self.log(f"> {msg}")

    def send_custom_message(self):
        msg = self.message_entry.get().strip()
        if msg:
            self.send_message(msg)
            self.message_entry.delete(0, tk.END)

    def save_settings(self):
        data = {
            "nick": self.nick.get(),
            "token": self.token.get(),
            "channel": self.channel.get(),
            "fish_min_delay": self.fish_min_delay.get(),
            "fish_max_delay": self.fish_max_delay.get(),
            "join_min_delay": self.join_min_delay.get(),
            "join_max_delay": self.join_max_delay.get()
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            for k, v in data.items():
                var = getattr(self, k, None)
                if isinstance(var, (tk.StringVar, tk.IntVar)):
                    var.set(v)

if __name__ == "__main__":
    root = tk.Tk()
    app = TwitchFishingBotGUI(root)
    root.mainloop()
