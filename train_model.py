import cv2
import os
import numpy as np

UPLOADS_DIR = "uploads"
ID_PHOTO = os.path.join(UPLOADS_DIR, "id_photo.jpg")

if not os.path.exists(ID_PHOTO):
    print("[ERROR] ID photo not found in 'uploads/' folder.")
    exit()

# Load face cascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Read image in grayscale
image = cv2.imread(ID_PHOTO, cv2.IMREAD_GRAYSCALE)
faces = face_cascade.detectMultiScale(image, scaleFactor=1.1, minNeighbors=5)

if len(faces) == 0:
    print("[ERROR] No face detected in the ID photo.")
    exit()

x, y, w, h = faces[0]
face_roi = image[y:y+h, x:x+w]

# Train LBPH recognizer
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.train([face_roi], np.array([1]))  # label 1 = the applicant

# Save model
recognizer.write("trained_model.yml")
print("[INFO] LBPH model trained and saved as 'trained_model.yml'")
