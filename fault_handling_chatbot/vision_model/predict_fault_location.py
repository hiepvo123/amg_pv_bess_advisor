import os
import random

# Trong thuc te, ban se import Ultralytics YOLO o day:
# from ultralytics import YOLO

MODEL_WEIGHTS = "best.pt"

class CustomVisionModel:
    def __init__(self):
        print(f"Loading custom model weights from {MODEL_WEIGHTS}...")
        # self.model = YOLO(MODEL_WEIGHTS)
        
    def predict(self, image_path: str, fault_name: str):
        """
        Gia lap qua trinh model phan tich anh va tim ra bounding box cua thiet bi bi loi.
        Tra ve: (x, y, w, h) - toa do tren hinh anh (hoac None neu khong thay).
        """
        if not os.path.exists(image_path):
            print(f"Khong tim thay anh: {image_path}")
            return None
            
        print(f"Dang chay inference tren {image_path} de tim {fault_name}...")
        # results = self.model(image_path)
        # for box in results[0].boxes: ...
        
        # Gia lap ket qua (mock data)
        # random toa do (x, y, width, height)
        x = random.randint(50, 200)
        y = random.randint(50, 200)
        w = random.randint(50, 100)
        h = random.randint(50, 100)
        
        return [x, y, w, h]

# Khoi tao model toan cuc de tai dung
_model_instance = None

def get_vision_model():
    global _model_instance
    if _model_instance is None:
        _model_instance = CustomVisionModel()
    return _model_instance

def find_fault_on_diagram(diagram_filename: str, fault_name: str):
    """
    Goi tu Agent, truyen vao ten file va ten loi.
    Tra ve duong dan anh va toa do (neu tim thay).
    """
    model = get_vision_model()
    # static directory mapping
    # Hien tai dang chay tu thu muc root (main.py) nen duong dan phai la static/diagrams/
    image_path = os.path.join("static", "diagrams", diagram_filename)
    
    coords = model.predict(image_path, fault_name)
    if coords:
        return f"/static/diagrams/{diagram_filename}", coords
    return "", []
