import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
from ctypes import wintypes

# --- Windows API Definitions using ctypes ---

# Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
LWA_ALPHA = 0x2
RDW_ERASE = 0x0004
RDW_INVALIDATE = 0x0001
RDW_FRAME = 0x0400
RDW_ALLCHILDREN = 0x0080

# Function prototypes
user32 = ctypes.WinDLL('user32')
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
GetClassNameW = user32.GetClassNameW
IsWindowVisible = user32.IsWindowVisible
GetWindowLongW = user32.GetWindowLongW
SetWindowLongW = user32.SetWindowLongW
SetLayeredWindowAttributes = user32.SetLayeredWindowAttributes
RedrawWindow = user32.RedrawWindow

class ChromeTransparencyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chrome Transparency Controller")
        self.root.geometry("450x400")
        self.root.resizable(False, True)

        # Store found windows as a list of (hwnd, title) tuples
        self.chrome_windows = []

        # --- GUI Setup ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Window List
        list_frame = ttk.LabelFrame(main_frame, text="Open Chrome Windows")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        # Controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)

        self.refresh_button = ttk.Button(controls_frame, text="Refresh List", command=self.refresh_window_list)
        self.refresh_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Transparency Slider
        slider_frame = ttk.LabelFrame(main_frame, text="Transparency Level (0% = Invisible, 100% = Opaque)")
        slider_frame.pack(fill=tk.X, pady=5)
        
        self.alpha_var = tk.IntVar(value=85)
        self.slider = ttk.Scale(slider_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.alpha_var, command=self.update_slider_label)
        self.slider.pack(fill=tk.X, expand=True, padx=5, pady=(5,0))
        
        self.slider_label = ttk.Label(slider_frame, text="85%")
        self.slider_label.pack()

        # Action Buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=5)

        self.apply_button = ttk.Button(action_frame, text="Apply Transparency", command=self.apply_transparency)
        self.apply_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.reset_button = ttk.Button(action_frame, text="Reset Transparency", command=self.reset_transparency)
        self.reset_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Status Bar
        self.status_var = tk.StringVar(value="Ready. Please refresh the list.")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Initial population of the list
        self.refresh_window_list()

    def update_slider_label(self, value):
        self.slider_label.config(text=f"{int(float(value))}%")

    def _enum_windows_callback(self, hwnd, lParam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, buffer, length + 1)
                
                class_buffer = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, class_buffer, 256)

                # Find windows belonging to Chrome
                if "Chrome_WidgetWin_1" in class_buffer.value:
                    self.chrome_windows.append((hwnd, buffer.value))
        return True

    def refresh_window_list(self):
        self.status_var.set("Refreshing window list...")
        self.listbox.delete(0, tk.END)
        self.chrome_windows.clear()

        # Enumerate all top-level windows
        EnumWindows(EnumWindowsProc(self._enum_windows_callback), 0)

        if not self.chrome_windows:
            self.listbox.insert(tk.END, "No Chrome windows found.")
            self.status_var.set("No Chrome windows found. Make sure Chrome is running.")
        else:
            for _, title in self.chrome_windows:
                self.listbox.insert(tk.END, title)
            self.status_var.set(f"Found {len(self.chrome_windows)} Chrome window(s). Select one.")

    def get_selected_hwnd(self):
        selection_indices = self.listbox.curselection()
        if not selection_indices:
            messagebox.showwarning("No Selection", "Please select a Chrome window from the list.")
            return None
        
        selected_index = selection_indices[0]
        if selected_index >= len(self.chrome_windows):
             messagebox.showerror("Error", "Invalid selection. Please refresh the list.")
             return None

        hwnd, title = self.chrome_windows[selected_index]
        return hwnd

    def apply_transparency(self):
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            return

        alpha_percent = self.alpha_var.get()
        alpha_value = int(255 * (alpha_percent / 100))

        try:
            # Set window style to support transparency
            ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE)
            SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)
            
            # Set transparency
            SetLayeredWindowAttributes(hwnd, 0, alpha_value, LWA_ALPHA)
            
            self.status_var.set(f"Applied {alpha_percent}% transparency to the selected window.")
        except Exception as e:
            self.status_var.set(f"Error applying transparency: {e}")
            messagebox.showerror("Error", f"Could not apply transparency.\nError: {e}")

    def reset_transparency(self):
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            return

        try:
            # Remove the layered style to disable transparency
            ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE)
            SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_LAYERED)
            
            # Force the window to redraw to reflect the change
            RedrawWindow(hwnd, None, None, RDW_ERASE | RDW_INVALIDATE | RDW_FRAME | RDW_ALLCHILDREN)

            self.status_var.set("Transparency has been reset for the selected window.")
        except Exception as e:
            self.status_var.set(f"Error resetting transparency: {e}")
            messagebox.showerror("Error", f"Could not reset transparency.\nError: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ChromeTransparencyApp(root)
    root.mainloop()
