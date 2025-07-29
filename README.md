# Window Transparency GUI

A simple GUI application to control the transparency of any window on Microsoft Windows.

## Features

-   Lists all visible windows on the system.
-   Allows you to apply a transparency effect to any selected window.
-   Adjust transparency level with a simple slider (0% to 100%).
-   Reset the transparency of a window back to its default opaque state.

## How to Use

1.  **Run the application** (`WindowTransparencyGUI.exe` or `python window_transparency_gui.py`).
2.  **Refresh List**: Click the "Refresh List" button to get a list of all currently open and visible windows.
3.  **Select a Window**: Click on the title of the window you want to modify from the list.
4.  **Adjust Transparency**:
    *   Move the slider to the desired transparency level. (0% is fully transparent, 100% is fully opaque).
    *   Click the **"Apply Transparency"** button.
5.  **Reset Transparency**:
    *   Select a window from the list that you have previously modified.
    *   Click the **"Reset Transparency"** button to make it fully opaque again.

## How to Build

Follow these steps to build this application into a standalone `.exe` file.

### 1. Create and Activate a Virtual Environment

From the project folder, create and activate a Python virtual environment. If you already have one, just activate it.

```bash
# 1. Create virtual environment
# Use python or python3 depending on your system's Python installation.
python -m venv venv

# 2. Activate virtual environment on Windows
.\venv\Scripts\activate
```

### 2. Install Dependencies

With the virtual environment activated, install the required packages from `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 3. Build the Executable

Use `pyinstaller` to build the `.py` file into an `.exe` executable.

```bash
pyinstaller --onefile --windowed --name WindowTransparencyGUI window_transparency_gui.py
```

**Build Options Explained:**
*   `--onefile`: Bundles everything into a single executable file.
*   `--windowed`: Prevents the console window (black terminal) from appearing when the application is run.
*   `--name WindowTransparencyGUI`: Sets the output file name to `WindowTransparencyGUI.exe`.

### 4. Check the Result

After a successful build, a `dist` folder will be created in the project directory. Your final `WindowTransparencyGUI.exe` file will be inside this folder.
