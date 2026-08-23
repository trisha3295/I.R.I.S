import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import time
import math

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True 

# ==========================================
# 1. EAR (EYE ASPECT RATIO) MATH
# ==========================================
def calculate_ear(eye_landmarks, face_landmarks, w, h):
    coords = []
    for idx in eye_landmarks:
        lm = face_landmarks.landmark[idx]
        coords.append(np.array([lm.x * w, lm.y * h]))
    
    v1 = math.dist(coords[1], coords[5])
    v2 = math.dist(coords[2], coords[4])
    h1 = math.dist(coords[0], coords[3])
    
    if h1 == 0:
        return 0.0
    return (v1 + v2) / (2.0 * h1)

# ==========================================
# 2. THE ONE EURO FILTER CLASS
# ==========================================
class OneEuroFilter:
    def __init__(self, t0, x0, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = x0
        self.dx_prev = 0.0
        self.t_prev = t0

    def smoothing_factor(self, t_e, cutoff):
        r = 2 * math.pi * cutoff * t_e
        return r / (r + 1)

    def __call__(self, t, x):
        t_e = t - self.t_prev
        if t_e <= 0.0: return x
        
        a_d = self.smoothing_factor(t_e, self.d_cutoff)
        dx = (x - self.x_prev) / t_e
        dx_hat = a_d * dx + (1.0 - a_d) * self.dx_prev
        
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        
        a = self.smoothing_factor(t_e, cutoff)
        x_hat = a * x + (1.0 - a) * self.x_prev
        
        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        
        return x_hat

# ==========================================
# 3. MAIN I.R.I.S. LOOP
# ==========================================
def main():
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1, 
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.85 
    )

    face_3d = np.array([
        (0.0, 0.0, 0.0),            
        (0.0, -330.0, -65.0),       
        (-225.0, 170.0, -135.0),    
        (225.0, 170.0, -135.0),     
        (-150.0, -150.0, -125.0),   
        (150.0, -150.0, -125.0)     
    ], dtype=np.float64)

    landmark_indices = [1, 152, 33, 263, 61, 291]
    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]
    
    screen_w, screen_h = pyautogui.size()

    # Window Setup (Centered & Windowed)
    window_name = 'I.R.I.S. - Controller'
    window_w, window_h = 1024, 768  
    center_x = int((screen_w - window_w) / 2)
    center_y = int((screen_h - window_h) / 2) - 50
    
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, window_w, window_h)
    cv2.moveWindow(window_name, center_x, center_y)

    t_start = time.time()
    filter_x = OneEuroFilter(t_start, screen_w / 2, min_cutoff=0.005, beta=0.001) 
    filter_y = OneEuroFilter(t_start, screen_h / 2, min_cutoff=0.005, beta=0.001)

    prev_x, prev_y = screen_w / 2, screen_h / 2
    
    # --- SPLIT DEADZONES ---
    DEADZONE_X = 22.0  # Wider: ignores left/right head-twist wobble
    DEADZONE_Y = 8.0   # Sensitive: lets you easily look up and down

    # --- BLINK & HOLD TIMER CONFIGURATION ---
    EAR_THRESHOLD = 0.15      
    CLICK_COOLDOWN = 1.0      
    last_click_time = 0.0
    
    BLINK_HOLD_TIME = 0.4     # Must hold eyes closed for 0.4 seconds to click
    blink_start_time = None   

    cap = cv2.VideoCapture(0)
    print("I.R.I.S. Active. Move mouse to corner to emergency stop.")

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            continue

        image = cv2.flip(image, 1)
        image_h, image_w, _ = image.shape
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        rgb_image.flags.writeable = False
        results = face_mesh.process(rgb_image)
        rgb_image.flags.writeable = True

        # Draw Control Box (Centered)
        box_w, box_h = int(image_w * 0.4), int(image_h * 0.4) 
        box_x1 = int(image_w/2 - box_w/2)
        box_y1 = int(image_h/2 - box_h/2)
        box_x2 = int(image_w/2 + box_w/2)
        box_y2 = int(image_h/2 + box_h/2)
        cv2.rectangle(image, (box_x1, box_y1), (box_x2, box_y2), (255, 255, 0), 2)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                
                # 1. CALCULATE BLINKS WITH HOLD TIMER
                left_ear = calculate_ear(LEFT_EYE, face_landmarks, image_w, image_h)
                right_ear = calculate_ear(RIGHT_EYE, face_landmarks, image_w, image_h)
                avg_ear = (left_ear + right_ear) / 2.0
                
                current_time = time.time()
                is_blinking = avg_ear < EAR_THRESHOLD

                # Smart Blink Logic
                if is_blinking:
                    if blink_start_time is None:
                        blink_start_time = current_time 
                    else:
                        hold_duration = current_time - blink_start_time
                        if hold_duration >= BLINK_HOLD_TIME:
                            if (current_time - last_click_time) > CLICK_COOLDOWN:
                                pyautogui.click()
                                last_click_time = current_time
                                blink_start_time = None 
                else:
                    blink_start_time = None

                # Print UI on screen
                cv2.putText(image, f"Live EAR: {avg_ear:.2f}", 
                            (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                if (current_time - last_click_time) < 0.5:
                    cv2.putText(image, "CLICK FIRED!", (30, 90), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

                # 2. CALCULATE HEAD POSE
                face_2d = []
                for idx in landmark_indices:
                    landmark = face_landmarks.landmark[idx]
                    x, y = int(landmark.x * image_w), int(landmark.y * image_h)
                    face_2d.append((x, y))
                    cv2.circle(image, (x, y), 3, (0, 255, 0), -1)
                
                face_2d = np.array(face_2d, dtype=np.float64)
                focal_length = 1 * image_w
                camera_matrix = np.array([
                    [focal_length, 0, image_w / 2],
                    [0, focal_length, image_h / 2],
                    [0, 0, 1]
                ], dtype=np.float64)
                dist_coeffs = np.zeros((4, 1), dtype=np.float64)

                success, rotation_vec, translation_vec = cv2.solvePnP(
                    face_3d, face_2d, camera_matrix, dist_coeffs
                )

                if success:
                    nose_3d_projection, _ = cv2.projectPoints(
                        np.array([(0.0, 0.0, 1000.0)]), 
                        rotation_vec, translation_vec, camera_matrix, dist_coeffs
                    )
                    
                    laser_x = int(nose_3d_projection[0][0][0])
                    laser_y = int(nose_3d_projection[0][0][1])
                    cv2.circle(image, (laser_x, laser_y), 8, (0, 0, 255), -1)

                    raw_x = np.interp(laser_x, [box_x1, box_x2], [0, screen_w])
                    raw_y = np.interp(laser_y, [box_y1, box_y2], [0, screen_h])
                    
                    smooth_x = filter_x(current_time, raw_x)
                    smooth_y = filter_y(current_time, raw_y)
                    
                    # Independent X and Y movement checks
                    delta_x = abs(smooth_x - prev_x)
                    delta_y = abs(smooth_y - prev_y)
                    
                    # Only move mouse if eyes are open and movement clears split deadzones
                    if not is_blinking and (delta_x > DEADZONE_X or delta_y > DEADZONE_Y):
                        try:
                            pyautogui.moveTo(smooth_x, smooth_y)
                            prev_x, prev_y = smooth_x, smooth_y
                        except pyautogui.FailSafeException:
                            print("Failsafe triggered! Exiting...")
                            cap.release()
                            cv2.destroyAllWindows()
                            return

        cv2.imshow(window_name, image)
        if cv2.waitKey(5) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()