import cv2

print("OpenCV version:", cv2.__version__)
print("'face' module available?", hasattr(cv2, 'face'))

# Try creating LBPH recognizer
try:
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    print("LBPH Face Recognizer works!")
except AttributeError:
    print("cv2.face is not available!")
