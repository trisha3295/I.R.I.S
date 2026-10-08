import sys, traceback, time, os, numpy as np
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
import cv2

# Patch display so no window opens
cv2.imshow = lambda *a, **k: None
cv2.waitKey = lambda *a, **k: -1
cv2.namedWindow = lambda *a, **k: None
cv2.setMouseCallback = lambda *a, **k: None
cv2.destroyAllWindows = lambda *a, **k: None

try:
    from iris_engine.camera import ThreadedWebcamStream
    from iris_engine.preprocessor import LightingCompensator
    from iris_engine.tracker import FastFaceMeshTracker
    from iris_engine.pose_estimator import HeadPoseEstimator
    from iris_engine.gesture_engine import GestureEngine
    from iris_engine.controller import WindowsCursorController
    from iris_engine.iris_detector import IrisGazeDetector
    from iris_engine.navigation import PointerNavigationEngine

    BASE_DIR = r'C:\I.R.I.S'
    YUNET = BASE_DIR + r'\models\face_detection_yunet.onnx'
    FM    = BASE_DIR + r'\models\FaceMesh.onnx'

    controller = WindowsCursorController(enable_sound=False)
    sw, sh = controller.get_screen_size()

    lighting  = LightingCompensator()
    pose      = HeadPoseEstimator()
    iris_d    = IrisGazeDetector()
    ge        = GestureEngine(
                    ear_threshold_ratio=0.68, asymmetry_threshold=0.28,
                    wink_hold_time=0.18, double_click_hold_time=0.55, click_cooldown=0.55)
    nav       = PointerNavigationEngine(
                    screen_w=sw, screen_h=sh,
                    default_method=PointerNavigationEngine.METHOD_BALLISTICS_RELATIVE,
                    base_sensitivity=1.0, enable_dwell_click=False,
                    dwell_time=0.70, dwell_radius=25.0)
    tracker   = FastFaceMeshTracker(
                    model_yunet_path=YUNET, model_facemesh_path=FM,
                    input_size=(640, 480), redetect_interval=90)

    cam = ThreadedWebcamStream(src=0, width=640, height=480, fps=30).start()
    time.sleep(0.5)

    for i in range(8):
        frame = cam.read()
        if frame is None:
            print(f"Frame {i}: None")
            continue
        frame = cv2.flip(frame, 1)
        ih, iw, _ = frame.shape
        rgb = lighting.process(frame)
        lm  = tracker.detect_and_track(rgb)
        pitch = 0.0
        if lm is not None:
            ok, pt, rvec, tvec = pose.estimate_pose(lm, iw, ih)
            if ok and pt is not None:
                pitch, _, _ = pose.get_euler_angles(rvec)
            g = ge.process_frame(lm, time.time(), pitch_angle=pitch, is_mirrored=True)
            iris_d.estimate_iris_gaze(frame, lm, is_blinking=g.get('is_blinking', False))
            trigger = g.get('trigger_action')
            l_ear   = g.get('left_ear', 0)
            r_ear   = g.get('right_ear', 0)
            print(f"Frame {i}: trigger={trigger}  L={l_ear:.3f}  R={r_ear:.3f}  pitch={pitch:.1f}")
        else:
            print(f"Frame {i}: no face detected")
        time.sleep(0.05)

    cam.stop()
    print("\nPIPELINE TEST PASSED")

except Exception as e:
    traceback.print_exc()
    sys.exit(1)
