import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import cv2
import numpy as np

class VisionNode(Node):
    def __init__(self):
        super().__init__('vision_node')
        
        # Subscriptions
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10)
        self.subscription  # prevent unused variable warning

        # Publications
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)

        # Helpers
        self.bridge = CvBridge()
        self.frame_count = 0
        self.get_logger().info('Vision Node has been started.')

    def image_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            self.get_logger().error(f'Could not convert image: {e}')
            return

        # Detection Logic
        obstacle_detected = self.detect_obstacle(cv_image)
        arrow_direction = self.detect_arrow(cv_image)

        # Control Logic
        twist = Twist()

        if obstacle_detected:
            self.get_logger().info('Obstacle detected! Stopping.')
            twist.linear.x = 0.0
            twist.angular.z = 0.0
        elif arrow_direction:
            self.get_logger().info(f'Arrow detected: {arrow_direction}')
            if arrow_direction == 'LEFT':
                twist.angular.z = 0.5
            elif arrow_direction == 'RIGHT':
                twist.angular.z = -0.5
            elif arrow_direction == 'FORWARD':
                twist.linear.x = 0.5
        else:
            # Default behavior if nothing detected (stop or keep exploring?)
            # For now, just stop to be safe
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            
            self.frame_count += 1
            if self.frame_count % 50 == 0:
                self.get_logger().info(f'Processed {self.frame_count} frames. No obstacles or arrows detected.')

        self.publisher_.publish(twist)

    def detect_obstacle(self, image):
        # Placeholder for obstacle detection logic
        # Return True if obstacle is close, else False
        # Example: Check depth image center or use simple color thresholding for now
        return False

    def detect_arrow(self, image):
        # Placeholder for arrow detection logic
        # Return 'LEFT', 'RIGHT', 'FORWARD', or None
        return None

def main(args=None):
    rclpy.init(args=args)
    node = VisionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
