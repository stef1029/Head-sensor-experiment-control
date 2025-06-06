import tkinter as tk
import time
import threading
import keyboard
from colorama import init, Fore, Back, Style

class TimerApp:
    def __init__(self, root):
        self.start_time = time.time()
        self.root = root
        self.root.title("Timer")
        self.root.geometry("200x100+0+0")
        self.label = tk.Label(root, text="00:00", font=("Helvetica", 24))
        self.label.pack(expand=True)
        self.update_time()
        self.check_esc_key()

    def update_time(self):
        elapsed_time = time.time() - self.start_time
        minutes, seconds = divmod(int(elapsed_time), 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        self.label.config(text=time_str)
        self.root.after(1000, self.update_time)  # Update every second

    def check_esc_key(self):
        if keyboard.is_pressed("del"):
            self.root.quit()
        else:
            self.root.after(100, self.check_esc_key)

def run_timer():
    root = tk.Tk()
    app = TimerApp(root)
    root.mainloop()

if __name__ == "__main__":
    run_timer()
    print(Fore.MAGENTA + "Timer:" + Style.RESET_ALL + "Timer window stopped.")
