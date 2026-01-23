import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import NavSatFix, Imu
from std_msgs.msg import Bool
import math
import threading
import sys

class GPSNavigationNode(Node):
    def __init__(self):
        super().__init__('gps_navigation_node')
        
        # Subscriptions
        self.gps_sub = self.create_subscription(
            NavSatFix,
            '/gps/fix',
            self.gps_callback,
            10)
        self.imu_sub = self.create_subscription(
            Imu,
            '/imu/data',
            self.imu_callback,
            10)
        self.obstacle_sub = self.create_subscription(
            Bool,
            'obstacle_detected',
            self.obstacle_callback,
            10)
            
        # Publisher
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # State
        self.current_lat = None
        self.current_lon = None
        self.current_heading = 0.0 # Radians
        self.target_lat = None
        self.target_lon = None
        self.obstacle_detected = False
        
        # Parameters
        self.distance_threshold = 2.0 # Meters
        self.linear_speed = 0.5
        self.angular_speed = 0.5
        
        self.get_logger().info('GPS Navigation Node Started')
        
        # Input Thread
        self.input_thread = threading.Thread(target=self.get_user_input)
        self.input_thread.daemon = True
        self.input_thread.start()
        
        # Control Loop
        self.timer = self.create_timer(0.1, self.control_loop)

    def gps_callback(self, msg):
        self.current_lat = msg.latitude
        self.current_lon = msg.longitude

    def imu_callback(self, msg):
        # Convert quaternion to yaw (heading)
        # Simplified for planar navigation
        q = msg.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.current_heading = math.atan2(siny_cosp, cosy_cosp)

    def obstacle_callback(self, msg):
        self.obstacle_detected = msg.data

    def get_user_input(self):
        while rclpy.ok():
            try:
                print("Enter Target Coordinates (Lat Lon): ", end='', flush=True)
                line = sys.stdin.readline()
                if not line:
                    break
                parts = line.strip().split()
                if len(parts) == 2:
                    self.target_lat = float(parts[0])
                    self.target_lon = float(parts[1])
                    self.get_logger().info(f"New Target Set: {self.target_lat}, {self.target_lon}")
                else:
                    print("Invalid format. Usage: <lat> <lon>")
            except ValueError:
                print("Invalid numbers.")
            except Exception as e:
                self.get_logger().error(f"Input error: {e}")

    def control_loop(self):
        if self.target_lat is None or self.target_lon is None:
            return
            
        if self.current_lat is None or self.current_lon is None:
            self.get_logger().warn("Waiting for GPS fix...", throttle_duration_sec=2.0)
            return

        twist = Twist()

        if self.obstacle_detected:
            self.get_logger().warn("Obstacle Detected! Stopping.")
            self.cmd_vel_pub.publish(twist) # Stop
            return

        # Calculate distance and bearing
        distance = self.haversine_distance(
            self.current_lat, self.current_lon,
            self.target_lat, self.target_lon
        )
        
        if distance < self.distance_threshold:
            self.get_logger().info("Target Reached!")
            self.target_lat = None # Reset target
            self.target_lon = None
            self.cmd_vel_pub.publish(twist) # Stop
            return
            
        bearing = self.calculate_bearing(
             self.current_lat, self.current_lon,
            self.target_lat, self.target_lon
        )
        
        # Calculate heading error
        heading_error = bearing - self.current_heading
        
        # Normalize error to [-pi, pi]
        while heading_error > math.pi:
            heading_error -= 2 * math.pi
        while heading_error < -math.pi:
            heading_error += 2 * math.pi
            
        # Defines control logic
        if abs(heading_error) > 0.5: # Turn in place if error is large
            twist.angular.z = self.angular_speed if heading_error > 0 else -self.angular_speed
        else:
            twist.linear.x = self.linear_speed
            twist.angular.z = heading_error * 1.0 # P-controller for steering
            
        self.cmd_vel_pub.publish(twist)
        self.get_logger().info(f"Dist: {distance:.2f}m, Heading Err: {heading_error:.2f}", throttle_duration_sec=1.0)

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        R = 6371000 # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def calculate_bearing(self, lat1, lon1, lat2, lon2):
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dlambda = math.radians(lon2 - lon1)
        
        y = math.sin(dlambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
        return math.atan2(y, x)

def main(args=None):
    rclpy.init(args=args)
    node = GPSNavigationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
