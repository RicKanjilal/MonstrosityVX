import pygame
import chess
import os
import time
from collections import defaultdict

# ==========================
# CONFIG
# ==========================
TILE = 80
BOARD = TILE * 8
WHITE_COLOR = (240, 217, 181)
BROWN_COLOR = (181, 136, 99)
ENGINE_MOVE_DELAY = 120  # visual delay before engine moves (ms)

MAX_DEPTH = 32  # Increased max search depth for safety
TIME_LIMIT_MS = 10000  # time per move for engine (in ms)
INF = 10 ** 9
MATE_SCORE = 100000
TT_MAX_SIZE = 200_000
MAX_PLY = 64

# Engine Pruning/Tuning
NULL_MOVE_R = 2
LMR_MIN_DEPTH = 3
LMR_MIN_MOVES = 4
HISTORY_DECAY = 4

# ==========================
# INIT
# ==========================
pygame.init()
screen = pygame.display.set_mode((BOARD, BOARD))
pygame.display.set_caption("Monstrocity")
clock = pygame.time.Clock()

# ==========================
# LOAD PIECES
# ==========================
pieces_img = {}
# Ensure the 'assets' folder with pieces is present
for color in ("w", "b"):
    for piece in ("P", "R", "N", "B", "Q", "K"):
        try:
            path = os.path.join("assets", f"{color}{piece}.png")
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (TILE, TILE))
            pieces_img[color + piece] = img
        except pygame.error:
            print(f"Warning: Could not load piece image {color}{piece}.png. Check 'assets' folder.")
            pieces_img[color + piece] = pygame.Surface((TILE, TILE))  # Placeholder

# ==========================
# BOARD & GLOBAL ENGINE STATE
# ==========================
board = chess.Board()
selected = None
legal_moves = []
last_move = None

# Transposition table:
# key -> (score, depth, flag, best_move)
TT_EXACT = 0
TT_LOWER = 1  # lower bound (alpha)
TT_UPPER = 2  # upper bound (beta)
transposition_table = {}

# Killer moves: two killers per ply
killer_moves = [[None, None] for _ in range(MAX_PLY)]

# History heuristic: move -> score (now global, not just for root)
history_heuristic = defaultdict(int)

# Zobrist keys (initial generation is fine)
ZOBRIST_KEYS = defaultdict(lambda: os.urandom(8))

# ==========================
# PIECE VALUES & PST (Tapered)
# ==========================
# Piece values for Material and MVV-LVA
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000  # King value for phase calculation, not material
}
# For MVV-LVA (capture ordering) - same as PIECE_VALUES essentially
MVV_LVA_VALUES = PIECE_VALUES

# Tapered PSTs (Middlegame / Endgame)
# From White's POV; Black is mirrored. Values are Centipawns.

# Midgame (MG) and Endgame (EG) PSTs
PST_MG = {
    chess.PAWN: [
        0, 0, 0, 0, 0, 0, 0, 0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5, 5, 10, 25, 25, 10, 5, 5,
        0, 0, 0, 20, 20, 0, 0, 0,
        5, -5, -10, 0, 0, -10, -5, 5,
        5, 10, 10, -20, -20, 10, 10, 5,
        0, 0, 0, 0, 0, 0, 0, 0
    ],
    chess.KNIGHT: [
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20, 0, 0, 0, 0, -20, -40,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -40, -20, 0, 5, 5, 0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50
    ],
    chess.BISHOP: [
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 5, 0, 0, 0, 0, 5, -10,
        -20, -10, -10, -10, -10, -10, -10, -20
    ],
    chess.ROOK: [
        0, 0, 0, 0, 0, 0, 0, 0,
        5, 10, 10, 10, 10, 10, 10, 5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        0, 0, 0, 5, 5, 0, 0, 0
    ],
    chess.QUEEN: [
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5,
        0, 0, 5, 5, 5, 5, 0, -5,
        -10, 5, 5, 5, 5, 5, 0, -10,
        -10, 0, 5, 0, 0, 0, 0, -10,
        -20, -10, -10, -5, -5, -10, -10, -20
    ],
    chess.KING: [
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -10, -20, -20, -20, -20, -20, -20, -10,
        20, 20, 0, 0, 0, 0, 20, 20,
        20, 30, 10, 0, 0, 10, 30, 20
    ]
}

PST_EG = {
    chess.PAWN: PST_MG[chess.PAWN],  # No major change for pawns
    chess.KNIGHT: [p - 10 for p in PST_MG[chess.KNIGHT]],  # Knighs less effective in EG
    chess.BISHOP: PST_MG[chess.BISHOP],
    chess.ROOK: PST_MG[chess.ROOK],
    chess.QUEEN: PST_MG[chess.QUEEN],
    chess.KING: [  # Endgame King: Centralize!
        -50, -30, -30, -30, -30, -30, -30, -50,
        -30, -10, 0, 0, 0, 0, -10, -30,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -30, -10, 0, 0, 0, 0, -10, -30,
        -50, -30, -30, -30, -30, -30, -30, -50
    ]
}

# Total material that defines the Middlegame -> Endgame transition
TOTAL_PHASE_MATERIAL = (
        PIECE_VALUES[chess.KNIGHT] * 4 +
        PIECE_VALUES[chess.BISHOP] * 4 +
        PIECE_VALUES[chess.ROOK] * 4 +
        PIECE_VALUES[chess.QUEEN] * 2
)  # = 4*320 + 4*330 + 4*500 + 2*900 = 1280 + 1320 + 2000 + 1800 = 6400 (Adjusted total for scaling)


# ==========================
# ZOBRIST HASHING
# ==========================
def zobrist_hash(b: chess.Board) -> int:
    h = 0
    # ... (Zobrist keys initialization remains the same)
    for square, piece in b.piece_map().items():
        h ^= int.from_bytes(ZOBRIST_KEYS[(square, piece.symbol(), piece.color)], "big")

    if b.turn == chess.BLACK:
        h ^= int.from_bytes(ZOBRIST_KEYS["black_to_move"], "big")

    if b.has_kingside_castling_rights(chess.WHITE):
        h ^= int.from_bytes(ZOBRIST_KEYS["castle_K"], "big")
    if b.has_queenside_castling_rights(chess.WHITE):
        h ^= int.from_bytes(ZOBRIST_KEYS["castle_Q"], "big")
    if b.has_kingside_castling_rights(chess.BLACK):
        h ^= int.from_bytes(ZOBRIST_KEYS["castle_k"], "big")
    if b.has_queenside_castling_rights(chess.BLACK):
        h ^= int.from_bytes(ZOBRIST_KEYS["castle_q"], "big")

    if b.ep_square is not None:
        h ^= int.from_bytes(ZOBRIST_KEYS[("ep", b.ep_square)], "big")

    return h


# ==========================
# EVALUATION HELPERS
# ==========================
def pst_index(piece: chess.Piece, square: chess.Square) -> int:
    """Return PST index, mirroring for Black."""
    if piece.color == chess.WHITE:
        return square
    # Mirror vertically for Black (0 to 63)
    return chess.square_mirror(square)


def calculate_phase(b: chess.Board) -> float:
    """Calculate the game phase (0.0=Endgame, 1.0=Middlegame)."""
    current_phase_material = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        current_phase_material += len(b.pieces(piece_type, chess.WHITE)) * PIECE_VALUES[piece_type]
        current_phase_material += len(b.pieces(piece_type, chess.BLACK)) * PIECE_VALUES[piece_type]

    # Normalize the phase score
    phase = current_phase_material / TOTAL_PHASE_MATERIAL
    return max(0.0, min(1.0, phase))


def count_pawn_structure(b: chess.Board, color: bool, phase: float):
    """Simple doubled / isolated / passed pawn evaluation, with phase weighting."""
    pawns = b.pieces(chess.PAWN, color)
    if not pawns:
        return 0

    score = 0
    files_with_pawns = [0] * 8

    pawn_squares = list(chess.SquareSet(pawns))
    for sq in pawn_squares:
        f = chess.square_file(sq)
        files_with_pawns[f] += 1

    # Doubled pawns (Middlegame focus)
    for f in range(8):
        if files_with_pawns[f] > 1:
            score -= 15 * (files_with_pawns[f] - 1) * phase

    # Isolated & passed pawns
    enemy_color = not color
    enemy_pawns = b.pieces(chess.PAWN, enemy_color)

    for sq in pawn_squares:
        file_ = chess.square_file(sq)
        rank_ = chess.square_rank(sq)

        # Isolated (Middlegame focus)
        left_file = file_ - 1
        right_file = file_ + 1
        isolated = True
        for f in (left_file, right_file):
            if 0 <= f < 8:
                if any(chess.square(f, r) in pawns for r in range(8)):
                    isolated = False
                    break
        if isolated:
            score -= 10 * phase

        # Passed pawn check (Endgame focus)
        passed = True
        for f in range(file_ - 1, file_ + 2):
            if not (0 <= f < 8):
                continue
            # Iterate through squares *ahead* of the pawn's rank
            start_rank = rank_ + 1 if color == chess.WHITE else 0
            end_rank = 8 if color == chess.WHITE else rank_

            for r in range(start_rank, end_rank):
                sq2 = chess.square(f, r)
                if sq2 in enemy_pawns:
                    passed = False
                    break
            if not passed:
                break

        if passed:
            # More advanced = bigger bonus (Endgame heavily weighted)
            # Rank 7/2 gets biggest bonus
            advancement = rank_ if color == chess.WHITE else (7 - rank_)
            bonus = 10 + advancement * 10
            score += bonus * (1.0 - phase)  # Heavily weight for endgame

    return score


def king_safety(b: chess.Board, color: bool, phase: float):
    """King safety heavily weighted for middlegame."""
    if phase < 0.2:  # Too deep in endgame for safety to matter
        return 0

    king_sq = b.king(color)
    if king_sq is None:
        return 0

    score = 0

    # Simple check for being castled
    back_rank = chess.square_rank(king_sq)
    if (color == chess.WHITE and back_rank == 0) or (color == chess.BLACK and back_rank == 7):
        file = chess.square_file(king_sq)
        if file in (2, 6):  # c or g file
            score += 20 * phase  # Bonus for castled king in middlegame

    # Simple penalty for king in center
    if 2 <= chess.square_file(king_sq) <= 5 and 2 <= chess.square_rank(king_sq) <= 5:
        score -= 20 * phase

    return score


def mobility(b: chess.Board, color: bool):
    """Mobility: count legal moves for the side (lightly weighted)."""
    # Temporarily switch turn if needed to get correct moves
    b_turn = b.turn
    b.turn = color
    moves = sum(1 for _ in b.legal_moves)
    b.turn = b_turn

    return moves * 3


def evaluate_board(b: chess.Board) -> int:
    """Return score from side-to-move's perspective using Tapered Eval."""
    # Terminal states
    if b.is_checkmate():
        # Score is lower if mate is shallow, higher if deep
        return -MATE_SCORE
    if b.is_stalemate() or b.is_insufficient_material() or b.is_fivefold_repetition():
        return 0

    # Calculate Phase (0.0=Endgame, 1.0=Middlegame)
    phase = calculate_phase(b)

    white_mg_score = 0
    black_mg_score = 0
    white_eg_score = 0
    black_eg_score = 0
    white_mat = 0
    black_mat = 0

    for square, piece in b.piece_map().items():
        if piece.piece_type == chess.KING:
            continue

        value = PIECE_VALUES.get(piece.piece_type, 0)
        idx = pst_index(piece, square)

        mg_bonus = PST_MG.get(piece.piece_type, [0] * 64)[idx]
        eg_bonus = PST_EG.get(piece.piece_type, [0] * 64)[idx]

        if piece.color == chess.WHITE:
            white_mat += value
            white_mg_score += value + mg_bonus
            white_eg_score += value + eg_bonus
        else:
            black_mat += value
            black_mg_score += value + mg_bonus
            black_eg_score += value + eg_bonus

    # Pawn Structure, Mobility, King Safety (weighted by phase)
    white_mg_score += count_pawn_structure(b, chess.WHITE, 1.0)
    black_mg_score += count_pawn_structure(b, chess.BLACK, 1.0)
    white_eg_score += count_pawn_structure(b, chess.WHITE, 0.0)
    black_eg_score += count_pawn_structure(b, chess.BLACK, 0.0)

    white_mg_score += king_safety(b, chess.WHITE, 1.0)
    black_mg_score += king_safety(b, chess.BLACK, 1.0)

    # Mobility (lightly weighted, doesn't depend on phase much)
    white_mg_score += mobility(b, chess.WHITE)
    black_mg_score += mobility(b, chess.BLACK)
    white_eg_score += mobility(b, chess.WHITE)
    black_eg_score += mobility(b, chess.BLACK)

    # Tapered score (MG * phase + EG * (1 - phase))
    white_score = white_mg_score * phase + white_eg_score * (1.0 - phase)
    black_score = black_mg_score * phase + black_eg_score * (1.0 - phase)

    total_eval = int(white_score - black_score)

    # Convert to side-to-move perspective
    if b.turn == chess.WHITE:
        return total_eval
    else:
        return -total_eval


# ==========================
# MOVE ORDERING HELPERS
# ==========================
def update_killers(move: chess.Move, ply: int):
    if ply >= MAX_PLY:
        return
    km1, km2 = killer_moves[ply]
    if move == km1 or move == km2:
        return
    killer_moves[ply][1] = km1
    killer_moves[ply][0] = move


def move_order_score(b: chess.Board, move: chess.Move, tt_move: chess.Move, ply: int) -> int:
    score = 0

    # 1. TT move
    if tt_move is not None and move == tt_move:
        score += 10_000_000

    # 2. Captures with MVV-LVA
    if b.is_capture(move):
        victim = b.piece_at(move.to_square)
        if victim is None and b.is_en_passant(move):
            victim_value = MVV_LVA_VALUES[chess.PAWN]
        elif victim is not None:
            victim_value = MVV_LVA_VALUES.get(victim.piece_type, 0)
        else:
            victim_value = 0

        attacker = b.piece_at(move.from_square)
        attacker_value = MVV_LVA_VALUES.get(attacker.piece_type, 0) if attacker else 0

        mvv_lva = victim_value * 10 - attacker_value
        score += 5_000_000 + mvv_lva

    # 3. Promotions
    if move.promotion is not None:
        promotion_value = MVV_LVA_VALUES.get(move.promotion, 0)
        score += 4_000_000 + promotion_value

    else:
        # 4. Killer moves
        if ply < MAX_PLY:
            km1, km2 = killer_moves[ply]
            if move == km1:
                score += 90_000
            elif move == km2:
                score += 80_000

        # 5. History heuristic
        score += history_heuristic[move]

    return score


# ==========================
# QUIESCENCE SEARCH
# ==========================
def quiescence(b: chess.Board, alpha: int, beta: int) -> int:
    # 1. Stand pat
    stand_pat = evaluate_board(b)

    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    # 2. Generate and sort tactical moves
    tactical_moves = []
    for move in b.legal_moves:
        # Only consider captures and promotions (checks are good but can be delayed)
        if b.is_capture(move) or move.promotion is not None:
            tactical_moves.append(move)

    # Simple sort for quiescence (MVV-LVA for captures, Promotions last)
    tactical_moves.sort(key=lambda m: move_order_score(b, m, None, MAX_PLY), reverse=True)

    for move in tactical_moves:
        b.push(move)
        score = -quiescence(b, -beta, -alpha)
        b.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


# ==========================
# MAIN SEARCH (NEGAMAX + ALPHA-BETA + NMP + LMR)
# ==========================
def search(b: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
    # 1. Draw checks at node level
    if b.is_repetition() or b.is_stalemate() or b.is_insufficient_material() or b.is_fivefold_repetition():
        return 0

    in_check = b.is_check()

    # 2. Check Extension
    if in_check and depth < MAX_PLY:  # Only extend if not too deep
        depth += 1

    # 3. Depth / quiescence
    if depth <= 0:
        return quiescence(b, alpha, beta)

    # 4. Transposition table lookup
    key = zobrist_hash(b)
    tt_entry = transposition_table.get(key)
    tt_move = None

    if tt_entry is not None:
        tt_score, tt_depth, tt_flag, tt_move = tt_entry
        if tt_depth >= depth:
            if tt_flag == TT_EXACT:
                return tt_score
            elif tt_flag == TT_LOWER:
                if tt_score > alpha:
                    alpha = tt_score
            elif tt_flag == TT_UPPER:
                if tt_score < beta:
                    beta = tt_score
            if alpha >= beta:
                return tt_score

    # 5. Null Move Pruning (NMP)
    # Skip if in check, or if depth is too low, or if material is insufficient for mate (not implemented)
    if not in_check and depth >= NULL_MOVE_R and ply > 0:
        b.push(chess.Move.null())
        score = -search(b, depth - NULL_MOVE_R - 1, -beta, -beta + 1, ply + 1)
        b.pop()

        if score >= beta:
            # If null move yields a cutoff, we've found a good move!
            return beta

    moves = list(b.legal_moves)
    if not moves:
        # No legal moves -> checkmate or stalemate
        return (-MATE_SCORE + ply) if in_check else 0

    # 6. Move Ordering
    moves.sort(key=lambda m: move_order_score(b, m, tt_move, ply), reverse=True)

    best_score = -INF
    best_move_local = None
    alpha_orig = alpha

    move_count = 0

    for move in moves:
        move_count += 1
        is_cap_or_check = b.is_capture(move) or b.gives_check(move)

        # 7. Late Move Reduction (LMR)
        reduction = 0
        if depth >= LMR_MIN_DEPTH and move_count >= LMR_MIN_MOVES and not is_cap_or_check and move != tt_move:
            reduction = 1

        if depth >= 6 and move_count >= 8:
            reduction = 2

        b.push(move)

        # Reduced-depth search (PVS style)
        if reduction > 0:
            score = -search(b, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1)
            # If the reduced search is promising, do a full-depth re-search
            if score > alpha and reduction > 0:
                score = -search(b, depth - 1, -beta, -alpha, ply + 1)
        else:
            # Full-depth search (first move or highly-ranked moves)
            score = -search(b, depth - 1, -beta, -alpha, ply + 1)

        b.pop()

        if score > best_score:
            best_score = score
            best_move_local = move

        if score > alpha:
            if not is_cap_or_check:  # Only update history if it's a quiet move (non-tactical)
                history_heuristic[move] += depth * depth
            alpha = score

        if alpha >= beta:
            if not is_cap_or_check:
                update_killers(move, ply)
            break

    # 8. Store in TT
    if len(transposition_table) > TT_MAX_SIZE:
        transposition_table.clear()

    flag = TT_EXACT
    if best_score <= alpha_orig:
        flag = TT_UPPER
    elif best_score >= beta:
        flag = TT_LOWER

    transposition_table[key] = (best_score, depth, flag, best_move_local)
    return best_score


# ==========================
# ITERATIVE DEEPENING DRIVER
# ==========================
def engine_best_move(b: chess.Board,
                     max_depth: int = MAX_DEPTH,
                     time_limit_ms: int = TIME_LIMIT_MS) -> chess.Move | None:
    global transposition_table, killer_moves, history_heuristic

    if b.is_game_over():
        return None

    start_time = time.time()
    best_move = None

    # Decay history heuristic to avoid old scores dominating
    if b.fullmove_number % HISTORY_DECAY == 0:
        for move in history_heuristic:
            history_heuristic[move] //= 2

    # Clear killers for a fresh search (optional, but often done at root)
    killer_moves = [[None, None] for _ in range(MAX_PLY)]

    for depth in range(1, max_depth + 1):
        if (time.time() - start_time) * 1000 >= time_limit_ms:
            break

        local_best_move = None
        local_best_score = -INF
        local_alpha, local_beta = -INF, INF

        # Get TT move for initial ordering
        key = zobrist_hash(b)
        tt_entry = transposition_table.get(key)
        tt_move = tt_entry[3] if tt_entry is not None else None

        moves = list(b.legal_moves)
        moves.sort(key=lambda m: move_order_score(b, m, tt_move, 0), reverse=True)

        # Principal Variation Search (PVS) with Aspiration Window
        # This is a full-width search at the root, but we can try to narrow the window if a score is known.
        # For simplicity, we stick to the basic sorting and search here.

        for move in moves:
            if (time.time() - start_time) * 1000 >= time_limit_ms:
                # If time runs out, break and use the best_move found in the previous *complete* depth
                break

            is_cap_or_check = b.is_capture(move) or b.gives_check(move)

            b.push(move)

            # Simple Full-depth search at the root (No LMR/Reduction)
            score = -search(b, depth - 1, -local_beta, -local_alpha, 1)

            b.pop()

            if score > local_best_score:
                local_best_score = score
                local_best_move = move

            if score > local_alpha:
                if not is_cap_or_check:
                    history_heuristic[move] += depth * depth
                local_alpha = score

        # Only update best_move if the depth search completed fully
        if (time.time() - start_time) * 1000 < time_limit_ms:
            if local_best_move is not None:
                best_move = local_best_move
            # print(f"Depth {depth} completed. Score: {local_best_score}, Move: {best_move.uci() if best_move else 'N/A'}")

    return best_move


# ==========================
# GUI HELPERS (Unchanged)
# ==========================
def square_to_xy(sq):
    col = chess.square_file(sq)
    row = 7 - chess.square_rank(sq)
    return col * TILE, row * TILE


def xy_to_square(x, y):
    col = x // TILE
    row = 7 - (y // TILE)
    if 0 <= col < 8 and 0 <= row < 8:
        return chess.square(col, row)
    return None


def draw_board():
    for r in range(8):
        for c in range(8):
            color = WHITE_COLOR if (r + c) % 2 == 0 else BROWN_COLOR
            pygame.draw.rect(screen, color, (c * TILE, r * TILE, TILE, TILE))

    # Selected square highlight
    if selected is not None:
        sx, sy = square_to_xy(selected)
        surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        surf.fill((0, 255, 0, 90))
        screen.blit(surf, (sx, sy))

    # Legal moves highlight
    for sq in legal_moves:
        x, y = square_to_xy(sq)
        surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        surf.fill((0, 0, 255, 80))
        screen.blit(surf, (x, y))

    # Last move highlight
    if last_move:
        for sq in last_move:
            x, y = square_to_xy(sq)
            surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            surf.fill((255, 255, 0, 90))
            screen.blit(surf, (x, y))


def draw_pieces():
    for sq, p in board.piece_map().items():
        x, y = square_to_xy(sq)
        key = ("w" if p.color == chess.WHITE else "b") + p.symbol().upper()
        if key in pieces_img:
            screen.blit(pieces_img[key], (x, y))
        else:
            # Draw a basic square if image is missing
            pygame.draw.rect(screen, (255, 0, 0), (x, y, TILE, TILE), 1)


# ==========================
# MAIN LOOP
# ==========================
running = True

while running:
    clock.tick(60)

    # Engine plays Black
    if board.turn == chess.BLACK and not board.is_game_over():
        pygame.time.delay(ENGINE_MOVE_DELAY)
        mv = engine_best_move(board)
        if mv:
            board.push(mv)
            last_move = (mv.from_square, mv.to_square)

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        if e.type == pygame.MOUSEBUTTONDOWN and board.turn == chess.WHITE and not board.is_game_over():
            mx, my = pygame.mouse.get_pos()
            sq = xy_to_square(mx, my)

            if selected is None:
                if sq is not None:
                    piece = board.piece_at(sq)
                    if piece and piece.color == chess.WHITE:
                        selected = sq
                        legal_moves = [
                            m.to_square for m in board.legal_moves if m.from_square == sq
                        ]
            else:
                # Handle promotion: Default to Queen for simplicity
                mv = chess.Move(selected, sq)
                if board.piece_at(selected).piece_type == chess.PAWN and (
                        (sq in chess.SquareSet(chess.BB_RANK_8) and board.turn == chess.WHITE) or
                        (sq in chess.SquareSet(chess.BB_RANK_1) and board.turn == chess.BLACK)
                ):
                    mv = chess.Move(selected, sq, promotion=chess.QUEEN)

                if mv in board.legal_moves:
                    board.push(mv)
                    last_move = (mv.from_square, mv.to_square)
                selected = None
                legal_moves = []

        # Undo move on right click (for testing)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            if board.move_stack:
                board.pop()
                if board.move_stack:
                    last_move = (board.move_stack[-1].from_square, board.move_stack[-1].to_square)
                else:
                    last_move = None
            selected = None
            legal_moves = []

    draw_board()
    draw_pieces()
    pygame.display.flip()

pygame.quit()
