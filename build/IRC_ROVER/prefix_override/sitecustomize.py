import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/shubh/ros2_ws/src/irc_rover/install/IRC_ROVER'
