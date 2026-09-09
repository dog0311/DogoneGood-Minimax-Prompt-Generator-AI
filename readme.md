# MiniMax H3 Image-to-Video Prompt Generator

A Python/Tkinter desktop application for creating detailed MiniMax H3/Hailuo image-to-video prompts with help from a local vision-language model.

The current entry point is `minimax_i2v_apptest.py`.

## Features

- Load up to four reference images.
- Analyze each image with Ollama or LM Studio.
- Review and edit the generated image description in each reference card.
- Insert `image_reference1` through `image_reference4` into the Action and timing field at the current cursor position.
- Configure duration, aspect ratio, shot type, camera movement, lens, motion, style, mood, lighting, time of day, background motion, audio, and negative prompts.
- Scroll the complete application window with one page scrollbar.
- Use individual text-editor scrollbars when multiline content exceeds its editor.
- Copy the generated prompt or save it as `.txt`, `.md`, or `.json`.
- Remember the selected backend and vision model in `mmsetup.ini`.

## Requirements

- Windows, macOS, or Linux
- Python 3.9 or newer
- Tkinter
- Pillow
- Requests
- A local model provider:
	- Ollama at `http://127.0.0.1:11434`, or
	- LM Studio's OpenAI-compatible server at `http://127.0.0.1:1234`

Tkinter is normally included with Python on Windows. On Linux, install the distribution's Tk package, such as `python3-tk`, if necessary.

## Installation

Open a terminal in the project directory and optionally create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install pillow requests
```

## Configure a Local Model Provider

### Ollama

Start Ollama and make sure a vision-capable model is available. For example:

```powershell
ollama pull llava
ollama serve
```

The application sends image-analysis and prompt-generation requests to Ollama's `/api/chat` endpoint.

### LM Studio

Load a vision-capable model in LM Studio and start its local server. The default endpoint is:

```text
http://127.0.0.1:1234/v1/chat/completions
```

## Run the Program

From the project directory:

```powershell
python minimax_i2v_apptest.py
```

The application window opens with the backend, reference-image, prompt-detail, generated-prompt, and action sections inside one vertically scrollable page.

## Backend and Model Settings

On startup, the program looks for `mmsetup.ini` beside `minimax_i2v_apptest.py`.

If the file does not exist, it creates one with these defaults:

```ini
[settings]
backend = Ollama
model = llava
```

Changing the Backend or Vision model field updates the file automatically. A later launch loads those saved values.

## Basic Workflow

1. Select `Ollama` or `LM Studio` and confirm the vision model name.
2. Choose one or more reference images.
3. Click `Analyze` on a reference card.
4. Review or edit the generated description.
5. Use an `Add image_referenceN` button to insert that reference name into the Action and timing editor.
6. Complete the subject, action, environment, continuity, options, and negative prompt fields.
7. Click `GENERATE COMPLETE PROMPT`.
8. Copy the result or save it to a file.

The generated prompt includes the reference descriptions, requested motion, camera and style settings, audio, continuity instructions, and negative prompt.

## Project Files

```text
minimax_i2v_apptest.py  Main application
mmsetup.ini             Created automatically for backend/model settings
readme.md               This documentation
```

## Troubleshooting

- **Connection refused:** Start Ollama or the LM Studio local server and confirm its expected port.
- **Model errors:** Use a vision-capable model for image analysis and enter its exact model identifier.
- **Tkinter import error:** Install the operating system's Tkinter package or reinstall Python with Tk support.
- **Settings not saved:** Ensure the application directory is writable; `mmsetup.ini` is written beside the script.

## License

Distributed under the MIT License.