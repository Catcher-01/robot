from setuptools import find_packages, setup

package_name = 'voice_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hyh',
    maintainer_email='hyh@robot.local',
    description='语音导航控制：语音识别 → 意图解析 → Nav2 导航',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'voice_node = voice_control.voice_node:main',
            'nav_controller = voice_control.nav_controller:main',
        ],
    },
)
