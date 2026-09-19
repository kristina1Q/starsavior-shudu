"""
凑十游戏（苹果游戏/Fruit Box）自动脚本主程序
具备自动定位、OCR高精识别、跨空域最优求解与极速鼠标控制
全局停止键: [/] 键 (随时可按退出或急停)
"""
import os
import sys
import time
import json
import numpy as np

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import detector
import solver
import controller
from controller import EmergencyStopException

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    """读取配置文件"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "rows": 10,
        "cols": 15,
        "drag_speed_ms": 25,
        "move_interval_ms": 40,
        "hotkey_start": "F8",
        "hotkey_stop": "/",
        "saved_bbox": None
    }

def save_config(cfg):
    """保存配置文件"""
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[-] 保存配置失败: {e}")

def print_grid(grid):
    """在终端美化打印 10x15 网格"""
    print("\n   +" + "---+" * 15)
    header = "   |" + "|".join(f"{c:^3}" for c in range(1, 16)) + "|"
    print(header)
    print("---+" + "---+" * 15)
    for r in range(grid.shape[0]):
        row_str = f"{r+1:2d} |"
        for c in range(grid.shape[1]):
            val = grid[r, c]
            if val == 0:
                row_str += " . |"
            else:
                row_str += f" {val} |"
        print(row_str)
    print("---+" + "---+" * 15 + "\n")

def calibrate_board():
    """手动引导标定棋盘左上与右下坐标"""
    print("\n" + "=" * 55)
    print("【手动标定棋盘坐标】")
    print("1. 请切换到游戏窗口，使棋盘完全可见。")
    print("2. 将鼠标悬停在【第1行第1列（最左上角）数字卡片】的正中心。")
    input(">> 鼠标就位后，在本终端按下 [Enter] 键记录左上角...")
    tl_x, tl_y = controller.get_cursor()
    print(f"[+] 记录左上角坐标: ({tl_x}, {tl_y})")
    
    print("\n3. 现在将鼠标悬停在【第10行第15列（最右下角）数字卡片】的正中心。")
    input(">> 鼠标就位后，在本终端按下 [Enter] 键记录右下角...")
    br_x, br_y = controller.get_cursor()
    print(f"[+] 记录右下角坐标: ({br_x}, {br_y})")
    
    if br_x <= tl_x or br_y <= tl_y:
        print("[-] 坐标无效：右下角坐标必须大于左上角坐标！标定取消。")
        return None
        
    cfg = load_config()
    cfg["saved_bbox"] = [tl_x, tl_y, br_x, br_y]
    save_config(cfg)
    print(f"[✓] 标定成功并保存！步长: X={(br_x-tl_x)/14:.1f}px, Y={(br_y-tl_y)/9:.1f}px")
    return cfg["saved_bbox"]

def solve_and_play(use_beam_search=True, countdown=3):
    """
    执行一轮截屏、识别、求解并自动拖拽消除
    """
    cfg = load_config()
    cached_bbox = cfg.get("saved_bbox")
    
    print("\n[1/4] 正在截取屏幕画面...")
    screen_img = detector.capture_screen()
    
    print("[2/4] 正在定位棋盘区域...")
    geom = detector.get_board_geometry(screen_img, cached_bbox=cached_bbox)
    if geom is None:
        print("[-] 未能自动检测到棋盘！")
        print("    建议：1. 确保游戏窗口处于前台且未被遮挡；")
        print("          2. 或在主菜单选择 [3] 手动标定棋盘位置。")
        return False
        
    print(f"[+] 棋盘定位成功 (模式: {geom['method']})")
    print(f"    坐标范围: ({geom['tl_x']:.0f}, {geom['tl_y']:.0f}) -> ({geom['br_x']:.0f}, {geom['br_y']:.0f})")
    
    print("[3/4] 正在识别卡片数字...")
    templates = detector.load_templates()
    grid = detector.recognize_grid(screen_img, geom, templates)
    
    total_valid = np.count_nonzero(grid)
    print(f"[+] 识别完成！当前棋盘剩余数字: {total_valid} / 150")
    print_grid(grid)
    
    if total_valid == 0:
        print("[-] 当前棋盘没有检测到任何数字卡片。")
        return False
        
    print("[4/4] 正在计算最优凑十消除方案 (支持跨空白区域框选)...")
    t0 = time.time()
    if use_beam_search:
        moves, final_board = solver.solve_beam_search(grid, beam_width=35)
    else:
        moves, final_board = solver.solve_greedy(grid)
    calc_time = time.time() - t0
    
    cleared_count = sum(m[4] for m in moves)
    clear_rate = (cleared_count / max(1, total_valid)) * 100
    print(f"[+] 求解完成 (耗时 {calc_time:.2f}s):")
    print(f"    计划执行步数: {len(moves)} 步")
    print(f"    预计消除数字: {cleared_count} 个 (消除率: {clear_rate:.1f}%)")
    
    if not moves:
        print("[-] 当前棋盘无可用凑十矩形！如果游戏中有洗牌技能（如W键），可洗牌后重试。")
        return False
        
    # 倒计时准备
    print("\n" + "!" * 55)
    print(f"【重要】准备开始鼠标消除！全局急停键为 [/] 键！")
    print("!" * 55)
    for i in range(countdown, 0, -1):
        controller.check_stop()
        print(f">> 将在 {i} 秒后接管鼠标，请确保游戏窗口在前台... (按 / 键取消)")
        time.sleep(1.0)
        
    controller.check_stop()
    print("[▶] 开始自动消除...")
    
    drag_speed = cfg.get("drag_speed_ms", 25)
    move_interval = cfg.get("move_interval_ms", 40)
    
    try:
        for idx, (r1, c1, r2, c2, nz_count) in enumerate(moves, 1):
            controller.check_stop()
            w = c2 - c1 + 1
            h = r2 - r1 + 1
            print(f"  ({idx}/{len(moves)}) 框选 [{r1+1},{c1+1}] 到 [{r2+1},{c2+1}] ({h}x{w} 矩形, 消除 {nz_count} 数)")
            controller.execute_move(geom, r1, c1, r2, c2, drag_delay_ms=drag_speed, interval_ms=move_interval)
            
        print("\n[✓] 消除执行完毕！")
        return True
    except EmergencyStopException as e:
        print(f"\n{e}")
        return False

def test_screen_recognition():
    """仅截屏并显示识别结果，不执行任何鼠标动作"""
    cfg = load_config()
    cached_bbox = cfg.get("saved_bbox")
    
    print("\n[测试] 正在截取屏幕画面...")
    screen_img = detector.capture_screen()
    
    print("[测试] 正在定位棋盘...")
    geom = detector.get_board_geometry(screen_img, cached_bbox=cached_bbox)
    if geom is None:
        print("[-] 未能定位棋盘！请在游戏中打开棋盘界面后重试，或先进行手动标定。")
        return
        
    print(f"[+] 棋盘定位: 模式={geom['method']}, 左上=({geom['tl_x']:.0f}, {geom['tl_y']:.0f}), 步长=({geom['step_x']:.1f}, {geom['step_y']:.1f})")
    grid = detector.recognize_grid(screen_img, geom)
    print_grid(grid)
    valid_count = np.count_nonzero(grid)
    print(f"[+] 识别出 {valid_count} 个数字卡片。")
    
    moves, _ = solver.solve_greedy(grid)
    cleared = sum(m[4] for m in moves)
    print(f"[+] 经检测，当前盘面可直接消除 {cleared} 个数字（共 {len(moves)} 个矩形组合）。")

def hotkey_listener_mode():
    """全局热键监听模式"""
    cfg = load_config()
    start_key = cfg.get("hotkey_start", "F8")
    stop_key = cfg.get("hotkey_stop", "/")
    
    print("\n" + "=" * 55)
    print("【全局热键挂机模式】")
    print(f"  • 按 [{start_key}] 键：立即截屏并自动执行消除")
    print(f"  • 按 [{stop_key}] 键：立即急停退出")
    print("  • 挂机监听已激活，请在游戏中随时按 F8 触发...")
    print("=" * 55 + "\n")
    
    # 轮询监听按键
    while True:
        try:
            if controller.is_stop_pressed():
                print("\n[!] 收到退出键 [/]，已退出热键监听模式。")
                break
                
            if controller.is_key_pressed(controller.VK_F8):
                print(f"\n[!] 检测到按键 [{start_key}]，开始自动求解与消除...")
                # 等待按键抬起，防止重复触发
                while controller.is_key_pressed(controller.VK_F8):
                    time.sleep(0.05)
                    
                solve_and_play(use_beam_search=True, countdown=1)
                print(f"\n[+] 本轮完毕。可按 [{start_key}] 继续下一轮，或按 [{stop_key}] 退出。")
                
            time.sleep(0.03)
        except EmergencyStopException as e:
            print(f"\n{e}")
            break
        except KeyboardInterrupt:
            print("\n[-] 已手动终止。")
            break

def main_menu():
    """终端交互主菜单"""
    # 确保桌面权限与DPI
    detector.ensure_desktop_access()
    
    while True:
        print("\n" + "=" * 55)
        print("🎮 凑十游戏（苹果游戏/Fruit Box）全自动脚本")
        print("   全局停止键: [/] 键 (任何时刻按下均可急停)")
        print("=" * 55)
        print(" [1] 一键自动识别并消除 (单局执行)")
        print(" [2] 全局热键挂机模式 (在游戏中按 F8 触发, / 停止)")
        print(" [3] 测试识别当前屏幕 (只显示数字矩阵，不动鼠标)")
        print(" [4] 手动标定棋盘坐标 (两点标定，备用方案)")
        print(" [0] 退出程序")
        print("=" * 55)
        choice = input("请输入选项编号 [0-4]: ").strip()
        
        if choice == "1":
            solve_and_play(use_beam_search=True, countdown=2)
        elif choice == "2":
            hotkey_listener_mode()
        elif choice == "3":
            test_screen_recognition()
        elif choice == "4":
            calibrate_board()
        elif choice == "0":
            print("[✓] 感谢使用，脚本已退出。")
            break
        else:
            print("[-] 无效选项，请重新输入。")

if __name__ == "__main__":
    main_menu()
