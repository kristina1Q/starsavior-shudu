"""
凑十游戏（苹果游戏/Fruit Box）求解器
核心算法：二维前缀和 + 启发式贪心与束搜索（Beam Search）
支持消除后跨越空白区域（0）继续进行矩形消除
"""
import numpy as np

def compute_prefix_sum(board):
    """计算二维前缀和，用于 O(1) 查询任意矩形内数字之和"""
    R, C = board.shape
    pref = np.zeros((R + 1, C + 1), dtype=int)
    pref[1:, 1:] = np.cumsum(np.cumsum(board, axis=0), axis=1)
    return pref

def rect_sum(pref, r1, c1, r2, c2):
    """查询矩形 [r1, r2] x [c1, c2] 内所有数字之和"""
    return pref[r2 + 1, c2 + 1] - pref[r1, c2 + 1] - pref[r2 + 1, c1] + pref[r1, c1]

def find_valid_rectangles(board):
    """
    检索当前棋盘所有和为 10 的有效矩形
    返回: list of (r1, c1, r2, c2, non_zero_count, area)
    """
    R, C = board.shape
    pref = compute_prefix_sum(board)
    valid = []
    
    for r1 in range(R):
        for r2 in range(r1, R):
            for c1 in range(C):
                for c2 in range(c1, C):
                    s = rect_sum(pref, r1, c1, r2, c2)
                    if s == 10:
                        sub = board[r1:r2+1, c1:c2+1]
                        nz_count = np.count_nonzero(sub)
                        # 只有包含实际有效数字时才有效（至少包含数字）
                        if nz_count > 0:
                            area = (r2 - r1 + 1) * (c2 - c1 + 1)
                            valid.append((r1, c1, r2, c2, nz_count, area))
    return valid

def solve_greedy(initial_board, prioritize_compact=True):
    """
    快速贪心求解算法：每一步选择最优矩形并将其消除（置为0），循环直到无法继续
    
    :param initial_board: 10x15 numpy 数组
    :param prioritize_compact: 是否优先选择紧凑（面积小）的矩形
    :return: moves (list of (r1, c1, r2, c2, nz_count)), final_board
    """
    board = initial_board.copy()
    R, C = board.shape
    moves = []
    
    while True:
        candidates = find_valid_rectangles(board)
        if not candidates:
            break
            
        if prioritize_compact:
            # 排序规则：优先面积最小，其次消除数字最多
            candidates.sort(key=lambda x: (-x[5], x[4]), reverse=True)
        else:
            # 排序规则：优先消除数字最多，其次面积最小
            candidates.sort(key=lambda x: (x[4], -x[5]), reverse=True)
            
        best = candidates[0]
        r1, c1, r2, c2, nz_count, _ = best
        
        # 记录动作
        moves.append((r1, c1, r2, c2, nz_count))
        # 执行消除：框内所有数字置为 0
        board[r1:r2+1, c1:c2+1] = 0
        
    return moves, board

def solve_beam_search(initial_board, beam_width=40, max_steps=70):
    """
    束搜索（Beam Search）求解算法：探索多条消除分支，最大化总消除率
    
    :param initial_board: 10x15 numpy 数组
    :param beam_width: 束宽度（保留的优质状态数）
    :param max_steps: 最大搜索步数
    :return: best_moves, final_board
    """
    board_init = initial_board.copy()
    R, C = board_init.shape
    
    # 状态元组: (累计消除数, 棋盘bytes, 动作列表)
    beam = [(0, board_init.tobytes(), [])]
    
    best_overall_moves = []
    best_overall_cleared = 0
    best_overall_board = board_init
    
    for _ in range(max_steps):
        next_beam = []
        seen = set()
        
        for cleared_cnt, b_bytes, moves in beam:
            board = np.frombuffer(b_bytes, dtype=int).reshape((R, C)).copy()
            candidates = find_valid_rectangles(board)
            
            if not candidates:
                if cleared_cnt > best_overall_cleared:
                    best_overall_cleared = cleared_cnt
                    best_overall_moves = moves
                    best_overall_board = board
                continue
                
            # 候选排序：先紧凑再消数
            candidates.sort(key=lambda x: (-x[5], x[4]), reverse=True)
            
            # 每个状态取前 6~8 个最优分支
            for r1, c1, r2, c2, nz_count, area in candidates[:8]:
                new_board = board.copy()
                new_board[r1:r2+1, c1:c2+1] = 0
                new_bytes = new_board.tobytes()
                
                if new_bytes not in seen:
                    seen.add(new_bytes)
                    new_cleared = cleared_cnt + nz_count
                    next_beam.append((new_cleared, new_bytes, moves + [(r1, c1, r2, c2, nz_count)]))
                    if new_cleared > best_overall_cleared:
                        best_overall_cleared = new_cleared
                        best_overall_moves = moves + [(r1, c1, r2, c2, nz_count)]
                        best_overall_board = new_board
                        
        if not next_beam:
            break
            
        next_beam.sort(key=lambda x: x[0], reverse=True)
        beam = next_beam[:beam_width]
        
    return best_overall_moves, best_overall_board
