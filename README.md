# HandTrack Assistant

Control your system using just your hand.

This project uses your webcam to track hand gestures and trigger actions like changing brightness, volume, or taking screenshots.

---

## What it does

* Show **5 fingers** → open menu
* **1 finger** → show date & time
* **2 fingers** → brightness control
* **3 fingers** → volume control
* **4 fingers** → take screenshot
* **Fist (0 fingers)** → go back / exit

Inside brightness and volume:

* 1–5 fingers → set 20% to 100%

---

## How it works

The webcam captures your hand.
MediaPipe detects hand landmarks.
The program counts fingers and matches them to actions.

It also waits for a stable gesture, so random movement doesn’t trigger anything.

---

## Tech stack

* Python
* OpenCV
* MediaPipe
* PyAutoGUI
* screen-brightness-control
* pycaw

---

## Setup

Clone the repo:

```
git clone https://github.com/your-username/HandTrack-Assistant.git
cd HandTrack-Assistant
```

Install dependencies:

```
pip install opencv-python mediapipe pyautogui screen-brightness-control pycaw comtypes numpy
```

Add the model file:
Download `hand_landmarker.task` and place it in the project folder.

Run the project:

```
python main.py
```

---

## Controls

* Keep your hand steady for a second
* The system confirms before running any action
* There’s a short delay after each action

---


## Limitations

* Needs decent lighting
* Works best with one hand
* Camera quality affects accuracy
* Volume control may not work on all systems

---

