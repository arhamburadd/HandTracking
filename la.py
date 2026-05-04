import cv2
import mediapipe as mp
import time
import math
import numpy as np
import datetime
import os
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import pyautogui
import screen_brightness_control as sbc

try:
    from pycaw.pycaw import AudioUtilities
    devices = AudioUtilities.GetSpeakers()
    volume_control = devices.EndpointVolume
except Exception as e:
    print(f"Failed to initialize pycaw volume control: {e}")
    volume_control = None

MODEL_PATH = 'hand_landmarker.task'
CONSISTENCY_THRESHOLD = 30
TIMEOUT_DURATION = 10.0
COOLDOWN_DURATION = 2.0

current_mode = "DEFAULT"
last_action_time = time.time()
previous_finger_count = -1
consistency_count = 0
cooldown_end_time = 0

popup_message = ""
popup_start_time = 0

def show_popup(msg):
    global popup_message, popup_start_time
    popup_message = msg
    popup_start_time = time.time()

def count_fingers(hand_landmarks, handedness_label):
    count = 0
    tips = [4, 8, 12, 16, 20]
    pips = [3, 6, 10, 14, 18]
    
    for i in range(1, 5):
        if hand_landmarks[tips[i]].y < hand_landmarks[pips[i]].y:
            count += 1
            
    thumb_tip_x = hand_landmarks[4].x
    thumb_ip_x = hand_landmarks[3].x
    if handedness_label == 'Right':
        if thumb_tip_x > thumb_ip_x:
            count += 1
    elif handedness_label == 'Left':
        if thumb_tip_x < thumb_ip_x:
            count += 1
    return count

def draw_ui(frame):

    cv2.rectangle(frame, (10, 10), (450, 130), (30, 30, 30), -1)
    cv2.putText(frame, f"MODE: {current_mode}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
    
    instruction = ""
    if current_mode == "DEFAULT":
        instruction = "Show 5 fingers -> MENU"
    elif current_mode == "MENU":
        instruction = "1:Time 2:Bright 3:Vol 4:Shot (Fist to EXIT)"
    elif current_mode in ["BRIGHTNESS", "VOLUME"]:
        instruction = "1-5 to set 20-100% (Fist to EXIT)"
        
    cv2.putText(frame, instruction, (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    if current_mode == "MENU":
        cv2.rectangle(frame, (10, 140), (250, 310), (30, 30, 30), -1)
        cv2.putText(frame, "1 -> Date & Time", (20, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        cv2.putText(frame, "2 -> Brightness", (20, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        cv2.putText(frame, "3 -> Volume", (20, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        cv2.putText(frame, "4 -> Screenshot", (20, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        cv2.putText(frame, "Fist -> Exit", (20, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
    global consistency_count
    if consistency_count > 0:
        bar_width = int((consistency_count / CONSISTENCY_THRESHOLD) * 200)
        cv2.rectangle(frame, (10, frame.shape[0] - 40), (210, frame.shape[0] - 20), (50, 50, 50), -1)
        cv2.rectangle(frame, (10, frame.shape[0] - 40), (10 + bar_width, frame.shape[0] - 20), (0, 255, 0), -1)
        cv2.putText(frame, "Confirming...", (10, frame.shape[0] - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    if time.time() - popup_start_time < 3.0 and popup_message != "":
        lines = popup_message.split('|')
        
        max_w = 0
        total_h = 0
        line_heights = []
        for line in lines:
            (w, h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_DUPLEX, 1.2, 2)
            if w > max_w: max_w = w
            total_h += h + 20
            line_heights.append(h)
            
        box_x = 480
        box_y = 10
        
        padding = 30

        cv2.rectangle(frame, (box_x, box_y), 
                             (box_x + max_w + 2*padding, box_y + total_h + 2*padding - 20), 
                             (25, 25, 25), cv2.FILLED)
        cv2.rectangle(frame, (box_x, box_y), 
                             (box_x + max_w + 2*padding, box_y + total_h + 2*padding - 20), 
                             (0, 200, 255), 2)
                             
        current_y = box_y + padding + line_heights[0]
        for line in lines:
            (w, h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_DUPLEX, 1.2, 2)
            
            line_x = box_x + padding + (max_w - w) // 2
            cv2.putText(frame, line, (line_x + 3, current_y + 3), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 0, 0), 3)
            cv2.putText(frame, line, (line_x, current_y), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)
            current_y += h + 20

def track_consistency(fingers):
    global previous_finger_count, consistency_count, last_action_time
    if fingers == previous_finger_count:
        consistency_count += 1
    else:
        previous_finger_count = fingers
        consistency_count = 1
        
    if consistency_count >= CONSISTENCY_THRESHOLD:
        consistency_count = 0
        last_action_time = time.time()
        return True
    return False

def switch_mode(new_mode):
    global current_mode, consistency_count, previous_finger_count, last_action_time
    current_mode = new_mode
    consistency_count = 0
    previous_finger_count = -1
    last_action_time = time.time()
    if current_mode != "DEFAULT":
        show_popup(f"{new_mode} MODE")

def start_cooldown():
    global cooldown_end_time, previous_finger_count, consistency_count
    cooldown_end_time = time.time() + COOLDOWN_DURATION
    previous_finger_count = -1
    consistency_count = 0

def handle_default_mode(fingers):
    if fingers == 5:
        if track_consistency(fingers):
            switch_mode("MENU")

def handle_menu_mode(fingers):
    if fingers == 0:
        if track_consistency(fingers):
            switch_mode("DEFAULT")
    elif fingers == 1:
        if track_consistency(fingers):
            current_time = datetime.datetime.now().strftime("%I:%M:%S %p|%B %d, %Y")
            show_popup(current_time)
            start_cooldown()
    elif fingers == 2:
        if track_consistency(fingers):
            switch_mode("BRIGHTNESS")
    elif fingers == 3:
        if track_consistency(fingers):
            switch_mode("VOLUME")
    elif fingers == 4:
        if track_consistency(fingers):
            filename = f"screenshot_{int(time.time())}.png"
            pyautogui.screenshot(filename)
            show_popup("Screenshot Saved!")
            start_cooldown()

def handle_brightness_mode(fingers):
    if fingers == 0:
        if track_consistency(fingers):
            switch_mode("MENU")
    elif fingers in [1, 2, 3, 4, 5]:
        if track_consistency(fingers):
            target = fingers * 20
            try:
                sbc.set_brightness(target)
                show_popup(f"Brightness: {target}%")
                start_cooldown()
            except Exception as e:
                show_popup("Brightness format error")

def handle_volume_mode(fingers):
    if fingers == 0:
        if track_consistency(fingers):
            switch_mode("MENU")
    elif fingers in [1, 2, 3, 4, 5]:
        if track_consistency(fingers):
            target_pct = fingers * 20
            if volume_control:
                try:
                    volume_control.SetMasterVolumeLevelScalar(target_pct / 100.0, None)
                    show_popup(f"Volume: {target_pct}%")
                    start_cooldown()
                except Exception as e:
                    show_popup("Volume adj failed")
            else:
                show_popup(f"SIMULATED VOLUME: {target_pct}%")
                start_cooldown()

def main():
    global current_mode, last_action_time, consistency_count

    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=1)
    detector = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    

    cv2.namedWindow('Gesture Assistant', cv2.WINDOW_NORMAL)
    
    while True:
        success, frame = cap.read()
        if not success:
            continue

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = detector.detect(mp_image)
        
        fingers = -1
        
        if detection_result.hand_landmarks:
            hand_landmarks = detection_result.hand_landmarks[0]
            for landmark in hand_landmarks:
                x = int(landmark.x * frame.shape[1])
                y = int(landmark.y * frame.shape[0])
                cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

            handedness_label = detection_result.handedness[0][0].category_name
            fingers = count_fingers(hand_landmarks, handedness_label)
            
            
            last_action_time = time.time()
        else:
           
            consistency_count = 0
            
        if current_mode != "DEFAULT" and (time.time() - last_action_time) > TIMEOUT_DURATION:
            switch_mode("DEFAULT")
            show_popup("Timeout: Returned to DEFAULT")
            
        if time.time() < cooldown_end_time:
            cv2.putText(frame, "Waiting (Cooldown)...", (10, frame.shape[0] - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            fingers = -1
        
        if fingers != -1:
            if current_mode == "DEFAULT":
                handle_default_mode(fingers)
            elif current_mode == "MENU":
                handle_menu_mode(fingers)
            elif current_mode == "BRIGHTNESS":
                handle_brightness_mode(fingers)
            elif current_mode == "VOLUME":
                handle_volume_mode(fingers)

        draw_ui(frame)

        cv2.imshow('Gesture Assistant', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
