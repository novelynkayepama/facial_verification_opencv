import cv2
import numpy as np
import os

# Load LBPH model
if not os.path.exists("trained_model.yml"):
    print("[ERROR] Model not found. Run 'train_model.py' first.")
    exit()

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read("trained_model.yml")

# Load face cascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Start webcam
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Could not open webcam.")
    exit()

print("[INFO] Press 's' to capture selfie for verification.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] Failed to grab frame.")
        break

    cv2.imshow("Selfie Verification", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s'):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        if len(faces) == 0:
            print("[ERROR] No face detected in selfie.")
            continue

        x, y, w, h = faces[0]
        face_roi = gray[y:y+h, x:x+w]

        label, confidence = recognizer.predict(face_roi)
        if confidence < 70:  # lower = better match
            print(f"[SUCCESS] Selfie matches ID! Confidence={confidence:.2f}")
        else:
            print(f"[FAIL] Selfie does NOT match ID. Confidence={confidence:.2f}")
        break

    elif key == ord('q'):
        print("[INFO] Quitting without verification.")
        break

cap.release()
cv2.destroyAllWindows()
