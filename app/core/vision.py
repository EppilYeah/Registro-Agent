import cv2
import mediapipe as mp
import threading
import time
import eel

class VisionHandler:
    def __init__(self):
        try:
            print("[VISAO]")
            self.mp_face_detection = mp.solutions.face_detection
            self.mp_drawing = mp.solutions.drawing_utils
            self.face_detection = self.mp_face_detection.FaceDetection(
                model_selection=0, 
                min_detection_confidence=0.5
            )
            self.cap = None
            self.rodando = False
            self.thread = None
            print("[VISAO] SUCESSO")
        except Exception as e:
            print(f"[VISAO] Erro : {e}")
            self.face_detection = None

    def iniciar(self):
        if self.rodando or not self.face_detection:
            print("[VISAO] já está rodando ou MediaPipe não inicializado")
            return
            
        self.rodando = True
        
        self.cap = cv2.VideoCapture(0)
        
        if not self.cap.isOpened():
            print("[VISAO]")
            self.rodando = False
            return
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        print("[VISAO]")
        
        self.thread = threading.Thread(target=self._loop_visao, daemon=True)
        self.thread.start()
        print("[VISAO]")

    def parar(self):
        print("[VISAO] PARANDO")
        self.rodando = False
        
        if self.cap:
            self.cap.release()
            
        if self.thread:
            self.thread.join(timeout=2)
            
        print("[VISAO] PARADA")

    def _loop_visao(self):
        print("[VISAO] RODANDO")
        
        fps_counter = 0
        fps_start = time.time()
        ultimo_update = time.time()
        
        while self.rodando and self.cap.isOpened():
            try:
                success, image = self.cap.read()
                
                if not success:
                    print("[VISAO] Falha ao capturar frame")
                    time.sleep(0.1)
                    continue

                image.flags.writeable = False
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = self.face_detection.process(image_rgb)

                encontrou_rosto = False
                cx, cy = 0.0, 0.0

                if results.detections:
                    for detection in results.detections:
                        bboxC = detection.location_data.relative_bounding_box
                        
                        face_center_x = bboxC.xmin + bboxC.width / 2
                        face_center_y = bboxC.ymin + bboxC.height / 2
                        
                        cx = face_center_x - 0.5
                        cy = face_center_y - 0.5
                        
                        cx = -cx * 15.0 
                        cy = cy * 10.0 
                        
                        encontrou_rosto = True
                        break  

                agora = time.time()
                if agora - ultimo_update > 0.033:  
                    try:
                        eel.jsAtualizarOlhar(cx, cy, encontrou_rosto)
                    except Exception as e:
                        pass
                    ultimo_update = agora

                fps_counter += 1
                if time.time() - fps_start > 5.0:  
                    fps = fps_counter / (time.time() - fps_start)
                    print(f"[VISAO] FPS: {fps:.1f} | Rosto: {'O' if encontrou_rosto else 'X'}")
                    fps_counter = 0
                    fps_start = time.time()

                time.sleep(0.01) 
                
            except Exception as e:
                print(f"[VISAO] Erro no loop: {e}")
                time.sleep(0.1)
        
        print("[VISAO] Loop de visão finalizado")

if __name__ == "__main__":
    print("=" * 50)
    print("TESTE DO VISIONHANDLER")
    print("=" * 50)
    
    vision = VisionHandler()
    
    if vision.face_detection:
        
        vision.iniciar()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nParando")
            vision.parar()
            print("Finalizado!")
    else:
        print("MediaPipe não inicializado ")