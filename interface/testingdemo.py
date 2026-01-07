# -------------------------------------------------------------
# Trixant Rover Control - ROS 2 INTEGRATED
# -------------------------------------------------------------

import sys
import os
import time
import json
import csv
from datetime import datetime
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
import cv2
import threading
import socket

# --- ROS 2 INTEGRATION ---
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

# -----------------------------------------
# File paths
# -----------------------------------------
BASE = Path.cwd()
CAPTURE_DIR = BASE / "captures"
LOG_DIR = BASE / "logs"
TELEMETRY_CSV = LOG_DIR / "telemetry.csv"
CAPTURE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# --- ROS 2 INTEGRATION ---
# Set your stream sources here.
# ROS topics MUST start with a "/"
# Local cameras are strings: "0", "1", etc.
DEFAULT_STREAMS = [
    "/camera/camera/color/image_raw",  # Cam 1: RealSense
    "0",                               # Cam 2: Laptop Webcam
    "",                                # Cam 3: Empty
    "2",                                # Cam 4: Empty
    ""                                 # Default Main (empty)
]


# -------------------------------------------------------------
# VIDEO THREAD (For non-ROS cameras)
# -------------------------------------------------------------
class VideoThread(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)

    def __init__(self, src):
        super().__init__()
        self.src = src
        self.running = False
        self.cap = None

    def run(self):
        self.running = True
        if not self.src:
            return

        src = int(self.src) if isinstance(self.src, str) and self.src.isdigit() else self.src
        
        # --- MODIFIED: Use appropriate backend for local cams ---
        if isinstance(src, int):
            self.cap = cv2.VideoCapture(src, cv2.CAP_V4L2) # V4L2 for Linux
            if not self.cap.isOpened():
                print(f"Retrying Cam {src} with default backend...")
                self.cap = cv2.VideoCapture(src) # Fallback
        else:
             self.cap = cv2.VideoCapture(src) # For RTSP etc.


        if not self.cap or not self.cap.isOpened():
            print(f"[ERROR] Cannot open stream: {self.src}")
            self.running = False
            return

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.02)
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QtGui.QImage(rgb.data, w, h, ch*w, QtGui.QImage.Format_RGB888)
            self.frame_ready.emit(img)
            QtCore.QThread.msleep(20) # ~50fps cap

    def stop(self):
        self.running = False
        try:
            if self.cap:
                self.cap.release()
        except:
            pass
        self.quit()
        self.wait()


# -------------------------------------------------------------
# CAMERA WIDGET (Now ROS-Aware)
# -------------------------------------------------------------
class CameraWidget(QtWidgets.QWidget):
    # --- MODIFIED: Added ros_node and ros_signal ---
    def __init__(self, title, ros_node, ros_signal, url=""):
        super().__init__()
        self.stream_url = url
        self.last_img = None
        self.thread = None # For local VideoThread
        
        # --- ROS 2 INTEGRATION ---
        self.ros_node = ros_node
        self.ros_frame_ready_signal = ros_signal
        self.ros_sub = None
        self.bridge = CvBridge()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.label = QtWidgets.QLabel(title)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("color: #8ab4ff; font-size:14px;")

        self.display = QtWidgets.QLabel("No Stream")
        self.display.setFixedSize(260, 150)
        self.display.setAlignment(QtCore.Qt.AlignCenter)
        self.display.setStyleSheet(
            "background:#222; border:1px solid #444; color:white; font-size:12px;"
        )

        layout.addWidget(self.label)
        layout.addWidget(self.display)

    def start(self, url=None):
        if url:
            self.stream_url = url
        self.stop() # Stop any previous stream

        if not self.stream_url:
            self.display.setText("No Stream")
            return

        # --- ROS 2 INTEGRATION: Check if URL is a ROS topic ---
        if self.stream_url.startswith("/"):
            try:
                self.ros_sub = self.ros_node.create_subscription(
                    Image,
                    self.stream_url,
                    self.ros_callback, # This widget's own callback
                    10
                )
                print(f"[INFO] Subscribing {self.label.text()} to {self.stream_url}")
                self.display.setText(f"Waiting for topic...\n{self.stream_url}")
            except Exception as e:
                print(f"[ERROR] Failed to create ROS subscription: {e}")
                self.display.setText("ROS Sub Failed")
        
        # --- Default: Use regular VideoThread ---
        else:
            self.thread = VideoThread(self.stream_url)
            self.thread.frame_ready.connect(self.update_frame) # Direct connection
            self.thread.start()

    # --- ROS 2 INTEGRATION: Callback for ROS subscriber ---
    def ros_callback(self, msg):
        """ROS THREAD: Converts msg, emits thread-safe signal."""
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QtGui.QImage(rgb.data, w, h, ch*w, QtGui.QImage.Format_RGB888).copy()
            
            # Emit the main window's signal, passing *self* (this widget) and the image
            self.ros_frame_ready_signal.emit(self, qimg)
        except Exception as e:
            self.ros_node.get_logger().error(f"Frame processing error: {e}")

    @QtCore.pyqtSlot(QtGui.QImage)
    def update_frame(self, qimg):
        """MAIN THREAD: Updates the display pixmap."""
        self.last_img = qimg
        pix = QtGui.QPixmap.fromImage(qimg).scaled(
            self.display.width(), self.display.height(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.display.setPixmap(pix)

    def stop(self):
        # Stop local camera thread
        if self.thread:
            self.thread.stop()
            self.thread = None
        
        # --- ROS 2 INTEGRATION: Stop ROS subscriber ---
        if self.ros_sub:
            try:
                self.ros_node.destroy_subscription(self.ros_sub)
            except Exception as e:
                print(f"[WARN] Error destroying subscription: {e}")
            self.ros_sub = None

    def snapshot(self):
        return self.last_img


# -------------------------------------------------------------
# TCP CLIENT (No changes)
# -------------------------------------------------------------
class TCPClient(QtCore.QObject):
    telemetry = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.sock = None
        self.running = False

    def connect(self, host, port):
        self.disconnect()
        self.sock = socket.socket()
        self.sock.connect((host, port))
        self.running = True
        threading.Thread(target=self.listen, daemon=True).start()

    def listen(self):
        buf = b""
        while self.running:
            try:
                d = self.sock.recv(4096)
                if not d:
                    break
                buf += d

                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        self.telemetry.emit(json.loads(line.decode()))
                    except:
                        pass
            except:
                break

    def send(self, obj):
        if self.sock:
            try:
                self.sock.sendall((json.dumps(obj) + "\n").encode())
            except:
                pass

    def disconnect(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except:
            pass
        self.sock = None


# -------------------------------------------------------------
# MAIN GUI
# -------------------------------------------------------------
class RoverControl(QtWidgets.QMainWindow):
    # --- ROS 2 INTEGRATION: Thread-safe signal for ROS frames ---
    # This signal will carry the CameraWidget object and the QImage
    ros_frame_ready = QtCore.pyqtSignal(QtWidgets.QWidget, QtGui.QImage)

    # --- MODIFIED: Accept ROS 2 node ---
    def __init__(self, node):
        super().__init__()
        self.setWindowTitle("Trixant Rover Control")
        self.resize(1400, 850)
        self.setStyleSheet("background:#111; color:white;")

        # --- ROS 2 INTEGRATION ---
        self.node = node
        # Connect the thread-safe signal to its slot
        self.ros_frame_ready.connect(self.on_ros_frame)

        self.streams = DEFAULT_STREAMS.copy()
        self.client = TCPClient()
        self.client.telemetry.connect(self.on_telemetry)

        self.setup_ui()
        self.keys = set()

        # Start all camera widgets
        for i, cam in enumerate(self.cams):
            cam.start(self.streams[i])
        
        # Start the main cam with its default stream (if any)
        self.main_cam.start(self.streams[4])

    # ---------------------------------------------------------
    def setup_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main = QtWidgets.QVBoxLayout(central)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(6)

        # ==================== TOP BAR ====================
        top = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel("Trixant Rover Control")
        lbl.setStyleSheet("font-size:22px; font-weight:bold; color:#7dc3ff;")
        top.addWidget(lbl)
        top.addStretch()

        btn_conn = QtWidgets.QPushButton("Connect")
        btn_conn.setStyleSheet("padding:6px; font-size:14px;")
        btn_conn.clicked.connect(self.do_connect)
        top.addWidget(btn_conn)

        main.addLayout(top)

        # ==================== CAMERA GRID ====================
        self.cams = []
        for i in range(4):
            # --- MODIFIED: Pass node and signal to CameraWidget ---
            cw = CameraWidget(
                f"Camera {i+1}", 
                self.node, 
                self.ros_frame_ready
            )
            cw.display.mousePressEvent = self.make_swap_handler(cw)
            self.cams.append(cw)

        mid = QtWidgets.QHBoxLayout()
        main.addLayout(mid, stretch=1)

        left_spacer = QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        right_spacer = QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)

        mid.addItem(left_spacer)

        # ==================== CENTER PANEL ====================
        center = QtWidgets.QVBoxLayout()
        center.setSpacing(8)

        # Top cams
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(self.cams[0])
        top_row.addWidget(self.cams[1])
        center.addLayout(top_row)

        # Main cam
        # --- MODIFIED: Pass node and signal to CameraWidget ---
        self.main_cam = CameraWidget(
            "Main Camera", 
            self.node, 
            self.ros_frame_ready
        )
        self.main_cam.display.setFixedSize(800, 450)
        self.main_cam.label.setVisible(False)
        center.addWidget(self.main_cam, alignment=QtCore.Qt.AlignCenter)

        # Bottom cams
        bot_row = QtWidgets.QHBoxLayout()
        bot_row.setSpacing(8)
        bot_row.addWidget(self.cams[2])
        bot_row.addWidget(self.cams[3])
        center.addLayout(bot_row)

        # Capture button
        cap_row = QtWidgets.QHBoxLayout()
        self.btn_cap = QtWidgets.QPushButton("Capture")
        self.btn_cap.setStyleSheet("padding:6px; font-size:14px;")
        self.btn_cap.clicked.connect(self.capture)
        cap_row.addStretch()
        cap_row.addWidget(self.btn_cap)
        cap_row.addStretch()
        center.addLayout(cap_row)

        mid.addLayout(center, stretch=3)

        # ==================== RIGHT MODULE PANEL ====================
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(10)

        # ABEx + Arm buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_abex = QtWidgets.QPushButton("ABEx")
        self.btn_arm = QtWidgets.QPushButton("Arm")

        for b in (self.btn_abex, self.btn_arm):
            b.setFixedHeight(36)
            b.setStyleSheet("background:#2a82da; color:white; font-size:16px; border-radius:4px; padding:4px;")

        btn_row.addWidget(self.btn_abex)
        btn_row.addWidget(self.btn_arm)

        right.addLayout(btn_row)

        # Right module panel
        self.module_panel = QtWidgets.QFrame()
        self.module_panel.setMinimumWidth(330)
        self.module_panel.setStyleSheet("border:1px solid #333; background:#1a1a1a;")
        self.module_panel_layout = QtWidgets.QVBoxLayout(self.module_panel)
        self.module_panel_layout.addWidget(QtWidgets.QLabel("Module Panel"))
        right.addWidget(self.module_panel, stretch=1)

        mid.addLayout(right, stretch=1)
        mid.addItem(right_spacer)

        # ==================== BOTTOM GPS + IMU ====================
        bottom = QtWidgets.QHBoxLayout()
        self.lbl_gps = QtWidgets.QLabel("GPS: lon=0.0000  lat=0.0000")
        self.lbl_imu = QtWidgets.QLabel("IMU: x=0 y=0 z=0")

        self.lbl_gps.setStyleSheet("font-size:16px; color:#8ab4ff;")
        self.lbl_imu.setStyleSheet("font-size:16px; color:#8ab4ff;")

        bottom.addWidget(self.lbl_gps)
        bottom.addStretch()
        bottom.addWidget(self.lbl_imu)
        main.addLayout(bottom)

    # -------------------------------------------------------------
    # FIXED LAMBDA BINDING (No changes)
    # -------------------------------------------------------------
    def make_swap_handler(self, cam):
        return lambda e: self.swap_to_main(cam)

    # --- THIS NOW WORKS FOR ROS STREAMS TOO! ---
    def swap_to_main(self, cam):
        img = cam.snapshot()
        if img:
            pix = QtGui.QPixmap.fromImage(img).scaled(
                self.main_cam.display.width(),
                self.main_cam.display.height(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.main_cam.display.setPixmap(pix)

        # This works because main_cam.start() is now ROS-aware
        self.main_cam.start(cam.stream_url)
        print("[INFO] Switched main to", cam.stream_url)

    # -------------------------------------------------------------
    # --- ROS 2 INTEGRATION: Slot for thread-safe GUI updates ---
    @QtCore.pyqtSlot(QtWidgets.QWidget, QtGui.QImage)
    def on_ros_frame(self, camera_widget, qimg):
        """MAIN THREAD: Safely updates the GUI for ROS Cams."""
        # This slot receives the signal from the ROS callback
        # and safely calls the widget's *actual* update function
        if isinstance(camera_widget, CameraWidget):
            camera_widget.update_frame(qimg)

    # -------------------------------------------------------------
    def capture(self):
        img = self.main_cam.snapshot()
        if not img:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = CAPTURE_DIR / f"cap_{ts}.png"
        img.save(str(fname))
        print("[Saved]", fname)

    # -------------------------------------------------------------
    def on_telemetry(self, t):
        gps = t.get("gps", {})
        imu = t.get("imu", {})
        lon = gps.get("lon", "0")
        lat = gps.get("lat", "0")
        x = imu.get("x", "0")
        y = imu.get("y", "0")
        z = imu.get("z", "0")
        self.lbl_gps.setText(f"GPS: lon={lon}  lat={lat}")
        self.lbl_imu.setText(f"IMU: x={x} y={y} z={z}")

    # -------------------------------------------------------------
    def do_connect(self):
        host, ok = QtWidgets.QInputDialog.getText(self, "Connect", "Host:", text="127.0.0.1")
        if not ok:
            return
        port, ok = QtWidgets.QInputDialog.getInt(self, "Port", "Port:", value=9000)
        if not ok:
            return
        try:
            self.client.connect(host, port)
        except Exception as e:
            print("Connect failed:", e)

    # -------------------------------------------------------------
    def keyPressEvent(self, e):
        keys = {QtCore.Qt.Key_W:"fwd", QtCore.Qt.Key_S:"back",
                QtCore.Qt.Key_A:"left", QtCore.Qt.Key_D:"right"}
        if e.key() in keys:
            cmd = keys[e.key()]
            if cmd not in self.keys:
                self.keys.add(cmd)
                self.send_move(cmd)

    def keyReleaseEvent(self, e):
        keys = {QtCore.Qt.Key_W:"fwd", QtCore.Qt.Key_S:"back",
                QtCore.Qt.Key_A:"left", QtCore.Qt.Key_D:"right"}
        if e.key() in keys:
            cmd = keys[e.key()]
            if cmd in self.keys:
                self.keys.remove(cmd)
            self.send_move("stop")

    def send_move(self, c):
        print("[MOVE]", c)
        if self.client.sock:
            self.client.send({"type": "move", "cmd": c})


# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():
    # --- ROS 2 INTEGRATION ---
    rclpy.init(args=sys.argv)
    app = QtWidgets.QApplication(sys.argv)
    
    # Create the ROS node
    node = rclpy.create_node('trixant_gui_node')
    
    # Pass the node to the main window
    win = RoverControl(node=node)
    win.show()

    # --- ROS 2 INTEGRATION: Add ROS spinner timer ---
    def ros_spin():
        if rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)

    # This timer integrates the ROS event loop with the Qt event loop
    timer = QtCore.QTimer()
    timer.timeout.connect(ros_spin)
    timer.start(20) # Spin at 50Hz

    # Start the Qt application loop
    exit_code = app.exec_()

    # --- ROS 2 INTEGRATION: Clean up ROS ---
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()