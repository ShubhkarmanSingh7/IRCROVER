# main_layout_v2.py
# Trixant Rover Control – Multi-Cam Layout
# Features:
# - Camera swap on click
# - Multi-direction key control (diagonal)
# - Key-hold color highlight + mouse-click flash

import sys
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from PyQt5 import QtCore, QtWidgets, QtGui


def cam_label(name):
    """Create small camera placeholder labels."""
    lbl = QtWidgets.QLabel(name)
    lbl.setAlignment(QtCore.Qt.AlignCenter)
    lbl.setStyleSheet("border: 1px solid gray; background-color: #222; color: white;")
    lbl.setFixedSize(230, 130)
    return lbl


class RoverControl(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trixant Rover Control - Multi-Cam Layout")
        self.resize(1300, 850)

        # allow keyboard control
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        # keep track of pressed keys
        self.active_keys = set()

        # ROS 2 Setup
        if not rclpy.ok():
            rclpy.init(args=None)
        self.node = rclpy.create_node('base_station_gui')
        self.publisher = self.node.create_publisher(Twist, 'cmd_vel', 10)
        
        # Timer to process ROS callbacks
        self.ros_timer = QtCore.QTimer()
        self.ros_timer.timeout.connect(lambda: rclpy.spin_once(self.node, timeout_sec=0))
        self.ros_timer.start(100)

        # ---------- Main central widget ----------
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # ---------- Top row: 4 small cameras ----------
        cam_row = QtWidgets.QHBoxLayout()
        self.small_cams = []
        for i in range(1, 5):
            lbl = cam_label(f"Cam {i}")
            lbl.mousePressEvent = lambda e, l=lbl: self.swap_camera(l)
            cam_row.addWidget(lbl)
            self.small_cams.append(lbl)
        layout.addLayout(cam_row)

        # ---------- Middle section (3 columns) ----------
        mid = QtWidgets.QHBoxLayout()
        layout.addLayout(mid, stretch=1)

        # LEFT column – GPS / IMU data
        left_col = QtWidgets.QVBoxLayout()
        group_left = QtWidgets.QGroupBox("GPS / IMU Data")
        gl = QtWidgets.QVBoxLayout(group_left)
        self.lbl_gps = QtWidgets.QLabel("GPS: 0.0000°, 0.0000°")
        self.lbl_imu = QtWidgets.QLabel("IMU: Pitch 0°, Roll 0°, Yaw 0°")
        gl.addWidget(self.lbl_gps)
        gl.addWidget(self.lbl_imu)
        gl.addStretch()
        left_col.addWidget(group_left)
        mid.addLayout(left_col, stretch=1)

        # CENTER column – Main camera + movement pad
        center_col = QtWidgets.QVBoxLayout()

        # Main camera
        self.main_cam = QtWidgets.QLabel("Main Camera Feed")
        self.main_cam.setAlignment(QtCore.Qt.AlignCenter)
        self.main_cam.setStyleSheet("border: 2px solid #555; background-color: #111; color: white;")
        self.main_cam.setFixedSize(1280, 960)
        center_col.addWidget(self.main_cam, alignment=QtCore.Qt.AlignCenter)

        # Movement pad
        move_grid = QtWidgets.QGridLayout()

        def btn(txt):
            b = QtWidgets.QPushButton(txt)
            b.setFixedSize(60, 40)
            return b

        btn_n = btn("N")
        btn_s = btn("S")
        btn_e = btn("E")
        btn_w = btn("W")
        btn_center = QtWidgets.QPushButton("•")
        btn_center.setFixedSize(40, 40)

        move_grid.addWidget(btn_n, 0, 1)
        move_grid.addWidget(btn_w, 1, 0)
        move_grid.addWidget(btn_center, 1, 1)
        move_grid.addWidget(btn_e, 1, 2)
        move_grid.addWidget(btn_s, 2, 1)
        center_col.addLayout(move_grid)
        mid.addLayout(center_col, stretch=2)

        # keep references for color feedback
        self.btn_n = btn_n
        self.btn_s = btn_s
        self.btn_e = btn_e
        self.btn_w = btn_w
        self.btn_center = btn_center

        # RIGHT column – ABEx and Recon
        right_col = QtWidgets.QVBoxLayout()
        group_right = QtWidgets.QGroupBox("Modules")
        gr = QtWidgets.QVBoxLayout(group_right)
        self.btn_abex = QtWidgets.QPushButton("ABEx")
        self.btn_recon = QtWidgets.QPushButton("Recon")
        for b in (self.btn_abex, self.btn_recon):
            b.setFixedHeight(60)
            b.setStyleSheet("font-size: 16px; background-color: #2a82da; color: white; border-radius: 8px;")
        gr.addWidget(self.btn_abex)
        gr.addWidget(self.btn_recon)
        gr.addStretch()
        right_col.addWidget(group_right)
        mid.addLayout(right_col, stretch=1)

        # Connect placeholder actions
        self.btn_abex.clicked.connect(lambda: print("[INFO] ABEx clicked"))
        self.btn_recon.clicked.connect(lambda: print("[INFO] Recon clicked"))

        # Connect movement buttons
        btn_n.clicked.connect(lambda: self.on_button_click("N"))
        btn_s.clicked.connect(lambda: self.on_button_click("S"))
        btn_e.clicked.connect(lambda: self.on_button_click("E"))
        btn_w.clicked.connect(lambda: self.on_button_click("W"))

    # ---- camera swap ----
    def swap_camera(self, clicked_label):
        """Swap the clicked small camera view with the main camera."""
        main_text = self.main_cam.text()
        clicked_text = clicked_label.text()
        self.main_cam.setText(clicked_text)
        clicked_label.setText(main_text)
        print(f"[INFO] Swapped main camera with {clicked_text}")

    # ---- movement command ----
    def move_cmd(self, d):
        print(f"[CMD] Move {d}")
        twist = Twist()
        
        # Linear speed
        speed = 0.5
        # Angular speed
        turn = 0.5

        if d == "N":
            twist.linear.x = speed
        elif d == "S":
            twist.linear.x = -speed
        elif d == "E":
            twist.angular.z = -turn
        elif d == "W":
            twist.angular.z = turn
        elif d == "N+E":
            twist.linear.x = speed
            twist.angular.z = -turn
        elif d == "N+W":
            twist.linear.x = speed
            twist.angular.z = turn
        elif d == "S+E":
            twist.linear.x = -speed
            twist.angular.z = -turn
        elif d == "S+W":
            twist.linear.x = -speed
            twist.angular.z = turn
        elif d == "STOP":
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            
        self.publisher.publish(twist)

    # ---- helper: set color ----
    def set_button_color(self, button, active=True):
        """Set button color: active=True -> blue, active=False -> normal."""
        if active:
            button.setStyleSheet("background-color: #00ccff; color: black; font-weight: bold;")
        else:
            button.setStyleSheet("")

    # ---- helper: flash when clicked ----
    def flash_button(self, button):
        """Short flash when mouse-clicked."""
        self.set_button_color(button, True)
        QtCore.QTimer.singleShot(200, lambda: self.set_button_color(button, False))

    # ---- handle button clicks ----
    def on_button_click(self, direction):
        self.move_cmd(direction)
        # flash color for click
        mapping = {"N": self.btn_n, "S": self.btn_s, "E": self.btn_e, "W": self.btn_w}
        btn = mapping.get(direction)
        if btn:
            self.flash_button(btn)

    # ---- keyboard control (press) ----
    def keyPressEvent(self, event):
        key = event.key()
        key_map = {
            QtCore.Qt.Key_Up: "Up", QtCore.Qt.Key_W: "Up",
            QtCore.Qt.Key_Down: "Down", QtCore.Qt.Key_S: "Down",
            QtCore.Qt.Key_Left: "Left", QtCore.Qt.Key_A: "Left",
            QtCore.Qt.Key_Right: "Right", QtCore.Qt.Key_D: "Right",
            QtCore.Qt.Key_Space: "Stop"
        }
        if key in key_map:
            self.active_keys.add(key_map[key])
            self.handle_multi_direction()
        else:
            super().keyPressEvent(event)

    # ---- keyboard control (release) ----
    def keyReleaseEvent(self, event):
        key = event.key()
        key_map = {
            QtCore.Qt.Key_Up: "Up", QtCore.Qt.Key_W: "Up",
            QtCore.Qt.Key_Down: "Down", QtCore.Qt.Key_S: "Down",
            QtCore.Qt.Key_Left: "Left", QtCore.Qt.Key_A: "Left",
            QtCore.Qt.Key_Right: "Right", QtCore.Qt.Key_D: "Right",
            QtCore.Qt.Key_Space: "Stop"
        }
        if key in key_map and key_map[key] in self.active_keys:
            self.active_keys.remove(key_map[key])
            self.handle_multi_direction()
        else:
            super().keyReleaseEvent(event)

    # ---- interpret held keys (multi-direction) ----
    def handle_multi_direction(self):
        dirs = self.active_keys

        # reset all button colors
        for b in [self.btn_n, self.btn_s, self.btn_e, self.btn_w, self.btn_center]:
            self.set_button_color(b, False)

        if not dirs:
            return

        # Diagonal / combined moves
        if "Up" in dirs and "Right" in dirs:
            self.move_cmd("N+E")
            self.set_button_color(self.btn_n, True)
            self.set_button_color(self.btn_e, True)
        elif "Up" in dirs and "Left" in dirs:
            self.move_cmd("N+W")
            self.set_button_color(self.btn_n, True)
            self.set_button_color(self.btn_w, True)
        elif "Down" in dirs and "Right" in dirs:
            self.move_cmd("S+E")
            self.set_button_color(self.btn_s, True)
            self.set_button_color(self.btn_e, True)
        elif "Down" in dirs and "Left" in dirs:
            self.move_cmd("S+W")
            self.set_button_color(self.btn_s, True)
            self.set_button_color(self.btn_w, True)
        else:
            mapping = {
                "Up": ("N", self.btn_n),
                "Down": ("S", self.btn_s),
                "Left": ("W", self.btn_w),
                "Right": ("E", self.btn_e),
                "Stop": ("STOP", self.btn_center)
            }
            for k, (cmd, btn) in mapping.items():
                if k in dirs:
                    self.move_cmd(cmd)
                    self.set_button_color(btn, True)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = RoverControl()
    win.show()
    win.show()
    try:
        sys.exit(app.exec_())
    finally:
        win.node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
