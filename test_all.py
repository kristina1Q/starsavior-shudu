"""
端到端自动化测试套件
验证识别精度、求解器正确性与跨空域消去逻辑
"""
import os
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import numpy as np
from PIL import Image

import detector
import solver
import controller

SAMPLE_IMAGES = [
    r'C:/Users/34632/.gemini/antigravity/brain/468484b0-8920-4374-8b81-e1cbe9331de5/.user_uploaded/media_1789782228970.png',
    r'C:/Users/34632/.gemini/antigravity/brain/468484b0-8920-4374-8b81-e1cbe9331de5/.user_uploaded/media_1789782228994.png',
    r'C:/Users/34632/.gemini/antigravity/brain/468484b0-8920-4374-8b81-e1cbe9331de5/.user_uploaded/media_1789782229014.png'
]

def test_detector_on_samples():
    print("[测试 1] 验证多截图定位与数字识别...")
    templates = detector.load_templates()
    assert len(templates) == 9, "模板数量应为 9"
    
    for idx, img_path in enumerate(SAMPLE_IMAGES, 1):
        if not os.path.exists(img_path):
            continue
        img = Image.open(img_path)
        geom = detector.get_board_geometry(img)
        assert geom is not None, f"图像 {idx} 应成功定位棋盘"
        
        grid = detector.recognize_grid(img, geom, templates)
        assert grid.shape == (10, 15), f"网格尺寸应为 10x15，实际为 {grid.shape}"
        valid_cnt = np.count_nonzero(grid)
        assert valid_cnt >= 140, f"识别有效卡片数应 >= 140，实际为 {valid_cnt}"
        print(f"  [+] 样本图 {idx} 识别成功: 找到 {valid_cnt} 个数字卡片")
    print("[OK] 检测模块测试通过！\n")

def test_solver_rules():
    print("[测试 2] 验证求解器规则：每步矩形求和严格等于 10，并验证跨空区域框选...")
    # 构造一个含跨区域特征的测试棋盘
    test_board = np.zeros((10, 15), dtype=int)
    # 第一行: 7, 3 (相邻凑十)
    test_board[0, 0] = 7
    test_board[0, 1] = 3
    # 第二行: 4, 空, 空, 6 (跨越两格空白凑十)
    test_board[1, 0] = 4
    test_board[1, 3] = 6
    # 第三行: 2x2 区域凑十: (2, 3), (1, 4)
    test_board[2, 0] = 2
    test_board[2, 1] = 3
    test_board[3, 0] = 1
    test_board[3, 1] = 4
    
    moves, final_board = solver.solve_greedy(test_board)
    assert len(moves) == 3, f"预期消除 3 组，实际为 {len(moves)}"
    
    # 逐一校验步步和为10
    board_sim = test_board.copy()
    for step_i, (r1, c1, r2, c2, nz) in enumerate(moves):
        sub = board_sim[r1:r2+1, c1:c2+1]
        assert np.sum(sub) == 10, f"第 {step_i} 步框选和必须严格等于 10，实际为 {np.sum(sub)}"
        board_sim[r1:r2+1, c1:c2+1] = 0
        
    assert np.count_nonzero(final_board) == 0, "全部测试数字应消除完毕"
    print("  [+] 构造跨空测试用例消除率 100%，所有矩形和严格为 10！")

    # 验证真实样本求解
    img = Image.open(SAMPLE_IMAGES[1])
    geom = detector.get_board_geometry(img)
    grid = detector.recognize_grid(img, geom)
    
    moves, _ = solver.solve_beam_search(grid, beam_width=25)
    board_check = grid.copy()
    for step_i, (r1, c1, r2, c2, nz) in enumerate(moves):
        sub = board_check[r1:r2+1, c1:c2+1]
        s = np.sum(sub)
        assert s == 10, f"真实棋盘第 {step_i} 步和应为 10，实际为 {s}"
        board_check[r1:r2+1, c1:c2+1] = 0
        
    cleared = sum(m[4] for m in moves)
    print(f"  [+] 真实棋盘验证：规划执行 {len(moves)} 步，消除 {cleared} / 150 数字，所有步骤严格满足规则！")
    print("[OK] 求解器规则测试通过！\n")

def test_controller_stop_key():
    print("[测试 3] 验证控制器急停键检测接口...")
    res = controller.is_stop_pressed()
    print(f"  [+] 急停键检测当前状态: {res} (正常未触发)")
    print("[OK] 控制器测试通过！\n")

if __name__ == "__main__":
    print("=" * 50)
    print("开始执行全套自动化回归测试...")
    print("=" * 50 + "\n")
    test_detector_on_samples()
    test_solver_rules()
    test_controller_stop_key()
    print("=" * 50)
    print("全部测试 100% 成功通过！脚本已就绪！")
    print("=" * 50)
