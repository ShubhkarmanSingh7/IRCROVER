import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist

class ExplorationNode(Node):
    def __init__(self):
        super().__init__('exploration_node')
        
        # Subscriptions
        self.subscription = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10)
        self.subscription  # prevent unused variable warning

        # Publications
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)

        self.get_logger().info('Exploration Node has been started.')

    def scan_callback(self, msg):
        # Simple exploration logic
        # 1. Check for obstacles in front
        # 2. If clear, move forward
        # 3. If obstacle, turn
        
        ranges = msg.ranges
        num_readings = len(ranges)
        center_index = num_readings // 2
        window_size = num_readings // 10 # Check 10% of the field of view in the center
        
        start_index = center_index - window_size // 2
        end_index = center_index + window_size // 2
        
        # Filter out invalid readings (inf, nan)
        front_ranges = [r for r in ranges[start_index:end_index] if not (r == float('inf') or r != r)]
        
        min_distance = float('inf')
        if front_ranges:
            min_distance = min(front_ranges)

        twist = Twist()
        
        safe_distance = 1.0 # meters

        if min_distance < safe_distance:
            self.get_logger().info(f'Obstacle detected at {min_distance:.2f}m. Turning.')
            twist.linear.x = 0.0
            twist.angular.z = 0.5 # Turn left
        else:
            self.get_logger().info('Path clear. Moving forward.')
            twist.linear.x = 0.5
            twist.angular.z = 0.0

        self.publisher_.publish(twist)

def main(args=None):
    rclpy.init(args=args)
    node = ExplorationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
