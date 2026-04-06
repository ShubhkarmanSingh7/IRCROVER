# IRCROVER (ROS 2 Rover Stack)

This repository is a ROS2 Python package for a rover project that combines:

- sensor-driven navigation nodes,
- a GUI base station,
- RealSense + RTAB-Map launch integration,
- and placeholder drive/motor control.

If you are new to ROS 2, this README explains what each folder/file does and how the pieces work together.

---

## 1) What this project is

`irc_rover` is an `ament_python` ROS 2 package.  
It includes:

- **Autonomous exploration logic** using Depth Camera (light scan) (`/scan`) -> velocity commands (`/cmd_vel`)
- **Vision-based logic** using camera images -> velocity commands (`/cmd_vel`)
- **GPS navigation logic** using GPS + IMU + obstacle flag -> velocity commands (`/cmd_vel`)
- **Drive control listener** that receives `/cmd_vel` (currently a placeholder for real motor driver code)
- **GUI base station** that can publish movement commands to `cmd_vel` and show camera placeholders
- **Launch file** to start Intel RealSense camera and RTAB-Map SLAM stack

---

## 2) ROS 2 explained in simple words

In ROS 2, your robot software is split into small programs called **nodes**.

- A node can **publish** messages to a topic (like broadcasting data).
- A node can **subscribe** to messages from a topic (like listening to a channel).

Example in this project:

- Navigation node publishes movement commands on `/cmd_vel` (`geometry_msgs/Twist`).
- Drive node subscribes to `cmd_vel` and should convert that to wheel motor commands.

So ROS 2 here is being used as the communication backbone between perception, navigation, and control components.

---

## 3) High-level architecture

```text
            +-------------------------+
            |  RealSense + RTAB-Map   |
            |  (launch file)          |
            +-----------+-------------+
                        |
                        | camera/depth topics
                        v
+-------------------+   +---------------------+   +----------------------+
| vision_node       |   | exploration_node    |   | gps_navigation_node  |
| sub: /camera/...  |   | sub: /scan          |   | sub: /gps/fix, /imu  |
| pub: /cmd_vel     |   | pub: /cmd_vel       |   | pub: /cmd_vel        |
+---------+---------+   +----------+----------+   +----------+-----------+
          \                     |                         /
           \                    |                        /
            +-------------------+-----------------------+
                                |
                                v
                        +------------------+
                        | /cmd_vel topic   |
                        +--------+---------+
                                 |
                                 v
                      +----------------------+
                      | drive_control_node   |
                      | (motor logic TODO)   |
                      +----------------------+

GUI path:
base_station_gui --> publishes cmd_vel (manual teleop)
```

Important: multiple nodes publishing to `/cmd_vel` can conflict unless you add arbitration/mux logic.

---

## 4) Repository structure and file-by-file explanation

### Top-level

- `package.xml`  
  ROS 2 package manifest (name, build type, metadata, test dependencies).  
  Note: runtime dependencies are currently minimal/incomplete in this file.

- `setup.py`  
  Python packaging + ROS entry points.  
  Currently exports `vision_node` and `exploration_node` as `ros2 run` executables.

- `setup.cfg`  
  Script install path config for `ament_python`.

- `LICENSE`  
  Apache-2.0 license.

- `telemetry_run_20251210_203607.csv`  
  Recorded telemetry data file (sample/run artifact).

- `README.md`  
  This documentation.

---

### `irc_rover/` (main source package)

#### `irc_rover/navigation/`

- `exploration_node.py`  
  LiDAR obstacle avoidance:
  - subscribes to `/scan` (`sensor_msgs/LaserScan`)
  - checks center sector distance
  - publishes forward or turning command on `/cmd_vel`

- `vision_node.py`  
  Camera perception node scaffold:
  - subscribes to `/camera/image_raw` (`sensor_msgs/Image`)
  - converts image via `cv_bridge`
  - placeholder functions for obstacle/arrow detection
  - publishes `Twist` on `/cmd_vel`

- `gps_navigation_node.py`  
  GPS waypoint control:
  - subscribes `/gps/fix` (`NavSatFix`) and `/imu/data` (`Imu`)
  - optional obstacle gate via `obstacle_detected` (`Bool`)
  - gets target lat/lon from terminal input
  - computes distance + bearing and publishes `Twist`
  - not currently exposed in `setup.py` entry points

#### `irc_rover/control/`

- `drive_control_node.py`  
  Subscribes to `cmd_vel`, prints received linear/angular values.  
  Intended place to implement real motor driver bridge (serial/CAN/GPIO).

#### `irc_rover/gui/`

- `base_station_gui.py`  
  PyQt5 GUI for base station:
  - creates ROS 2 node `base_station_gui`
  - publishes manual drive commands on `cmd_vel`
  - has camera placeholders and keyboard controls
  - integrates ROS spin loop with Qt timer

---

### `launch/`

- `realsense_rtabmap.launch.py`  
  Composite launch that includes:
  - `realsense2_camera` launch (`rs_launch.py`)
  - `rtabmap_launch` launch (`rtabmap.launch.py`)
  with topic remaps/arguments for RGB, depth, and camera info.

This is the SLAM/sensor side of the stack.

---

### `interface/`

These are standalone UI prototypes/variants (not wired via `setup.py` console entry points):

- `testingdemo.py`  
  Larger experimental GUI integrating:
  - ROS image topic subscriptions,
  - local/non-ROS camera streams,
  - TCP telemetry channel,
  - capture/logging support.

- `testingdemo2.py`  
  Another evolved variant of the above with:
  - sensor QoS for ROS image subscriptions,
  - added RTAB-Map debug image panel,
  - adjusted default stream configuration.

Use these as development prototypes/reference, not as finalized package launch entry scripts.

---

### `test/`

Standard ROS 2 Python package quality checks:

- `test_flake8.py` -> style lint
- `test_pep257.py` -> docstring lint
- `test_copyright.py` -> copyright test (currently skipped)

---

### Generated/build artifact directories

- `build/`  
  Colcon build outputs (generated). Do not hand-edit.

- `install/`  
  Built install space + environment setup scripts (generated). Do not hand-edit.

- `log/`  
  Colcon build/runtime logs (generated). Safe to clean if needed.

- `resource/irc_rover`  
  ROS package resource marker file used by ament index.

---

## 5) How ROS 2 is used in this repository

### Core topic interfaces

- **Motion command:** `/cmd_vel` (`geometry_msgs/Twist`)
  - published by: `exploration_node`, `vision_node`, `gps_navigation_node`, GUI
  - subscribed by: `drive_control_node`

- **Perception topics consumed**
  - `/scan` (`LaserScan`) by `exploration_node`
  - `/camera/image_raw` (`Image`) by `vision_node`
  - `/gps/fix` (`NavSatFix`) and `/imu/data` (`Imu`) by `gps_navigation_node`

- **Safety/topic flag**
  - `obstacle_detected` (`Bool`) consumed by `gps_navigation_node`

### Runtime model

Each Python file is a ROS node that follows:

1. `rclpy.init()`
2. create publishers/subscribers/timers
3. `rclpy.spin(node)`
4. cleanup + shutdown

This is standard ROS 2 node lifecycle usage.

---

## 6) Setup and run (Linux/ROS 2 workflow)

This package appears designed for Ubuntu + ROS 2 (likely Humble).  
General steps:

1. Install ROS 2 and source it:
   ```bash
   source /opt/ros/humble/setup.bash
   ```

2. Create workspace and clone:
   ```bash
   mkdir -p ~/ros2_ws/src
   cd ~/ros2_ws/src
   git clone https://github.com/ShubhkarmanSingh7/IRCROVER.git
   cd ..
   ```

3. Install Python/system dependencies you need (typical):
   - `rclpy`, `sensor_msgs`, `geometry_msgs`, `cv_bridge`
   - `python3-opencv`, `python3-numpy`, `python3-pyqt5`
   - RealSense + RTAB-Map ROS packages if using SLAM launch

4. Build:
   ```bash
   colcon build
   source install/setup.bash
   ```

5. Run available packaged nodes:
   ```bash
   ros2 run irc_rover exploration_node
   ros2 run irc_rover vision_node
   ```

6. Run launch file (camera + RTAB-Map):
   ```bash
   ros2 launch irc_rover realsense_rtabmap.launch.py
   ```

7. Run other scripts directly (if needed):
   ```bash
   python3 src/IRCROVER/irc_rover/gui/base_station_gui.py
   python3 src/IRCROVER/irc_rover/navigation/gps_navigation_node.py
   python3 src/IRCROVER/irc_rover/control/drive_control_node.py
   ```

---

## 7) Current limitations and what to improve

- `package.xml` and `setup.py` should declare all runtime dependencies explicitly.
- `gps_navigation_node`, `drive_control_node`, and GUI are not in `console_scripts`.
- `vision_node` has placeholder detection logic.
- no command arbitration for multiple `/cmd_vel` publishers (should use mux/safety layer).
- real motor control backend in `drive_control_node` is still TODO.

---

## 8) Suggested next cleanup

If you want to productionize this repo:

1. add full dependencies in `package.xml` and `setup.py`,
2. expose all runnable nodes in `console_scripts`,
3. add one unified launch file for full rover stack,
4. add a `/cmd_vel` multiplexer or behavior manager,
5. document exact hardware assumptions (camera, LiDAR, GPS, IMU, motor controller).

---

## 9) Quick beginner glossary

- **Node**: one ROS program/process.
- **Topic**: named message channel (e.g., `/cmd_vel`).
- **Publisher**: writes messages to a topic.
- **Subscriber**: reads messages from a topic.
- **Launch file**: script that starts multiple nodes/packages together.
- **`Twist`**: standard velocity command (`linear` + `angular`) for mobile robots.
