from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    realsense_launch_path = PathJoinSubstitution(
        [FindPackageShare('realsense2_camera'), 'launch', 'rs_launch.py']
    )

    rtabmap_launch_path = PathJoinSubstitution(
        [FindPackageShare('rtabmap_launch'), 'launch', 'rtabmap.launch.py']
    )

    return LaunchDescription([
        # Launch Realsense Camera
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(realsense_launch_path),
            launch_arguments={
                'align_depth.enable': 'true',
            }.items()
        ),

        # Launch RTAB-Map
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(rtabmap_launch_path),
            launch_arguments={
                'rtabmap_args': '--delete_db_on_start',
                'rgb_topic': '/camera/camera/color/image_raw',
                'depth_topic': '/camera/camera/aligned_depth_to_color/image_raw',
                'camera_info_topic': '/camera/camera/color/camera_info',
                'frame_id': 'camera_link',
                'approx_sync': 'false',
                'wait_for_transform': '0.2',
            }.items()
        )
    ])
