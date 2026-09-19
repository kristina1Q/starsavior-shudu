"""
鼠标控制与全局停止键监听模块
采用 Windows user32 底层 API 实现高精度无延迟模拟
"""
import time
import ctypes

user32 = ctypes.windll.user32

# Windows 鼠标事件标志
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000

# 虚拟键码
VK_OEM_2 = 0xBF   # 主键盘 '/?' 键
VK_DIVIDE = 0x6F  # 小键盘除号 '/' 键
VK_F8 = 0x77      # F8 键
VK_F7 = 0x76      # F7 键

class EmergencyStopException(Exception):
    """用户触发全局停止键异常"""
    pass

def is_stop_pressed():
    """
    检查全局停止键 '/' 是否被按下
    同时支持主键盘的 /? 键与小键盘的 / 键
    """
    if user32.GetAsyncKeyState(VK_OEM_2) & 0x8000:
        return True
    if user32.GetAsyncKeyState(VK_DIVIDE) & 0x8000:
        return True
    return False

def check_stop():
    """检测停止键，如果按下则立刻释放鼠标并抛出异常"""
    if is_stop_pressed():
        # 安全释放鼠标左键
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        raise EmergencyStopException("【急停通知】检测到按下全局停止键 '/'，脚本已立即安全停止！")

def is_key_pressed(vk_code):
    """检测指定虚拟键是否处于按下状态"""
    return bool(user32.GetAsyncKeyState(vk_code) & 0x8000)

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_cursor():
    """获取当前鼠标光标屏幕坐标 (x, y)"""
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def set_cursor(x, y):
    """设置鼠标光标位置"""
    user32.SetCursorPos(int(round(x)), int(round(y)))

def mouse_down():
    """按下鼠标左键"""
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

def mouse_up():
    """释放鼠标左键"""
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def drag_rectangle(start_x, start_y, end_x, end_y, steps=5, drag_delay_ms=25):
    """
    平滑拖拽框选矩形区域
    
    :param start_x, start_y: 框选起始坐标
    :param end_x, end_y: 框选终点坐标
    :param steps: 插值中间点数量（模拟真实鼠标拖动轨迹）
    :param drag_delay_ms: 拖拽总耗时(ms)
    """
    check_stop()
    
    # 移动到起点
    set_cursor(start_x, start_y)
    time.sleep(0.01)
    check_stop()
    
    # 按下左键
    mouse_down()
    time.sleep(0.01)
    check_stop()
    
    # 平滑插值拖拽到终点
    step_time = (drag_delay_ms / 1000.0) / max(1, steps)
    for i in range(1, steps + 1):
        check_stop()
        curr_x = start_x + (end_x - start_x) * (i / steps)
        curr_y = start_y + (end_y - start_y) * (i / steps)
        set_cursor(curr_x, curr_y)
        time.sleep(step_time)
        
    set_cursor(end_x, end_y)
    time.sleep(0.01)
    check_stop()
    
    # 释放左键
    mouse_up()
    time.sleep(0.01)

def execute_move(geom, r1, c1, r2, c2, drag_delay_ms=25, interval_ms=40):
    """
    将网格坐标转换为屏幕像素坐标并执行一次框选消除
    
    :param geom: 棋盘几何信息
    :param r1, c1: 矩形左上角网格坐标 (0~9, 0~14)
    :param r2, c2: 矩形右下角网格坐标 (0~9, 0~14)
    """
    check_stop()
    
    tl_x = geom["tl_x"]
    tl_y = geom["tl_y"]
    step_x = geom["step_x"]
    step_y = geom["step_y"]
    
    # 边缘微量向外扩展，确保框选矩形完整包围目标卡片
    margin_x = step_x * 0.38
    margin_y = step_y * 0.38
    
    start_x = int(round(tl_x + c1 * step_x - margin_x))
    start_y = int(round(tl_y + r1 * step_y - margin_y))
    end_x = int(round(tl_x + c2 * step_x + margin_x))
    end_y = int(round(tl_y + r2 * step_y + margin_y))
    
    drag_rectangle(start_x, start_y, end_x, end_y, steps=4, drag_delay_ms=drag_delay_ms)
    time.sleep(interval_ms / 1000.0)
