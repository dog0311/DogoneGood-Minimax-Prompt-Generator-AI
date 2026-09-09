from __future__ import annotations

import base64
import configparser
import json
import mimetypes
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import requests
from PIL import Image, ImageTk


MAX_IMAGES = 4
SETTINGS_FILE = "mmsetup.ini"


_EDITABLE_WIDGETS = (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)
_SCROLLABLE_WIDGETS = (tk.Text, tk.Canvas, tk.Listbox, ttk.Treeview)


def _select_all(widget):
    if isinstance(widget, tk.Text):
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "end-1c")
    elif isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox)):
        widget.selection_range(0, "end")
        widget.icursor("end")

    widget.focus_set()


def _show_context_menu(event):
    widget = event.widget
    menu = tk.Menu(widget, tearoff=False)

    if isinstance(widget, _EDITABLE_WIDGETS):
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: _select_all(widget))
    else:
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))

    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def _find_scrollable_widget(widget):
    while widget is not None:
        if isinstance(widget, _SCROLLABLE_WIDGETS):
            return widget

        parent_name = widget.winfo_parent()
        if not parent_name:
            break

        try:
            widget = widget.nametowidget(parent_name)
        except KeyError:
            break

    return None


def _scroll_under_pointer(event):
    widget = _find_scrollable_widget(event.widget)
    if widget is None:
        return None

    if event.num == 4:
        amount = -1
    elif event.num == 5:
        amount = 1
    else:
        amount = -int(event.delta / 120) if event.delta else 0
        amount = amount or (-1 if event.delta > 0 else 1)

    widget.yview_scroll(amount, "units")
    return "break"


def install_widget_navigation(root: tk.Tk):
    """Add context menus, scrollbars, and cross-platform wheel scrolling."""
    root.bind_all("<Button-3>", _show_context_menu, add="+")
    root.bind_all("<Button-4>", _scroll_under_pointer, add="+")
    root.bind_all("<Button-5>", _scroll_under_pointer, add="+")
    root.bind_all("<MouseWheel>", _scroll_under_pointer, add="+")

    def attach_text_scrollbar(widget):
        scrollbar = ttk.Scrollbar(
            widget.master,
            orient="vertical",
            command=widget.yview,
        )
        scrollbar_visible = False

        def update_scrollbar(first, last):
            nonlocal scrollbar_visible
            scrollbar.set(first, last)
            needs_scrollbar = float(first) > 0 or float(last) < 1

            if needs_scrollbar and not scrollbar_visible:
                scrollbar.pack(side="right", fill="y")
                scrollbar_visible = True
            elif not needs_scrollbar and scrollbar_visible:
                scrollbar.pack_forget()
                scrollbar_visible = False

        widget.configure(yscrollcommand=update_scrollbar)
        widget.after_idle(lambda: widget.yview_moveto(0))

    def add_scrollbars(parent):
        for child in parent.winfo_children():
            if isinstance(child, (tk.Text, tk.Listbox)) and not getattr(
                child, "_navigation_scrollbar", False
            ):
                attach_text_scrollbar(child)
                setattr(child, "_navigation_scrollbar", True)

            add_scrollbars(child)

    add_scrollbars(root)


@dataclass
class ImageReference:
    path: Optional[Path] = None
    description: str = ""
    voice_style: str = ""


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window: Optional[tk.Toplevel] = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        if self.tip_window or not self.text:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify="left",
            background="#fff8c4",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
            wraplength=360,
        )
        label.pack()

    def hide(self, _event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class ImageCard:
    def __init__(
        self,
        parent: tk.Widget,
        index: int,
        app: "MiniMaxApp",
    ):
        self.parent = parent
        self.index = index
        self.app = app
        self.reference = ImageReference()
        self.thumbnail: Optional[ImageTk.PhotoImage] = None

        self.frame = tk.LabelFrame(
            parent,
            text=f"Reference Image {index + 1}",
            padx=10,
            pady=10,
            font=("Segoe UI", 11, "bold"),
        )
        self.frame.grid(row=0, column=index, padx=6, pady=6, sticky="nsew")

        parent.grid_columnconfigure(index, weight=1)

        self.preview_frame = tk.Frame(
            self.frame,
            width=220,
            height=150,
        )
        self.preview_frame.pack_propagate(False)
        self.preview_frame.pack()

        self.preview_button = tk.Button(
            self.preview_frame,
            text="Click to select image",
            width=22,
            height=8,
            command=self.select_image,
            font=("Segoe UI", 10),
        )
        self.preview_button.pack(fill="both", expand=True)

        ToolTip(
            self.preview_button,
            "Click here to choose a JPG, PNG, WEBP, BMP, or TIFF image.",
        )

        self.file_label = tk.Label(
            self.frame,
            text="No image selected",
            wraplength=190,
            font=("Segoe UI", 9),
        )
        self.file_label.pack(pady=(6, 4))

        desc_label = tk.Label(
            self.frame,
            text="What is in this image?",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )
        desc_label.pack(fill="x")

        self.description = tk.Text(
            self.frame,
            height=4,
            width=24,
            wrap="word",
            font=("Segoe UI", 10),
        )
        self.description.pack(fill="x", pady=(2, 8))

        ToolTip(
            self.description,
            "Describe the person, clothing, pose, setting, colors, and important objects. "
            "Example: 'Woman with long brown hair, blue jacket, standing beside a red car.'",
        )

        voice_label = tk.Label(
            self.frame,
            text="Voice or speech style",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )
        voice_label.pack(fill="x")

        self.voice_style = tk.Entry(
            self.frame,
            font=("Segoe UI", 10),
        )
        self.voice_style.pack(fill="x", pady=(2, 8))

        ToolTip(
            self.voice_style,
            "Optional. Examples: female, soft, Southern; deep male, calm, British; "
            "elderly woman, warm, whispering.",
        )

        button_row = tk.Frame(self.frame)
        button_row.pack(fill="x")

        self.analyze_button = tk.Button(
            button_row,
            text="Analyze",
            command=self.analyze_image,
            font=("Segoe UI", 9),
        )
        self.analyze_button.pack(side="left", expand=True, fill="x", padx=(0, 3))

        clear_button = tk.Button(
            button_row,
            text="Clear",
            command=self.clear,
            font=("Segoe UI", 9),
        )
        clear_button.pack(side="left", expand=True, fill="x", padx=(3, 0))

        add_reference_button = tk.Button(
            button_row,
            text=f"Add image_reference{self.index + 1}",
            command=lambda: self.app.insert_reference_name(self.index),
            font=("Segoe UI", 9),
        )
        add_reference_button.pack(side="left", expand=True, fill="x", padx=(3, 0))

    def select_image(self):
        filename = filedialog.askopenfilename(
            title="Choose a reference image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )

        if not filename:
            return

        try:
            path = Path(filename)
            image = Image.open(path)
            image.thumbnail((220, 150))

            self.thumbnail = ImageTk.PhotoImage(image)
            self.preview_button.configure(
                image=self.thumbnail,
                text="",
                compound="center",
            )

            self.reference.path = path
            self.file_label.configure(text=path.name)

        except Exception as exc:
            messagebox.showerror("Could not open image", str(exc))

    def get_description(self) -> str:
        return self.description.get("1.0", "end").strip()

    def get_voice_style(self) -> str:
        return self.voice_style.get().strip()

    def analyze_image(self):
        if not self.reference.path:
            messagebox.showinfo(
                "Choose an image first",
                "Select an image before asking the app to analyze it.",
            )
            return

        self.analyze_button.configure(state="disabled", text="Analyzing...")

        thread = threading.Thread(
            target=self._analyze_worker,
            daemon=True,
        )
        thread.start()

    def _analyze_worker(self):
        try:
            description = self.app.analyze_single_image(self.reference.path)

            self.app.root.after(
                0,
                lambda: self._apply_analysis(description),
            )

        except Exception as exc:
            self.app.root.after(
                0,
                lambda: messagebox.showerror("Image analysis failed", str(exc)),
            )
            self.app.root.after(
                0,
                lambda: self.analyze_button.configure(
                    state="normal",
                    text="Analyze",
                ),
            )

    def _apply_analysis(self, description: str):
        self.reference.description = description
        self.description.delete("1.0", "end")
        self.description.insert("1.0", description)
        self.analyze_button.configure(state="normal", text="Analyze")

    def clear(self):
        self.reference = ImageReference()
        self.thumbnail = None
        self.preview_button.configure(
            image="",
            text="Click to select image",
        )
        self.file_label.configure(text="No image selected")
        self.description.delete("1.0", "end")
        self.voice_style.delete(0, "end")


class MiniMaxApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.setup_path = Path(__file__).resolve().parent / SETTINGS_FILE
        self.root.title("MiniMax H3 Image-to-Video Prompt Generator")
        self.root.geometry("1420x960")
        self.root.minsize(1100, 760)

        self.page_canvas = tk.Canvas(self.root, highlightthickness=0)
        self.page_scrollbar = ttk.Scrollbar(
            self.root,
            orient="vertical",
            command=self.page_canvas.yview,
        )
        self.page_frame = tk.Frame(self.page_canvas)
        self.page_frame.bind(
            "<Configure>",
            lambda _event: self.page_canvas.configure(
                scrollregion=self.page_canvas.bbox("all")
            ),
        )
        self.page_window = self.page_canvas.create_window(
            (0, 0),
            window=self.page_frame,
            anchor="nw",
        )
        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)
        self.page_canvas.pack(side="left", fill="both", expand=True)
        self.page_scrollbar.pack(side="right", fill="y")
        self.page_canvas.bind(
            "<Configure>",
            lambda event: self.page_canvas.itemconfigure(
                self.page_window,
                width=event.width,
            ),
        )

        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except tk.TclError:
            pass

        self.cards: list[ImageCard] = []

        backend, model = self.load_setup_values()
        self.backend_var = tk.StringVar(value=backend)
        self.model_var = tk.StringVar(value=model)
        self.backend_var.trace_add("write", self.save_setup_values)
        self.model_var.trace_add("write", self.save_setup_values)
        self.duration_var = tk.StringVar(value="5 seconds")
        self.aspect_ratio_var = tk.StringVar(value="16:9")
        self.shot_type_var = tk.StringVar(value="Medium shot")
        self.camera_movement_var = tk.StringVar(value="Subtle handheld push-in")
        self.lens_var = tk.StringVar(value="35mm cinematic lens")
        self.fps_var = tk.StringVar(value="24 fps")
        self.motion_strength_var = tk.StringVar(value="Moderate")
        self.style_var = tk.StringVar(value="Photorealistic cinematic")
        self.mood_var = tk.StringVar(value="Natural and believable")
        self.lighting_var = tk.StringVar(value="Soft natural lighting")
        self.time_of_day_var = tk.StringVar(value="Daytime")
        self.environment_motion_var = tk.StringVar(value="Natural environmental movement")
        self.audio_var = tk.StringVar(value="No dialogue unless specified")
        self.output_file_var = tk.StringVar(value="minimax_prompt.txt")
        self.status_var = tk.StringVar(value="Ready")

        self.build_interface()

    def load_setup_values(self) -> tuple[str, str]:
        defaults = ("Ollama", "llava")
        config = configparser.ConfigParser()

        if not self.setup_path.exists():
            self.write_setup_values(*defaults)
            return defaults

        try:
            config.read(self.setup_path, encoding="utf-8")
            settings = config["settings"]
            backend = settings.get("backend", defaults[0]).strip() or defaults[0]
            model = settings.get("model", defaults[1]).strip() or defaults[1]
        except (configparser.Error, KeyError, OSError):
            backend, model = defaults

        return backend, model

    def save_setup_values(self, *_args):
        self.write_setup_values(
            self.backend_var.get(),
            self.model_var.get(),
        )

    def write_setup_values(self, backend: str, model: str):
        config = configparser.ConfigParser()
        config["settings"] = {
            "backend": backend,
            "model": model,
        }

        try:
            with self.setup_path.open("w", encoding="utf-8") as setup_file:
                config.write(setup_file)
        except OSError:
            pass

    def build_interface(self):
        title = tk.Label(
            self.page_frame,
            text="MiniMax H3 Image-to-Video Prompt Generator",
            font=("Segoe UI", 18, "bold"),
            pady=10,
        )
        title.pack()

        subtitle = tk.Label(
            self.page_frame,
            text=(
                "Choose up to four reference images, describe the action, "
                "then generate a complete prompt."
            ),
            font=("Segoe UI", 11),
        )
        subtitle.pack(pady=(0, 8))

        self.build_backend_bar()
        self.build_images_section()
        self.build_prompt_fields()
        self.build_output_section()
        self.build_bottom_bar()

    def build_backend_bar(self):
        frame = tk.LabelFrame(
            self.page_frame,
            text="Local AI Model",
            padx=10,
            pady=8,
            font=("Segoe UI", 11, "bold"),
        )
        frame.pack(fill="x", padx=12, pady=6)

        tk.Label(frame, text="Backend:").grid(row=0, column=0, padx=5)
        backend = ttk.Combobox(
            frame,
            textvariable=self.backend_var,
            values=["Ollama", "LM Studio"],
            state="readonly",
            width=14,
        )
        backend.grid(row=0, column=1, padx=5)

        tk.Label(frame, text="Vision model:").grid(row=0, column=2, padx=5)

        model_entry = tk.Entry(
            frame,
            textvariable=self.model_var,
            width=30,
            font=("Segoe UI", 10),
        )
        model_entry.grid(row=0, column=3, padx=5)

        ToolTip(
            model_entry,
            "Use a vision-capable model. Examples for Ollama include llava "
            "or a Qwen vision model. In LM Studio, enter the loaded model ID.",
        )

        tk.Label(frame, text="Server:").grid(row=0, column=4, padx=5)

        self.server_label = tk.Label(
            frame,
            text="Ollama: http://127.0.0.1:11434 | LM Studio: http://127.0.0.1:1234",
            font=("Segoe UI", 9),
        )
        self.server_label.grid(row=0, column=5, padx=5, sticky="w")

    def build_images_section(self):
        frame = tk.LabelFrame(
            self.page_frame,
            text="Reference Images",
            padx=8,
            pady=8,
            font=("Segoe UI", 11, "bold"),
        )
        frame.pack(fill="x", padx=12, pady=6)

        for index in range(MAX_IMAGES):
            card = ImageCard(frame, index, self)
            self.cards.append(card)

    def build_prompt_fields(self):
        outer = tk.LabelFrame(
            self.page_frame,
            text="Video Prompt Details",
            padx=8,
            pady=8,
            font=("Segoe UI", 11, "bold"),
        )
        outer.pack(fill="both", expand=True, padx=12, pady=6)

        scroll_frame = tk.Frame(outer)
        scroll_frame.pack(fill="x", expand=True)

        self.add_large_text_field(
            scroll_frame,
            "Main subject",
            "Who or what is the main subject?",
            "Example: A middle-aged Marine veteran wearing a dark jacket",
            height=3,
        )

        self.add_large_text_field(
            scroll_frame,
            "Action and timing",
            "What should happen in the video?",
            "Example: He looks toward the camera, smiles slightly, and slowly raises his hand in greeting.",
            height=4,
        )

        self.add_large_text_field(
            scroll_frame,
            "Scene and environment",
            "Where does the action happen?",
            "Example: A quiet coastal road at sunrise with tall grass moving in the breeze.",
            height=3,
        )

        self.add_large_text_field(
            scroll_frame,
            "Continuity instructions",
            "What must remain unchanged from the reference images?",
            "Example: Preserve the subject's identity, clothing, hairstyle, facial features, and the red truck.",
            height=3,
        )

        self.add_large_text_field(
            scroll_frame,
            "Extra instructions",
            "Anything else the model should know?",
            "Example: Keep the motion natural and avoid exaggerated facial movement.",
            height=3,
        )

        self.add_option_row(
            scroll_frame,
            "Duration",
            self.duration_var,
            ["3 seconds", "5 seconds", "6 seconds", "10 seconds"],
            "Approximate video length.",
        )

        self.add_option_row(
            scroll_frame,
            "Aspect ratio",
            self.aspect_ratio_var,
            ["16:9", "9:16", "1:1", "4:3"],
            "16:9 is landscape. 9:16 is vertical phone video.",
        )

        self.add_option_row(
            scroll_frame,
            "Shot type",
            self.shot_type_var,
            [
                "Extreme close-up",
                "Close-up",
                "Medium shot",
                "Medium-wide shot",
                "Wide shot",
                "Extreme wide shot",
            ],
            "How much of the subject should be visible.",
        )

        self.add_option_row(
            scroll_frame,
            "Camera movement",
            self.camera_movement_var,
            [
                "Static camera",
                "Slow push-in",
                "Slow pull-back",
                "Pan left",
                "Pan right",
                "Tilt up",
                "Tilt down",
                "Orbit around subject",
                "Tracking shot",
                "Subtle handheld",
                "Fast dramatic movement",
            ],
            "How the camera moves during the shot.",
        )

        self.add_option_row(
            scroll_frame,
            "Lens and focus",
            self.lens_var,
            [
                "24mm wide-angle lens",
                "35mm cinematic lens",
                "50mm natural perspective",
                "85mm portrait lens",
                "Shallow depth of field",
                "Deep focus",
            ],
            "Controls the visual perspective and background blur.",
        )

        self.add_option_row(
            scroll_frame,
            "Motion strength",
            self.motion_strength_var,
            ["Very subtle", "Moderate", "Strong", "Highly dynamic"],
            "How much movement should be added to the image.",
        )

        self.add_option_row(
            scroll_frame,
            "Visual style",
            self.style_var,
            [
                "Photorealistic cinematic",
                "Documentary realism",
                "Film still",
                "Commercial advertisement",
                "Music video",
                "Dreamlike",
                "Vintage film",
                "Anime-inspired",
                "Stylized fantasy",
            ],
            "Overall visual treatment.",
        )

        self.add_option_row(
            scroll_frame,
            "Mood",
            self.mood_var,
            [
                "Natural and believable",
                "Warm and uplifting",
                "Calm and peaceful",
                "Serious and dramatic",
                "Mysterious",
                "Energetic",
                "Emotional",
                "Comedic",
            ],
            "Emotional feeling of the video.",
        )

        self.add_option_row(
            scroll_frame,
            "Lighting",
            self.lighting_var,
            [
                "Soft natural lighting",
                "Golden hour",
                "Overcast daylight",
                "Dramatic side lighting",
                "Low-key cinematic lighting",
                "Neon lighting",
                "Studio lighting",
                "Moonlight",
            ],
            "Main lighting style.",
        )

        self.add_option_row(
            scroll_frame,
            "Time of day",
            self.time_of_day_var,
            [
                "Dawn",
                "Morning",
                "Midday",
                "Golden hour",
                "Sunset",
                "Blue hour",
                "Night",
            ],
            "When the scene takes place.",
        )

        self.add_option_row(
            scroll_frame,
            "Background motion",
            self.environment_motion_var,
            [
                "Minimal background movement",
                "Wind moving hair and clothing",
                "Moving clouds",
                "Rain",
                "Snow",
                "Traffic and people in background",
                "Water movement",
                "Dust or atmospheric particles",
            ],
            "Movement that happens behind or around the subject.",
        )

        self.add_option_row(
            scroll_frame,
            "Audio and dialogue",
            self.audio_var,
            [
                "No dialogue unless specified",
                "Natural environmental sound",
                "Cinematic ambient sound",
                "Soft spoken dialogue",
                "Voice-over narration",
                "Dramatic sound design",
            ],
            "Describe the desired audio treatment.",
        )

        self.add_large_text_field(
            scroll_frame,
            "Negative prompt",
            "What should be avoided?",
            "Example: No face distortion, no extra fingers, no identity change, no flickering, no warped objects.",
            height=4,
        )

    def add_large_text_field(
        self,
        parent: tk.Widget,
        label: str,
        hint: str,
        placeholder: str,
        height: int = 3,
    ):
        frame = tk.Frame(parent)
        frame.pack(fill="x", padx=8, pady=5)

        label_widget = tk.Label(
            frame,
            text=label,
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        )
        label_widget.pack(fill="x")

        hint_widget = tk.Label(
            frame,
            text=hint,
            anchor="w",
            foreground="#555555",
            font=("Segoe UI", 9),
        )
        hint_widget.pack(fill="x")

        text_widget = tk.Text(
            frame,
            height=height,
            wrap="word",
            font=("Segoe UI", 10),
        )
        text_widget.pack(fill="x", pady=(2, 0))
        text_widget.insert("1.0", placeholder)
        text_widget.configure(foreground="#777777")

        def focus_in(_event):
            if text_widget.get("1.0", "end").strip() == placeholder:
                text_widget.delete("1.0", "end")
                text_widget.configure(foreground="black")

        def focus_out(_event):
            if not text_widget.get("1.0", "end").strip():
                text_widget.insert("1.0", placeholder)
                text_widget.configure(foreground="#777777")

        text_widget.bind("<FocusIn>", focus_in)
        text_widget.bind("<FocusOut>", focus_out)

        setattr(self, f"field_{label}", text_widget)

        ToolTip(text_widget, hint)

    def add_option_row(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        hint: str,
    ):
        frame = tk.Frame(parent)
        frame.pack(fill="x", padx=8, pady=3)

        label_widget = tk.Label(
            frame,
            text=label,
            width=22,
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        )
        label_widget.pack(side="left")

        combo = ttk.Combobox(
            frame,
            textvariable=variable,
            values=values,
            state="readonly",
            width=38,
        )
        combo.pack(side="left", fill="x", expand=True)

        ToolTip(combo, hint)

    def insert_reference_name(self, index: int):
        action_widget = getattr(self, "field_Action and timing", None)
        if action_widget is None:
            return

        placeholder = "What should happen in the video?"
        if action_widget.get("1.0", "end").strip() == placeholder:
            action_widget.delete("1.0", "end")
            action_widget.configure(foreground="black")

        reference_name = f"image_reference{index + 1}"
        action_widget.focus_set()
        action_widget.insert("insert", reference_name)

    def get_text_field(self, field_name: str) -> str:
        widget = getattr(self, f"field_{field_name}")
        value = widget.get("1.0", "end").strip()

        placeholder_map = {
            "Main subject": "Who or what is the main subject?",
            "Action and timing": "What should happen in the video?",
            "Scene and environment": "Where does the action happen?",
            "Continuity instructions": (
                "What must remain unchanged from the reference images?"
            ),
            "Extra instructions": "Anything else the model should know?",
            "Negative prompt": "What should be avoided?",
        }

        if value == placeholder_map.get(field_name):
            return ""

        return value

    def image_to_base64(self, path: Path) -> tuple[str, str]:
        mime_type, _ = mimetypes.guess_type(path.name)

        if not mime_type:
            mime_type = "image/jpeg"

        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return encoded, mime_type

    def analyze_single_image(self, path: Path) -> str:
        prompt = (
            "Describe this image for an image-to-video prompt. Include the main "
            "subject, appearance, clothing, pose, facial expression, camera angle, "
            "background, lighting, colors, and important objects. Be factual and "
            "concise. Do not invent details that cannot be seen."
        )

        backend = self.backend_var.get()
        model = self.model_var.get().strip()
        encoded, mime_type = self.image_to_base64(path)

        if backend == "Ollama":
            payload = {
                "model": model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [encoded],
                    }
                ],
            }

            response = requests.post(
                "http://127.0.0.1:11434/api/chat",
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            return response.json()["message"]["content"].strip()

        data_url = f"data:{mime_type};base64,{encoded}"

        payload = {
            "model": model,
            "temperature": 0.2,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
        }

        response = requests.post(
            "http://127.0.0.1:1234/v1/chat/completions",
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def build_generation_prompt(self) -> str:
        image_information = []

        for index, card in enumerate(self.cards, start=1):
            if not card.reference.path:
                continue

            description = card.get_description()
            voice_style = card.get_voice_style()

            image_information.append(
                f"""
REFERENCE IMAGE {index}
Filename: {card.reference.path.name}
Description: {description or "No manual description supplied."}
Voice or speech style: {voice_style or "Not specified."}
"""
            )

        images_text = "\n".join(image_information)
        if not images_text:
            images_text = "No reference images were supplied."

        return f"""
Create a complete, production-ready image-to-video prompt for a MiniMax
H3/Hailuo-style video model.

The prompt must use the supplied reference images as the visual source and
must preserve subject identity, clothing, important objects, composition,
and scene continuity.

REFERENCE IMAGES:
{images_text}

MAIN SUBJECT:
{self.get_text_field("Main subject")}

ACTION AND TIMING:
{self.get_text_field("Action and timing")}

SCENE AND ENVIRONMENT:
{self.get_text_field("Scene and environment")}

CONTINUITY INSTRUCTIONS:
{self.get_text_field("Continuity instructions")}

EXTRA INSTRUCTIONS:
{self.get_text_field("Extra instructions")}

VIDEO OPTIONS:
Duration: {self.duration_var.get()}
Aspect ratio: {self.aspect_ratio_var.get()}
Shot type: {self.shot_type_var.get()}
Camera movement: {self.camera_movement_var.get()}
Lens and focus: {self.lens_var.get()}
Motion strength: {self.motion_strength_var.get()}
Visual style: {self.style_var.get()}
Mood: {self.mood_var.get()}
Lighting: {self.lighting_var.get()}
Time of day: {self.time_of_day_var.get()}
Background motion: {self.environment_motion_var.get()}
Audio and dialogue: {self.audio_var.get()}

NEGATIVE PROMPT:
{self.get_text_field("Negative prompt")}
"""

    def generate_prompt(self):
        model = self.model_var.get().strip()

        if not model:
            messagebox.showwarning(
                "Model required",
                "Enter the name of the vision-capable local model.",
            )
            return

        action = self.get_text_field("Action and timing")
        if not action:
            messagebox.showwarning(
                "Action required",
                "Describe what should happen in the video.",
            )
            return

        self.status_var.set("Generating prompt...")
        self.generate_button.configure(state="disabled")

        thread = threading.Thread(
            target=self._generation_worker,
            daemon=True,
        )
        thread.start()

    def _generation_worker(self):
        try:
            result = self.call_local_model(self.build_generation_prompt())

            self.root.after(
                0,
                lambda: self.show_result(result),
            )

        except Exception as exc:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Generation failed",
                    str(exc),
                ),
            )
            self.root.after(
                0,
                lambda: self.status_var.set("Generation failed"),
            )
            self.root.after(
                0,
                lambda: self.generate_button.configure(state="normal"),
            )

    def call_local_model(self, user_prompt: str) -> str:
        system_prompt = """
You are a professional image-to-video prompt engineer.

Write one complete prompt for a MiniMax H3/Hailuo-style video model. Use the
reference-image descriptions and all selected settings. Be specific about
subject identity, motion, timing, camera movement, lighting, sound, and
continuity.

Return these sections:
TITLE:
VIDEO PROMPT:
CAMERA:
MOTION:
STYLE AND LIGHTING:
AUDIO:
CONTINUITY:
NEGATIVE PROMPT:
SETTINGS SUGGESTION:

Do not add explanations outside those sections.
"""

        backend = self.backend_var.get()
        model = self.model_var.get().strip()

        if backend == "Ollama":
            payload = {
                "model": model,
                "stream": False,
                "options": {
                    "temperature": 0.45,
                },
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            }

            response = requests.post(
                "http://127.0.0.1:11434/api/chat",
                json=payload,
                timeout=600,
            )
            response.raise_for_status()
            return response.json()["message"]["content"].strip()

        payload = {
            "model": model,
            "temperature": 0.45,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        response = requests.post(
            "http://127.0.0.1:1234/v1/chat/completions",
            json=payload,
            timeout=600,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def show_result(self, result: str):
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", result)
        self.status_var.set("Prompt generated")
        self.generate_button.configure(state="normal")

        self.root.after(
            100,
            lambda: self.output_text.focus_set(),
        )

    def copy_result(self):
        text = self.output_text.get("1.0", "end").strip()

        if not text:
            messagebox.showinfo(
                "Nothing to copy",
                "Generate a prompt first.",
            )
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Prompt copied to clipboard")

    def save_result(self):
        text = self.output_text.get("1.0", "end").strip()

        if not text:
            messagebox.showinfo(
                "Nothing to save",
                "Generate a prompt first.",
            )
            return

        filename = filedialog.asksaveasfilename(
            title="Save generated prompt",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("JSON files", "*.json"),
            ],
        )

        if not filename:
            return

        path = Path(filename)

        if path.suffix.lower() == ".json":
            data = {
                "backend": self.backend_var.get(),
                "model": self.model_var.get(),
                "duration": self.duration_var.get(),
                "aspect_ratio": self.aspect_ratio_var.get(),
                "shot_type": self.shot_type_var.get(),
                "camera_movement": self.camera_movement_var.get(),
                "lens": self.lens_var.get(),
                "motion_strength": self.motion_strength_var.get(),
                "visual_style": self.style_var.get(),
                "mood": self.mood_var.get(),
                "lighting": self.lighting_var.get(),
                "time_of_day": self.time_of_day_var.get(),
                "background_motion": self.environment_motion_var.get(),
                "audio": self.audio_var.get(),
                "prompt": text,
            }

            path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        else:
            path.write_text(text + "\n", encoding="utf-8")

        self.status_var.set(f"Saved: {path.name}")

    def clear_all(self):
        answer = messagebox.askyesno(
            "Clear everything?",
            "This will remove the selected images and all prompt information.",
        )

        if not answer:
            return

        for card in self.cards:
            card.clear()

        for field_name in [
            "Main subject",
            "Action and timing",
            "Scene and environment",
            "Continuity instructions",
            "Extra instructions",
            "Negative prompt",
        ]:
            widget = getattr(self, f"field_{field_name}")
            widget.delete("1.0", "end")

        self.output_text.delete("1.0", "end")
        self.status_var.set("Cleared")

    def build_output_section(self):
        frame = tk.LabelFrame(
            self.page_frame,
            text="Generated Prompt",
            padx=8,
            pady=8,
            font=("Segoe UI", 11, "bold"),
        )
        frame.pack(fill="both", expand=True, padx=12, pady=6)

        self.output_text = tk.Text(
            frame,
            height=15,
            wrap="word",
            font=("Consolas", 10),
        )
        self.output_text.pack(fill="both", expand=True)

        ToolTip(
            self.output_text,
            "This is the finished prompt. You can edit it before copying or saving.",
        )

    def build_bottom_bar(self):
        frame = tk.Frame(self.page_frame, padx=12, pady=8)
        frame.pack(fill="x")

        self.generate_button = tk.Button(
            frame,
            text="GENERATE COMPLETE PROMPT",
            command=self.generate_prompt,
            bg="#1769aa",
            fg="white",
            activebackground="#0d47a1",
            activeforeground="white",
            font=("Segoe UI", 12, "bold"),
            padx=15,
            pady=8,
        )
        self.generate_button.pack(side="left")

        copy_button = tk.Button(
            frame,
            text="Copy",
            command=self.copy_result,
            font=("Segoe UI", 10),
            padx=14,
            pady=8,
        )
        copy_button.pack(side="left", padx=8)

        save_button = tk.Button(
            frame,
            text="Save",
            command=self.save_result,
            font=("Segoe UI", 10),
            padx=14,
            pady=8,
        )
        save_button.pack(side="left")

        clear_button = tk.Button(
            frame,
            text="Clear All",
            command=self.clear_all,
            font=("Segoe UI", 10),
            padx=14,
            pady=8,
        )
        clear_button.pack(side="right")

        status = tk.Label(
            frame,
            textvariable=self.status_var,
            anchor="w",
            foreground="#555555",
            font=("Segoe UI", 10),
        )
        status.pack(side="left", padx=18)


def main():
    root = tk.Tk()
    MiniMaxApp(root)
    install_widget_navigation(root)
    root.mainloop()


if __name__ == "__main__":
    main()
