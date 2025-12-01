import tkinter as tk
from tkinter import ttk
import queue
from queue import Queue

class AngleDisplay:
    def __init__(self, window_title="Head Sensor Angles"):
        self.root = tk.Tk()
        self.root.title(window_title)
        self.root.geometry("800x100") 
        
        # Configure styles for the labels
        style = ttk.Style()
        style.configure("Value.TLabel", font=('Arial', 16, 'bold'))
        style.configure("Title.TLabel", font=('Arial', 14))
        
        # Create a single frame to hold all values
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(expand=True)
        
        # Size for each box
        box_width = 200
        box_height = 80
        
        # Create colored frames for each value with fixed size
        yaw_frame = tk.Frame(main_frame, bg='#4a90e2', width=box_width, height=box_height)
        yaw_frame.pack(side=tk.LEFT, padx=20)
        yaw_frame.pack_propagate(False)  # Prevent frame from resizing with content
        
        roll_frame = tk.Frame(main_frame, bg='#50c878', width=box_width, height=box_height)
        roll_frame.pack(side=tk.LEFT, padx=20)
        roll_frame.pack_propagate(False)
        
        pitch_frame = tk.Frame(main_frame, bg='#ff7f50', width=box_width, height=box_height)
        pitch_frame.pack(side=tk.LEFT, padx=20)
        pitch_frame.pack_propagate(False)
        
        # Center the labels within their frames
        # Yaw display
        yaw_container = tk.Frame(yaw_frame, bg='#4a90e2')
        yaw_container.place(relx=0.5, rely=0.5, anchor='center')
        ttk.Label(yaw_container, text="YAW", style="Title.TLabel", background='#4a90e2', foreground='white').pack()
        self.yaw_label = ttk.Label(yaw_container, text="0.0°", style="Value.TLabel", background='#4a90e2', foreground='white')
        self.yaw_label.pack()
        
        # Roll display
        roll_container = tk.Frame(roll_frame, bg='#50c878')
        roll_container.place(relx=0.5, rely=0.5, anchor='center')
        ttk.Label(roll_container, text="ROLL", style="Title.TLabel", background='#50c878', foreground='white').pack()
        self.roll_label = ttk.Label(roll_container, text="0.0°", style="Value.TLabel", background='#50c878', foreground='white')
        self.roll_label.pack()
        
        # Pitch display
        pitch_container = tk.Frame(pitch_frame, bg='#ff7f50')
        pitch_container.place(relx=0.5, rely=0.5, anchor='center')
        ttk.Label(pitch_container, text="PITCH", style="Title.TLabel", background='#ff7f50', foreground='white').pack()
        self.pitch_label = ttk.Label(pitch_container, text="0.0°", style="Value.TLabel", background='#ff7f50', foreground='white')
        self.pitch_label.pack()
        
        # Configure window properties
        self.root.attributes('-topmost', True)  # Keep window on top
        self.root.resizable(False, False)  # Fix window size
        
        # Queue for thread-safe communication
        self.queue = Queue()
        
        # Flag to control window updates
        self.running = True
        
        # Start checking for updates
        self.check_queue()
        
    def check_queue(self):
        """Check for new values in the queue"""
        try:
            while self.running:
                try:
                    # Get all available updates (non-blocking)
                    yaw, roll, pitch = self.queue.get_nowait()
                    self.yaw_label.config(text=f"{yaw:+.1f}°")
                    self.roll_label.config(text=f"{roll:+.1f}°")
                    self.pitch_label.config(text=f"{pitch:+.1f}°")
                except queue.Empty:
                    break
        except tk.TclError:
            # Window was closed
            return
            
        if self.running:
            # Schedule next check
            self.root.after(50, self.check_queue)
    
    def update_values(self, yaw, roll, pitch):
        """Add new values to the queue"""
        if self.running:
            self.queue.put((yaw, roll, pitch))
    
    def close(self):
        """Close the window and stop the event loop"""
        self.running = False
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass

        
def update_display_safe(display, yaw, roll, pitch):
    """Thread-safe way to update the display values"""
    if display and display.running:
        display.update_values(yaw, roll, pitch)