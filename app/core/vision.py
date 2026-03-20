import cv2  # pylint: disable=no-member
import mediapipe as mp
import numpy as np
import threading
import time
import math
import settings

class VisionHandler:
    def __init__(self, funcao_js=None):
        self.funcao_js = funcao_js
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(min_detection_confidence=0.6)

        self.prev_gray = None

        self.cap = None
        self.rodando = False
        self.thread = None

        self.foco_atual_x = 0
        self.foco_atual_y = 0
        self.tempo_para_perder_foco = 0

        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self._ultimo_envio_js = 0.0

    def iniciar(self):
        if self.rodando: return
        self.rodando = True
        self.cap = cv2.VideoCapture(0)
        self.thread = threading.Thread(target=self._loop_visao)
        self.thread.daemon = True
        self.thread.start()

    def parar(self):
        self.rodando = False
        if self.cap:
            self.cap.release()

    def _loop_visao(self):
        print("[VISAO] ")

        TEMPO_MEMORIA = 2.0
        FACTOR_SUAVIZACAO = 0.15
        AREA_MINIMA_MOVIMENTO = 3000
        DEADZONE = 0.2
        INTERVALO_JS = 0.05

        frame_count = 0

        while self.rodando and self.cap.isOpened():
            if not settings.get("camera_ativa"):
                time.sleep(0.2)
                continue

            success, frame = self.cap.read()
            if not success:
                time.sleep(1)
                continue

            frame_count += 1
            if frame_count % 2 != 0:
                continue

            frame = cv2.resize(frame, (500, 400))
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_frame = cv2.GaussianBlur(gray_frame, (25, 25), 0)

            height, width = frame.shape[:2]

            rosto_encontrado = False
            rosto_cx, rosto_cy = 0, 0

            results = self.face_detection.process(rgb_frame)
            if results.detections:
                for detection in results.detections:
                    bboxC = detection.location_data.relative_bounding_box
                    cx_raw = bboxC.xmin + bboxC.width / 2
                    cy_raw = bboxC.ymin + bboxC.height / 2
                    rosto_cx = (cx_raw - 0.5) * -15.0
                    rosto_cy = (cy_raw - 0.5) * 10.0
                    rosto_encontrado = True
                    break

            movimento_encontrado = False
            mov_cx, mov_cy = 0, 0

            if self.prev_gray is not None:
                delta_frame = cv2.absdiff(self.prev_gray, gray_frame)
                thresh = cv2.threshold(delta_frame, 40, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=3)
                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                maior_area = 0
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area < AREA_MINIMA_MOVIMENTO: continue

                    if area > maior_area:
                        maior_area = area
                        (x, y, w, h) = cv2.boundingRect(contour)
                        cx_raw = (x + w / 2) / width
                        cy_raw = (y + h / 2) / height
                        target_x = (cx_raw - 0.5) * -15.0
                        target_y = (cy_raw - 0.5) * 10.0

                        distancia_do_rosto = 100
                        if rosto_encontrado:
                            distancia_do_rosto = math.sqrt((target_x - rosto_cx)**2 + (target_y - rosto_cy)**2)

                        if not rosto_encontrado or (distancia_do_rosto > 4.0):
                            mov_cx = target_x
                            mov_cy = target_y
                            movimento_encontrado = True

            self.prev_gray = gray_frame

            agora = time.time()
            alvo_final_x, alvo_final_y = 0, 0
            ativo = False

            if movimento_encontrado:
                alvo_final_x = mov_cx
                alvo_final_y = mov_cy
                self.foco_atual_x = mov_cx
                self.foco_atual_y = mov_cy
                self.tempo_para_perder_foco = agora + TEMPO_MEMORIA
                ativo = True

            elif rosto_encontrado:
                if agora < self.tempo_para_perder_foco:
                    alvo_final_x = self.foco_atual_x
                    alvo_final_y = self.foco_atual_y
                else:
                    alvo_final_x = rosto_cx
                    alvo_final_y = rosto_cy
                ativo = True

            else:
                if agora < self.tempo_para_perder_foco:
                    alvo_final_x = self.foco_atual_x
                    alvo_final_y = self.foco_atual_y
                    ativo = True
                else:
                    ativo = False

            diff_x = abs(alvo_final_x - self.smooth_x)
            diff_y = abs(alvo_final_y - self.smooth_y)

            if diff_x >= DEADZONE or diff_y >= DEADZONE:
                self.smooth_x = (alvo_final_x * FACTOR_SUAVIZACAO) + (self.smooth_x * (1 - FACTOR_SUAVIZACAO))
                self.smooth_y = (alvo_final_y * FACTOR_SUAVIZACAO) + (self.smooth_y * (1 - FACTOR_SUAVIZACAO))

            if self.funcao_js and (agora - self._ultimo_envio_js) >= INTERVALO_JS:
                ativo_js = "true" if ativo else "false"
                try:
                    self.funcao_js(f"window.jsAtualizarOlhar({self.smooth_x:.3f}, {self.smooth_y:.3f}, {ativo_js})")
                    self._ultimo_envio_js = agora
                except Exception as e:
                    print(f"[VISAO] Erro JS: {e}")

            time.sleep(0.01)