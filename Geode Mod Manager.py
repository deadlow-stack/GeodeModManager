import os
import shutil
import zipfile
import json
import pathlib
import tkinter as tk
import sys
import io
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import platform

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX   = platform.system() == "Linux"
IS_MAC     = platform.system() == "Darwin"

if getattr(sys, 'frozen', False):
    # Running in EXE
    APP_DIR = pathlib.Path(sys._MEIPASS)  # PyInstaller temp folder
else:
    APP_DIR = pathlib.Path(__file__).parent

DEFAULT_GD_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Geometry Dash\GeometryDash.exe"

# =========================================================
# Config
# =========================================================
APP_DIR = pathlib.Path(__file__).parent
CONFIG_FILE = APP_DIR / "config.json"

BG_COLOR = "#282828"
ACCENT1 = "#f4d48e"
ACCENT2 = "#f4a47b"
ACCENT3 = "#e27880"
ACCENT4 = "#b9588f"
TEXT_COLOR = "#000000"
SELECT_COLOR = "#b9588f"

# =========================================================
# App State
# =========================================================
gd_exe_path = "C:/Program Files (x86)/Steam/steamapps/common/Geometry Dash/GeometryDash.exe"
MOD_PATH = None
ALL_MODS = []  # (display_name, filename, icon, disabled)

SAVED_JSON = os.path.expandvars(r"%LOCALAPPDATA%\GeometryDash\geode\mods\geode.loader\saved.json")

def load_enabled_mods():
    """Return a dictionary mapping mod filename -> True/False based on saved.json"""
    enabled_map = {}
    if os.path.exists(SAVED_JSON):
        try:
            with open(SAVED_JSON, "r") as f:
                data = json.load(f)
                for key, value in data.items():
                    # Convert keys like "should-load-absolllute.installer" -> "absolllute.installer.geode"
                    if key.startswith("should-load-"):
                        mod_name = key[len("should-load-"):] + ".geode"
                        enabled_map[mod_name] = value
        except Exception as e:
            print("Failed to load saved.json:", e)
    return enabled_map

row_widgets = []
selected_row = None
selected_mod = None

# =========================================================
# Tk Init
# =========================================================
root = tk.Tk()
root.title("Geode Mod Manager")
root.geometry("800x500")
root.configure(bg=BG_COLOR)

# =========================================================
# Pages
# =========================================================
def show_mods():
    mods_page.tkraise()
    refresh_mods()

def show_settings():
    settings_page.tkraise()

def refresh_mods():
    global ALL_MODS
    if not MOD_PATH:
        return
    clear_rows()
    
    enabled_map = load_enabled_mods()
    ALL_MODS = []

    for fname in os.listdir(MOD_PATH):
        if fname.endswith(".geode"):
            path = os.path.join(MOD_PATH, fname)
            icon = get_mod_icon(path)
            is_enabled = enabled_map.get(fname, True)
            display_name = get_mod_name(path)
            if not is_enabled:
                display_name = "✘ " + display_name
            ALL_MODS.append((display_name, fname, icon, not is_enabled))

    # Sort alphabetically
    ALL_MODS.sort(key=lambda x: x[0].lstrip("✘ ").lower())

    # Add rows to canvas
    for display_name, fname, icon, disabled in ALL_MODS:
        add_row(display_name, fname, icon, disabled)

    # force canvas scrollregion update
    canvas.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))

# =========================================================
# Header
# =========================================================
header = tk.Frame(root, bg=BG_COLOR)
header.pack(side="top", pady=12)

menu = tk.Menu(root, tearoff=0, bg=BG_COLOR, fg="white",
               activebackground=ACCENT2, activeforeground="black")
menu.add_command(label="Mods", command=show_mods)
menu.add_separator()
menu.add_command(label="Geode Settings", command=show_settings)

logo = tk.Label(header, bg=BG_COLOR, cursor="hand2")
logo.pack(side="left", padx=(0, 15))
logo.bind("<Button-1>", lambda e: menu.tk_popup(e.x_root, e.y_root))

def update_geode_logo():
    if not gd_exe_path:
        return
    try:
        logo_path = os.path.join(
            os.path.dirname(gd_exe_path),
            "geode", "resources", "geode.loader", "LogoSheet-uhd.png"
        )
        sheet = Image.open(logo_path)
        img = sheet.crop((133, 361, 457, 685))
        img = img.resize((50, 50), Image.Resampling.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        logo.config(image=tk_img)
        logo.image = tk_img
    except Exception as e:
        print("Failed to load Geode logo:", e)

def make_button(text, color, cmd):
    b = tk.Button(
        header, text=text, command=cmd,
        bg=color, fg=TEXT_COLOR, bd=0,
        font=("Segoe UI", 11, "bold"),
        padx=15, pady=8,
        activebackground=ACCENT3
    )
    b.pack(side="left", padx=10)
    b.bind("<Enter>", lambda e: b.config(bg=ACCENT2))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b

make_button("Refresh Mods", ACCENT1, show_mods)
make_button("Enable / Disable Mod", ACCENT3, lambda: toggle_mod())
make_button("Open Geometry Dash", ACCENT4,
            lambda: os.startfile(gd_exe_path) if gd_exe_path else None)

def find_steam_libraries():
    libraries = []

    # Default Steam install
    steam_root = r"C:\Program Files (x86)\Steam"
    vdf_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")

    if not os.path.exists(vdf_path):
        return libraries

    try:
        with open(vdf_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Very simple VDF parsing (good enough for this file)
        for line in content.splitlines():
            line = line.strip()
            if line.startswith('"path"'):
                path = line.split('"')[3]
                libraries.append(path.replace("\\\\", "\\"))
    except:
        pass

    # Always include default Steam folder
    libraries.append(steam_root)

    return list(set(libraries))

def auto_detect_gd_exe():
    for library in find_steam_libraries():
        exe_path = os.path.join(
            library,
            "steamapps",
            "common",
            "Geometry Dash",
            "GeometryDash.exe"
        )
        if os.path.exists(exe_path):
            return exe_path

    return None

# =========================================================
# Config Helpers
# =========================================================
def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({"gd_exe_path": gd_exe_path}, f)

def load_config():
    global gd_exe_path

    # 1️⃣ Try config.json override
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                gd_exe_path = json.load(f).get("gd_exe_path")
        except:
            gd_exe_path = None

    # 2️⃣ Auto-detect via Steam if not set or invalid
    if not gd_exe_path or not os.path.exists(gd_exe_path):
        gd_exe_path = auto_detect_gd_exe()

    # 3️⃣ Persist detected path
    if gd_exe_path:
        save_config()

# =========================================================
# Geode Validation
# =========================================================
def verify_geode_install(exe_path):
    geode_resources = os.path.join(os.path.dirname(exe_path), "geode", "resources")
    if not os.path.isdir(geode_resources):
        messagebox.showerror(
            "Geode Not Found",
            "Cannot access files, make sure Geode is installed"
        )
        return False
    return True

def setup_paths():
    global MOD_PATH, DISABLED_PATH
    gd_dir = os.path.dirname(gd_exe_path)
    MOD_PATH = os.path.join(gd_dir, "geode", "mods")
    DISABLED_PATH = os.path.join(MOD_PATH, "_disabled")
    os.makedirs(DISABLED_PATH, exist_ok=True)


# =========================================================
# Content
# =========================================================
content = tk.Frame(root, bg=BG_COLOR)
content.pack(fill="both", expand=True, padx=10, pady=10)

mods_page = tk.Frame(content, bg=BG_COLOR)
settings_page = tk.Frame(content, bg=BG_COLOR)
mods_page.place(relwidth=1, relheight=1)
settings_page.place(relwidth=1, relheight=1)

# =========================================================
# Mods container (search bar above mod list)
# =========================================================
mods_container = tk.Frame(mods_page, bg=BG_COLOR)
mods_container.pack(fill='both', expand=True)

# --------------------------
# Search bar
# --------------------------
search_var = tk.StringVar()

def on_search(*args):
    filter_mods(search_var.get())

search_frame = tk.Frame(mods_container, bg=BG_COLOR)
search_frame.pack(side="top", fill='x', pady=(0,5))

tk.Label(search_frame, text="Search:", bg=BG_COLOR, fg="white",
         font=("Segoe UI", 11)).pack(side="left", padx=(5,2))

search_entry = tk.Entry(search_frame, textvariable=search_var, font=("Segoe UI", 11))
search_entry.pack(side="left", fill='x', expand=True, padx=(0,5))

search_var.trace_add('write', on_search)

# --------------------------
# Canvas for mods
# --------------------------
canvas = tk.Canvas(mods_container, bg=BG_COLOR, highlightthickness=0)
canvas.pack(fill="both", expand=True, side="left")

# --------------------------
# Scrollbar
# --------------------------
from tkinter import ttk

style = ttk.Style()
style.theme_use('default')
style.configure("Custom.Vertical.TScrollbar",
                background="#232323",
                troughcolor="#282828",
                arrowcolor="#FFFFFF",
                bordercolor="#282828",
                gripcount=0)

scrollbar = ttk.Scrollbar(mods_container, 
                          orient="vertical", 
                          command=canvas.yview, 
                          style="Custom.Vertical.TScrollbar")
scrollbar.pack(side="right", fill="y")
canvas.configure(yscrollcommand=scrollbar.set)

# --------------------------
# Mod rows frame inside canvas
# --------------------------
rows = tk.Frame(canvas, bg=BG_COLOR)
rows_window = canvas.create_window((0, 0), window=rows, anchor="n")  # top-center anchor

def center_rows(event=None):
    canvas_width = canvas.winfo_width()
    rows_width = rows.winfo_reqwidth()
    x = max((canvas_width - rows_width)//2, 0)
    canvas.coords(rows_window, x, 0)

rows.bind("<Configure>", lambda e: (canvas.configure(scrollregion=canvas.bbox("all")), center_rows()))
canvas.bind("<Configure>", lambda e: center_rows())
canvas.bind_all("<MouseWheel>",
    lambda e: canvas.yview_scroll(-1 * int(e.delta / 120), "units")
)


# =========================================================
# Mod Helpers
# =========================================================
def get_mod_icon(path):
    try:
        with zipfile.ZipFile(path) as z:
            if "logo.png" in z.namelist():
                img = Image.open(io.BytesIO(z.read("logo.png")))
                img = img.resize((40, 40), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
    except:
        pass
    return None

def get_mod_name(path):
    try:
        with zipfile.ZipFile(path) as z:
            with z.open("mod.json") as f:
                return json.load(f).get("name", os.path.basename(path))
    except:
        return os.path.basename(path)

def filter_mods(search_text):
    clear_rows()
    filtered = ALL_MODS
    if search_text:
        filtered = [m for m in ALL_MODS if search_text.lower() in m[0].lower()]
    for display_name, fname, icon, disabled in filtered:
        add_row(display_name, fname, icon, disabled)

# =========================================================
# Rows / Mods (file operations removed)
# =========================================================
def clear_rows():
    global selected_row, selected_mod
    for child in rows.winfo_children():
        child.destroy()  # destroy each mod row frame
    row_widgets.clear()
    selected_row = None
    selected_mod = None
    canvas.configure(scrollregion=canvas.bbox("all"))  # update scrollregion

def select_row(frame):
    global selected_row, selected_mod
    if selected_row:
        selected_row.bg.itemconfig(selected_row.rect, fill=selected_row.color)
    selected_row = selected_mod = frame
    frame.bg.itemconfig(frame.rect, fill=SELECT_COLOR)

def add_row(name, filename, icon, disabled):
    color = ACCENT3 if disabled else ACCENT1

    # Outer frame fills the canvas width
    outer = tk.Frame(rows, bg=BG_COLOR)
    outer.pack(fill='x', pady=2)  # fill horizontally

    f = tk.Frame(outer, bg=BG_COLOR)
    f.pack(fill='x')  # fill horizontally

    # Canvas now fills the width of the frame
    bg = tk.Canvas(f, height=60, bg=BG_COLOR, highlightthickness=0)
    bg.pack(fill='x')  # fill horizontally

    # Draw rectangle across full width
    rect = bg.create_rectangle(0, 0, bg.winfo_reqwidth(), 60, fill=color, outline="")
    f.bg, f.rect, f.color = bg, rect, color
    f.filename, f.disabled = filename, disabled

    # Left-aligned icon
    if icon:
        bg.create_image(30, 30, image=icon)
        f.icon = icon

    # Left-aligned text, next to icon
    f.text_item = bg.create_text(70, 30, text=name, anchor="w",
                                 fill="black", font=("Segoe UI", 12, "bold"))

    # Bind selection events
    bg.bind("<Button-1>", lambda e, fr=f: select_row(fr))
    bg.bind("<Double-1>", lambda e, fr=f: show_mod_info(fr))

    row_widgets.append(f)

    # Update rectangle width after canvas resizes
    def resize_rect(event):
        bg.coords(rect, 0, 0, event.width, 60)
    bg.bind("<Configure>", resize_rect)

    # store text item so we can update it later
    f.text_item = bg.create_text(70, 30, text=name, anchor="w",
                                 fill="black", font=("Segoe UI", 12, "bold"))

    bg.bind("<Button-1>", lambda e, fr=f: select_row(fr))
    bg.bind("<Double-1>", lambda e, fr=f: show_mod_info(fr))

    row_widgets.append(f)

# =========================================================
# GD EXE selection
# =========================================================
def ask_gd_exe():
    global gd_exe_path
    messagebox.showinfo("Select Geometry Dash", "Select your Geometry Dash .exe")
    path = filedialog.askopenfilename(
        title="Select Geometry Dash .exe",
        filetypes=[("Geometry Dash", "*.exe")]
    )
    if not path or not verify_geode_install(path):
        root.destroy()
        return
    gd_exe_path = path
    save_config()
    setup_paths()
    update_geode_logo()
    refresh_mods()
    update_settings_label()

load_config()

if not gd_exe_path:
    messagebox.showerror(
        "Geometry Dash Not Found",
        "Could not auto-detect Geometry Dash.\n"
        "Make sure it is installed via Steam."
    )
    root.destroy()
    raise SystemExit

if not verify_geode_install(gd_exe_path):
    root.destroy()
    raise SystemExit

setup_paths()
update_geode_logo()
    
# =========================================================
# Toggle mod (just updates visual selection, no file moving)
# =========================================================
def toggle_mod():
    if not selected_mod:
        return

    # toggle the disabled flag
    selected_mod.disabled = not selected_mod.disabled
    color = ACCENT3 if selected_mod.disabled else ACCENT1
    selected_mod.bg.itemconfig(selected_mod.rect, fill=color)

    # update the display name
    name = get_mod_name(os.path.join(MOD_PATH, selected_mod.filename))
    display_name = f"✘ {name}" if selected_mod.disabled else name
    selected_mod.bg.itemconfig(selected_mod.text_item, text=display_name)

    # --- Update saved.json ---
    saved_data = {}
    if os.path.exists(SAVED_JSON):
        try:
            with open(SAVED_JSON, "r") as f:
                saved_data = json.load(f)
        except:
            saved_data = {}

    # Key format: "should-load-<modname_without_geode>"
    mod_key = "should-load-" + selected_mod.filename.rsplit(".geode", 1)[0]
    saved_data[mod_key] = not selected_mod.disabled  # True if enabled

    try:
        with open(SAVED_JSON, "w") as f:
            json.dump(saved_data, f, indent=4)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to update saved.json:\n{e}")

# =========================================================
# Mod Info Helper
# =========================================================
def get_mod_info(path):
    """Return description and developers from a mod's mod.json"""
    try:
        with zipfile.ZipFile(path) as z:
            if "mod.json" in z.namelist():
                with z.open("mod.json") as f:
                    data = json.load(f)
                    description = data.get("description", "No description provided")
                    
                    # Handle either "developer" (string) or "developers" (list)
                    if "developers" in data and isinstance(data["developers"], list):
                        developers = data["developers"]
                    elif "developer" in data and isinstance(data["developer"], str):
                        developers = [data["developer"]]
                    else:
                        developers = []
                    
                    return description, developers
    except:
        pass
    return "No description provided", []


# =========================================================
# Mod Info Popup
# =========================================================
def show_mod_info(frame):
    # Always read from MOD_PATH
    path = os.path.join(MOD_PATH, frame.filename)
    description, developers = get_mod_info(path)
    
    if not developers:
        dev_text = "None"
        dev_label = "Developer(s):"
    elif len(developers) == 1:
        dev_text = developers[0]
        dev_label = "Developer:"
    else:
        dev_text = "\n".join(developers)
        dev_label = "Developers:"
    
    messagebox.showinfo(
        title=get_mod_name(path),
        message=f"Description:\n{description}\n\n{dev_label}\n{dev_text}"
    )

# =========================================================
# Setting Page
# =========================================================
tk.Label(settings_page, text="Geode Settings",
         font=("Segoe UI", 18, "bold"),
         bg=BG_COLOR, fg=ACCENT1).pack(pady=20)

settings_label = tk.Label(settings_page, bg=BG_COLOR, fg="white")
settings_label.pack(pady=10)

def update_settings_label():
    settings_label.config(text=f"Geometry Dash Executable:\n{gd_exe_path}")

tk.Button(settings_page, text="Change Geometry Dash Location",
          bg=ACCENT4, fg="black", bd=0,
          padx=15, pady=8,
          command=ask_gd_exe).pack(pady=20)


update_settings_label()
show_mods()
root.mainloop()
