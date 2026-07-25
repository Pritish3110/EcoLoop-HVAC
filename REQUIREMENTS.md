# REQUIREMENTS — Eco-Loop Building Agent

This document provides a comprehensive specification of the system architecture, hardware requirements, runtime environment, and dependency dependencies required to build, run, and reproduce the **Eco-Loop Building Agent** from zero context.

---

## 1. Operating System & Hardware Assumptions

*   **Operating System:** Ubuntu 26.04 LTS (Linux kernel 6.x+). *Also compatible with Ubuntu 22.04/24.04 LTS and Debian 12+.*
*   **Architecture:** x86_64 / AMD64.
*   **Hardware Acceleration (GPU):**
    *   **Tested GPU:** NVIDIA GeForce RTX 3060 Mobile (6 GB VRAM) / NVIDIA Driver `580.173.02` / CUDA 13.0.
    *   **Recommended VRAM:** Minimum 8 GB VRAM recommended for full GPU offload of 8-parameter quantized models (`Q4_K_M` or `Q4_0`). On 6 GB VRAM systems, Ollama automatically splits inference (~71% GPU / ~29% CPU RAM offload).
    *   **CPU Fallback:** A multi-core CPU (8+ cores) with at least 16 GB system RAM is required if running Ollama inference in CPU-only mode (expect latency of ~25–35 seconds per interval in CPU-only mode versus ~8–14 seconds with GPU acceleration).

---

## 2. System Libraries & Build Dependencies

Before setting up Python or EnergyPlus, install the fundamental Linux build utilities and database headers required by the compilation toolchain and runtime metrics extraction scripts:

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake python3-venv sqlite3 libsqlite3-dev curl git
```

---

## 3. EnergyPlus Engine Setup

The closed-loop simulation relies on **EnergyPlus v26.1.0-6f2e40d102** and its official Python bindings (`pyenergyplus`).

1. **Download & Install EnergyPlus:**
   Download the Linux x86_64 tarball/installer from the [Official EnergyPlus Releases Repository](https://github.com/NREL/EnergyPlus/releases):
   ```bash
   # Download release tarball (v26.1.0)
   curl -sSL https://github.com/NREL/EnergyPlus/releases/download/v26.1.0/EnergyPlus-26.1.0-6f2e40d102-Linux-Ubuntu24.04-x86_64.sh -o EnergyPlus-installer.sh
   chmod +x EnergyPlus-installer.sh
   
   # Install to standard user location without root privileges
   ./EnergyPlus-installer.sh --prefix ~/.local/EnergyPlus-26-1-0 --exclude-subdir
   ```

2. **Configure Python Bindings (`.pth` mechanism):**
   To allow Python scripts and virtual environments to import `pyenergyplus` seamlessly without manually editing `PYTHONPATH` on every terminal session, link the EnergyPlus Python API directory into your environment:
   ```bash
   echo "$HOME/.local/EnergyPlus-26-1-0" > ~/.local/lib/python3.14/site-packages/energyplus.pth
   ```
   *(Note: Ensure your `~/.local/EnergyPlus-26-1-0` directory contains the `pyenergyplus/` module and shared object libraries).*

---

## 4. Python Runtime & Virtual Environment Setup

The project is developed and verified on **Python 3.14.4**.

1. **Initialize Virtual Environment:**
   In the root directory of the repository, create and activate an isolated virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Upgrade Core Packaging Tools:**
   ```bash
   pip install --upgrade pip setuptools wheel
   ```

---

## 5. Pinned Python Dependency Tree (`pip freeze`)

Below is the exact, deterministic dependency tree generated from our production verification environment via `./.venv/bin/pip freeze`. To reproduce the exact environment, save the list below to a `requirements.txt` file and run `pip install -r requirements.txt`:

```text
action_msgs==2.4.5
action_tutorials_py==0.37.8
ament_cmake_test==2.8.7
ament_copyright==0.20.6
ament_cppcheck==0.20.6
ament_cpplint==0.20.6
ament_flake8==0.20.6
ament_index_python==1.13.3
ament_lint==0.20.6
ament_lint_cmake==0.20.6
ament_mypy==0.20.6
ament_package==0.18.3
ament_pep257==0.20.6
ament_uncrustify==0.20.6
ament_xmllint==0.20.6
angles==1.16.1
builtin_interfaces==2.4.5
composition_interfaces==2.4.5
cv_bridge==4.1.0
demo_nodes_py==0.37.8
diagnostic_msgs==5.9.2
example_interfaces==0.14.1
examples_rclpy_executors==0.21.5
examples_rclpy_minimal_action_client==0.21.5
examples_rclpy_minimal_action_server==0.21.5
examples_rclpy_minimal_client==0.21.5
examples_rclpy_minimal_publisher==0.21.5
examples_rclpy_minimal_service==0.21.5
examples_rclpy_minimal_subscriber==0.21.5
geometry_msgs==5.9.2
image_geometry==4.1.0
interactive_markers==2.8.4
laser_geometry==2.11.3
launch==3.9.7
launch_ros==0.29.8
launch_testing==3.9.7
launch_testing_ros==0.29.8
launch_xml==3.9.7
launch_yaml==3.9.7
lifecycle_msgs==2.4.5
logging_demo==0.37.8
map_msgs==2.6.1
message_filters==7.4.1
nav_msgs==5.9.2
pcl_msgs==1.0.0
pendulum_msgs==0.37.8
python_qt_binding==2.5.4
qt_dotgraph==2.11.0
qt_gui==2.11.0
qt_gui_cpp==2.11.0
qt_gui_py_common==2.11.0
quality_of_service_demo_py==0.37.8
rcl_interfaces==2.4.5
rclpy==10.0.10
resource_retriever==3.9.3
resource_retriever_interfaces==0.0.2
rmw_dds_common==6.0.0
rmw_test_fixture_implementation==0.15.8
ros2action==0.40.7
ros2bag==0.33.3
ros2bag_mcap_cli==0.33.3
ros2bag_sqlite3_cli==0.33.3
ros2cli==0.40.7
ros2component==0.40.7
ros2doctor==0.40.7
ros2interface==0.40.7
ros2launch==0.29.8
ros2lifecycle==0.40.7
ros2multicast==0.40.7
ros2node==0.40.7
ros2param==0.40.7
ros2pkg==0.40.7
ros2plugin==5.8.4
ros2run==0.40.7
ros2service==0.40.7
ros2topic==0.40.7
rosbag2_interfaces==0.33.3
rosbag2_py==0.33.3
rosgraph_msgs==2.4.5
rosidl_adapter==5.2.1
rosidl_buffer==5.2.1
rosidl_cli==5.2.1
rosidl_cmake==5.2.1
rosidl_generator_c==5.2.1
rosidl_generator_cpp==5.2.1
rosidl_generator_py==0.27.2
rosidl_generator_rs==0.4.12
rosidl_generator_type_description==5.2.1
rosidl_parser==5.2.1
rosidl_pycommon==5.2.1
rosidl_runtime_py==0.15.2
rosidl_typesupport_c==3.4.2
rosidl_typesupport_cpp==3.4.2
rosidl_typesupport_fastrtps_c==3.9.5
rosidl_typesupport_fastrtps_cpp==3.9.5
rosidl_typesupport_introspection_c==5.2.1
rosidl_typesupport_introspection_cpp==5.2.1
rpyutils==0.7.2
rqt_action==2.5.0
rqt_bag==2.2.4
rqt_bag_plugins==2.2.4
rqt_console==2.4.4
rqt_graph==1.8.4
rqt_gui==1.10.5
rqt_gui_py==1.10.5
rqt_msg==1.7.3
rqt_plot==1.7.6
rqt_publisher==1.10.4
rqt_py_common==1.10.5
rqt_py_console==1.5.3
rqt_reconfigure==1.8.6
rqt_service_caller==1.5.3
rqt_shell==1.4.2
rqt_srv==1.4.1
rqt_topic==2.1.1
sensor_msgs==5.9.2
sensor_msgs_py==5.9.2
service_msgs==2.4.5
shape_msgs==5.9.2
sros2==0.16.6
statistics_msgs==2.4.5
std_msgs==5.9.2
std_srvs==5.9.2
stereo_msgs==5.9.2
teleop_twist_keyboard==2.4.1
tf2_geometry_msgs==0.45.7
tf2_kdl==0.45.7
tf2_msgs==0.45.7
tf2_py==0.45.7
tf2_ros_py==0.45.7
tf2_sensor_msgs==0.45.7
tf2_tools==0.45.7
topic_monitor==0.37.8
trajectory_msgs==5.9.2
turtlesim_msgs==1.10.9
type_description_interfaces==2.4.5
unique_identifier_msgs==2.8.1
visualization_msgs==5.9.2
```

---

## 6. Local LLM Service Setup (Ollama)

The agent communicates with a local **Ollama** daemon via REST API (`http://localhost:11434/api/chat`) utilizing the `llama3.1:8b` model for tool calling and reasoning.

1. **Install Ollama Service:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull Required LLM Weight Checkpoint:**
   Pull the official 8-billion parameter Llama 3.1 checkpoint:
   ```bash
   ollama pull llama3.1:8b
   ```

3. **Verify Service & GPU Offload Status:**
   To confirm that the model is loaded in memory and check how many layers are offloaded to CUDA hardware acceleration, execute:
   ```bash
   ollama ps
   ```
   *Expected Output Example:*
   ```text
   NAME           ID              SIZE      PROCESSOR          CONTEXT    UNTIL              
   llama3.1:8b    46e0c10c039e    6.5 GB    29%/71% CPU/GPU    4096       4 minutes from now    
   ```
   *(Note: A higher GPU percentage results in faster control loop cycle times. Ensure no excessive desktop background applications are consuming VRAM if 100% GPU offload is desired).*

---

## 7. Verification Checklist

Before starting the agent simulation loop, confirm your environment readiness:
- [x] Python 3.14+ active in virtual environment (`which python`).
- [x] EnergyPlus API importable (`python -c "import pyenergyplus; print(pyenergyplus.__file__)"`).
- [x] SQLite3 database engine accessible (`sqlite3 --version`).
- [x] Ollama daemon running and responding on port 11434 (`curl http://localhost:11434/api/tags`).
- [x] Llama 3.1 8B model verified in local registry (`ollama list`).
