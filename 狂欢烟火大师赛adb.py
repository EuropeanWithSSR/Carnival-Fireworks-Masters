import os
import subprocess
import cv2
import numpy as np
import time

# ADB 配置
ADB_PATH = r"E:\MeoAssistantArknights_v3.0.4\adb\platform-tools\adb.exe"  # 指定adb.exe路径
DEVICE_IP_PORT = "127.0.0.1:16384"  # 指定连接的IP和端口

# 基准分辨率（用于计算百分比）
base_width, base_height = 1440, 2560

# 基准尺寸和位置偏移百分比
cell_size_percent = 95 / base_width  # 方块尺寸的宽度百分比
offset_top_left_x_percent, offset_top_left_y_percent = 290 / base_width, 355 / base_height  # 上方方块左上角坐标百分比
offset_bottom_left_x_percent, offset_bottom_left_y_percent = 272 / base_width, 943 / base_height  # 下方方块左上角坐标百分比

# 数字和清除按钮的基准坐标（基于1440x2560分辨率）
button_coords_percent = {
    '0': (330 / base_width, 1823 / base_height),
    '1': (164 / base_width, 2035 / base_height),
    '2': (452 / base_width, 2035 / base_height),
    '3': (736 / base_width, 2035 / base_height),
    '4': (1017 / base_width, 2035 / base_height),
    '5': (1299 / base_width, 2035 / base_height),
    '6': (326 / base_width, 2236 / base_height),
    '7': (607 / base_width, 2236 / base_height),
    '8': (884 / base_width, 2236 / base_height),
    '9': (1166 / base_width, 2236 / base_height),
    'clear': (1155 / base_width, 1832 / base_height),
}

# 实际计算的坐标和尺寸（初始化为 None）
cell_size = None
offset_top_left_x, offset_top_left_y = None, None
offset_bottom_left_x, offset_bottom_left_y = None, None
button_coords = {}

# 颜色阈值（上方和下方彩色格子）- 转换为BGR格式
top_color = (105, 43, 199)  # BGR: #C72B69 in RGB
bottom_color = (205, 79, 108)  # BGR: #6C4FCD in RGB
color_tolerance = 50  # 色彩容差范围

# 检测到的相同彩色方块数量的计数
last_count = -1
repeat_count = 0
waiting_for_reset = False

def adb_command(command):
    """运行指定 adb 命令并附带 adb 路径和设备地址。"""
    full_command = f'"{ADB_PATH}" -s {DEVICE_IP_PORT} {command}'
    return full_command

def capture_screenshot():
    # 运行 adb 命令截取屏幕，并将输出传输到内存
    result = subprocess.run(
        adb_command("shell screencap -p"),
        shell=True,
        stdout=subprocess.PIPE
    )

    # 将截图数据读取到内存中并处理换行符
    img_data = result.stdout.replace(b'\r\n', b'\n')  # 修复行结束符

    # 转换图像数据为NumPy数组
    img_array = np.frombuffer(img_data, np.uint8)

    # 解码图像数据
    screenshot = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return screenshot

def initialize_dimensions(screenshot):
    """根据第一次截图的分辨率计算实际坐标和尺寸。"""
    global cell_size, offset_top_left_x, offset_top_left_y, offset_bottom_left_x, offset_bottom_left_y, button_coords

    # 获取截图的实际分辨率
    height, width = screenshot.shape[:2]
    
    # 计算实际的尺寸和坐标
    cell_size = int(cell_size_percent * width)
    offset_top_left_x = int(offset_top_left_x_percent * width)
    offset_top_left_y = int(offset_top_left_y_percent * height)
    offset_bottom_left_x = int(offset_bottom_left_x_percent * width)
    offset_bottom_left_y = int(offset_bottom_left_y_percent * height)

    # 计算按钮实际坐标
    for key, (x_percent, y_percent) in button_coords_percent.items():
        button_coords[key] = (int(x_percent * width), int(y_percent * height))

def click(x, y):
    """在设备上模拟点击"""
    os.system(adb_command(f"shell input tap {x} {y}"))

def input_number(number):
    """输入数字到游戏界面"""
    # 清除先前的输入
    click(*button_coords['clear'])
    time.sleep(0.2)

    # 输入每个数字
    for digit in str(number):
        click(*button_coords[digit])
        time.sleep(0.2)

def color_match(pixel, target_color, tolerance):
    """判断像素颜色是否在容差范围内接近目标颜色。"""
    return all(abs(int(pixel[i]) - target_color[i]) <= tolerance for i in range(3))

def get_color_matrix(image, offset_x, offset_y, cell_size, target_color, color, tolerance):
    """计算单个5x5方块的彩色区域矩阵并绘制检测框。"""
    matrix = np.zeros((5, 5), dtype=int)
    for i in range(5):
        for j in range(5):
            # 计算每个方块中心点坐标
            center_x = offset_x + j * cell_size + cell_size // 2
            center_y = offset_y + i * cell_size + cell_size // 2
            center_pixel = image[center_y, center_x]  # 获取中心点的像素值

            # 判断中心点颜色是否接近目标颜色
            if color_match(center_pixel, target_color, tolerance):
                matrix[i, j] = 1
                # 在原图上绘制检测框
                cv2.rectangle(image, (center_x - cell_size // 2, center_y - cell_size // 2), 
                              (center_x + cell_size // 2, center_y + cell_size // 2), color, 2)
    return matrix

def calculate_colored_blocks():
    """获取截图并计算彩色方块数量。"""
    screenshot = capture_screenshot()
    if screenshot is None:
        print("无法获取截图，请检查设备连接。")
        return None

    # 初始化实际坐标和尺寸（仅在第一次截图时调用）
    global cell_size
    if cell_size is None:
        initialize_dimensions(screenshot)

    # 获取上方和下方的彩色区域矩阵
    top_matrix = get_color_matrix(screenshot, offset_top_left_x, offset_top_left_y, cell_size, top_color, (0, 255, 0), color_tolerance)
    bottom_matrix = get_color_matrix(screenshot, offset_bottom_left_x, offset_bottom_left_y, cell_size, bottom_color, (255, 0, 0), color_tolerance)

    # 逐元素“或”运算，计算总彩色方块数量
    overlay_matrix = np.bitwise_or(top_matrix, bottom_matrix)
    colored_blocks_count = np.sum(overlay_matrix)

    # 缩小截图以适应窗口
    resized_screenshot = cv2.resize(screenshot, (0, 0), fx=0.5, fy=0.5)  # 将图像缩小50%

    # 在图像上显示方块数量
    cv2.putText(resized_screenshot, f"Colored Blocks: {colored_blocks_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # 显示结果
    cv2.imshow("Detected Blocks", resized_screenshot)
    return colored_blocks_count

# 循环检测彩色方块数量并自动输入
try:
    while True:
        colored_blocks_count = calculate_colored_blocks()
        #if colored_blocks_count is not None:
        print(f"当前彩色方块数量: {colored_blocks_count}")

        # 输入数字并设置等待标记
        if last_count!= colored_blocks_count:
            input_number(colored_blocks_count)
            last_count = colored_blocks_count

        # 每秒更新一次
        if cv2.waitKey(1) & 0xFF == ord('q'):  # 按 'q' 键退出
            break
        time.sleep(1)  # 每秒更新一次

except KeyboardInterrupt:
    print("实时检测已停止")

cv2.destroyAllWindows()
