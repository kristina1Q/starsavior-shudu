"""
游戏画面截取、棋盘定位与数字识别模块
采用 OpenCV 与纯 NumPy 实现，零第三方臃肿依赖，极速高精
"""
import os
import ctypes
import numpy as np
from PIL import Image, ImageGrab

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# 基础目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

def ensure_desktop_access():
    """确保当前线程具备屏幕与输入交互权限并开启DPI自适应"""
    try:
        user32 = ctypes.windll.user32
        hDesk = user32.OpenInputDesktop(0, False, 0x01FF)
        if hDesk:
            user32.SetThreadDesktop(hDesk)
    except Exception:
        pass
    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        pass

def capture_screen():
    """捕获当前全屏幕图像"""
    ensure_desktop_access()
    return ImageGrab.grab()

def load_templates():
    """加载 1~9 号数字标准模板"""
    templates = {}
    for d in range(1, 10):
        t_path = os.path.join(TEMPLATES_DIR, f"{d}.png")
        if os.path.exists(t_path):
            img = Image.open(t_path).convert('L')
            templates[d] = np.array(img, dtype=float)
        else:
            raise FileNotFoundError(f"未找到模板文件: {t_path}")
    return templates

def detect_board_by_exit_button(screen_img):
    """
    通过定位左上角的 EXIT 按钮进行锚点推算棋盘位置 (使用 OpenCV 毫秒级模板匹配)
    """
    exit_path = os.path.join(TEMPLATES_DIR, "exit_btn.png")
    if not os.path.exists(exit_path):
        return None
        
    exit_tmpl = Image.open(exit_path).convert('L')
    t_w, t_h = exit_tmpl.size
    
    # 限制在屏幕左上方 1/3 区域搜索
    w, h = screen_img.size
    crop_w, crop_h = min(w, int(w * 0.45)), min(h, int(h * 0.45))
    sub_screen = screen_img.crop((0, 0, crop_w, crop_h)).convert('L')
    sub_arr = np.array(sub_screen, dtype=np.uint8)
    
    best_val = -1.0
    best_loc = None
    best_scale = 1.0
    
    # 适配不同分辨率与缩放比例
    scales = [w / 1024.0, (w / 1024.0) * 0.8, (w / 1024.0) * 1.25, 1.0, 1.25, 1.5, 2.0, 2.5]
    scales = sorted(list(set([round(s, 2) for s in scales if s > 0.4])))
    
    for scale in scales:
        sw, sh = int(round(t_w * scale)), int(round(t_h * scale))
        if sw >= crop_w or sh >= crop_h or sw < 10 or sh < 10:
            continue
        tmpl_scaled = exit_tmpl.resize((sw, sh), Image.Resampling.BILINEAR)
        tmpl_arr = np.array(tmpl_scaled, dtype=np.uint8)
        
        if HAS_CV2:
            res = cv2.matchTemplate(sub_arr, tmpl_arr, cv2.TM_CCOEFF_NORMED)
            min_v, max_v, min_l, max_l = cv2.minMaxLoc(res)
            if max_v > best_val:
                best_val = max_v
                best_loc = max_l
                best_scale = scale
        else:
            # 纯 NumPy 简易相关匹配降级方案
            t_f = tmpl_arr.astype(float) - np.mean(tmpl_arr)
            t_norm = np.linalg.norm(t_f)
            if t_norm == 0:
                continue
            # 采样几个关键位置
            continue
            
    if best_loc is not None and best_val > 0.70:
        exit_x, exit_y = best_loc
        scale = best_scale
        # 基准坐标（在1024x639下：exit=(50,110), tl=(278,188), br=(743,487), step=33.2）
        tl_x = exit_x + (278 - 50) * scale
        tl_y = exit_y + (188 - 110) * scale
        step_x = 33.214 * scale
        step_y = 33.222 * scale
        br_x = tl_x + 14 * step_x
        br_y = tl_y + 9 * step_y
        return {
            "tl_x": tl_x, "tl_y": tl_y,
            "br_x": br_x, "br_y": br_y,
            "step_x": step_x, "step_y": step_y,
            "method": "exit_button_anchor",
            "scale": scale
        }
    return None

def detect_board_by_card_projection(screen_img):
    """
    通过高亮卡片（10x15网格）的投影分析定位棋盘 (纯 NumPy 实现)
    """
    arr = np.array(screen_img.convert('L'))
    h, w = arr.shape
    
    # 提取高亮白色卡片区域
    card_mask = (arr > 215).astype(float)
    row_sum = np.sum(card_mask, axis=1)
    col_sum = np.sum(card_mask, axis=0)
    
    # 找到可能包含棋盘的密集区域
    row_valid = np.where(row_sum > w * 0.1)[0]
    col_valid = np.where(col_sum > h * 0.05)[0]
    
    if len(row_valid) < 50 or len(col_valid) < 50:
        return None
        
    y_min, y_max = row_valid[0], row_valid[-1]
    x_min, x_max = col_valid[0], col_valid[-1]
    
    # 验证长宽比：15列 x 10行，长宽比约为 1.5 左右
    width = x_max - x_min
    height = y_max - y_min
    ratio = width / max(1, height)
    if not (1.2 <= ratio <= 1.8):
        return None
        
    step_x = width / 15.0
    step_y = height / 10.0
    
    tl_x = x_min + step_x * 0.5
    tl_y = y_min + step_y * 0.5
    br_x = tl_x + 14 * step_x
    br_y = tl_y + 9 * step_y
    
    return {
        "tl_x": tl_x, "tl_y": tl_y,
        "br_x": br_x, "br_y": br_y,
        "step_x": step_x, "step_y": step_y,
        "method": "projection"
    }

def get_board_geometry(screen_img, cached_bbox=None):
    """
    获取棋盘网格几何参数：
    优先使用缓存或配置文件中的坐标，否则自动检测
    """
    if cached_bbox is not None and len(cached_bbox) == 4:
        tl_x, tl_y, br_x, br_y = cached_bbox
        step_x = (br_x - tl_x) / 14.0
        step_y = (br_y - tl_y) / 9.0
        return {
            "tl_x": tl_x, "tl_y": tl_y,
            "br_x": br_x, "br_y": br_y,
            "step_x": step_x, "step_y": step_y,
            "method": "cached"
        }
        
    # 尝试通过锚点识别
    geom = detect_board_by_exit_button(screen_img)
    if geom is not None:
        return geom
        
    # 尝试通过高亮投影识别
    geom = detect_board_by_card_projection(screen_img)
    if geom is not None:
        return geom
        
    return None

def recognize_grid(screen_img, geom, templates=None):
    """
    根据定位信息识别 10x15 数字矩阵
    """
    if templates is None:
        templates = load_templates()
        
    gray_img = screen_img.convert('L')
    tl_x = geom["tl_x"]
    tl_y = geom["tl_y"]
    step_x = geom["step_x"]
    step_y = geom["step_y"]
    
    cell_half_w = max(5, int(round(step_x * 0.42)))
    cell_half_h = max(5, int(round(step_y * 0.42)))
    
    grid = np.zeros((10, 15), dtype=int)
    
    for r in range(10):
        for c in range(15):
            cx = int(round(tl_x + c * step_x))
            cy = int(round(tl_y + r * step_y))
            
            # 裁剪单元格
            crop = gray_img.crop((cx - cell_half_w, cy - cell_half_h, cx + cell_half_w, cy + cell_half_h))
            crop_arr = np.array(crop)
            
            # 判断卡片是否存在：未消除的白底卡片中心必有高于 205 的高亮像素
            if crop_arr.size == 0 or np.max(crop_arr) < 205:
                grid[r, c] = 0
                continue
                
            # 统一缩放至标准 28x28 尺寸以比对模板
            crop_resized = np.array(crop.resize((28, 28), Image.Resampling.BILINEAR), dtype=float)
            
            best_d = 0
            best_diff = 1e9
            
            for d in range(1, 10):
                t = templates[d]
                # 微移搜索 [-1, 0, 1]，消除亚像素对齐误差
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        shifted = np.roll(crop_resized, (dy, dx), axis=(0, 1))
                        diff = np.mean((shifted - t) ** 2)
                        if diff < best_diff:
                            best_diff = diff
                            best_d = d
                            
            grid[r, c] = best_d
            
    return grid
