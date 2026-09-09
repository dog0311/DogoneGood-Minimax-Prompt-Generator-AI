# DogoneGood-Minimax-Prompt-Generator-AI
DogoneGood-Minimax-Prompt-Generator AI Free Local LLM Use ollama or LM Studio Support use Local Free LLM
An interactive desktop application built in Python and Tkinter for generating production-ready, highly detailed image-to-video prompts for **MiniMax H3 / Hailuo** models using local AI vision models.

---

## 🖼️ Application Interface

![Main Application Screen](assets/mainscreen.png)

---

## 🌟 Key Features

- **Multi-Image Support**: Load up to **4 reference images** simultaneously to establish character, background, lighting, and style references.
- **Local Vision AI Integration**: Automatically analyze reference images locally using **Ollama** (e.g., `llava`, `LFM2.5-VL-3B`) or **LM Studio** local endpoints.
- **Detailed Parameter Fine-Tuning**: Fine-tune shot type, camera movement, lens/focus, motion strength, visual style, mood, lighting, time of day, background motion, and audio expectations.
- **Structured JSON Output**: Generates structured, production-ready prompt outputs complete with video prompt, camera controls, motion parameters, continuity rules, negative prompts, and suggested generation settings.
- **Export Capabilities**: Easily copy output directly to your clipboard or save prompt configurations as `.txt`, `.md`, or `.json` files.

---

## 📁 Repository Structure

```text
DogoneGood-Minimax-Prompt-Generator-AI/
├── assets/                          # Application screenshots and demo assets
│   ├── actionwindow.png
│   ├── aigeneratindprompt.png
│   ├── aitoolbar.png
│   ├── mainscreen.png
│   ├── mainsubject.png
│   ├── referenceImage.png
│   └── scroltofindmoreaction.png
├── minimax_i2v_app.py              # Main Tkinter desktop application script
└── README.md                       # Repository documentation

Component,Description,Preview
Local AI Toolbar,Select between Ollama or LM Studio backends and specify your vision model.,
Reference Image Cards,"Load reference images, add speech/voice styles, or use Analyze to generate detailed descriptions using your local vision model.",
Main Subject Details,Define the primary character or element directly referenced in your uploaded images.,
Action & Motion,"Specify the exact timeline, action, and subject motion intended for the video.",
Fine-Tuning Controls,"Scrollable options for setting lighting, environment, camera, and negative prompts.",
Generated Prompt Output,"Clean, structured, copyable prompt block ready for MiniMax video generation.",

Prerequisites
You will need a local AI provider running in the background:

Ollama: Default server running at http://127.0.0.1:11434 with a vision model loaded (e.g., ollama run llava or LFM2.5-VL-3B).

LM Studio: Default server running at http://127.0.0.1:1234.

Installation & Launch
Clone the repository:

DOS
git clone [https://github.com/dog0311/DogoneGood-Minimax-Prompt-Generator-AI.git](https://github.com/dog0311/DogoneGood-Minimax-Prompt-Generator-AI.git)
cd DogoneGood-Minimax-Prompt-Generator-AI
Install core packages:

DOS
pip install pillow requests
Run the app:

DOS
python minimax_i2v_app.py
💡 How to Use
Configure Local AI Backend: Select Ollama or LM Studio and verify your vision model name in the top bar.

Add Reference Images: Click on any of the four image slots to load an image, then click Analyze to automatically populate a description of the subject and scene using your local LLM.

Fill Video Details: Specify the Main Subject, Action and timing, Scene, and Continuity instructions.

Set Video Parameters: Choose your desired duration, shot type, camera movement, style, and lighting preferences.

Generate Prompt: Click GENERATE COMPLETE PROMPT to receive your formatted MiniMax H3 prompt output. Use Copy or Save to export your result.

📄 License
Distributed under the MIT License.
