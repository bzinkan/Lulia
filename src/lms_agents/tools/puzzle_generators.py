"""
Puzzle Generators — algorithmic content generators for game-based templates.

These produce structured data that the template renderer turns into print-ready HTML.
Each generator accepts educational content and returns puzzle-specific structures.
"""
import random
import string
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Word Search
# ---------------------------------------------------------------------------

def generate_word_search(
    words: list[str],
    grid_size: int = 15,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a word search puzzle.

    Args:
        words: vocabulary words to place (will be uppercased)
        grid_size: NxN grid dimension (12-20)
        seed: random seed for reproducibility

    Returns:
        {
          "grid": [[str, ...], ...],  # student grid (with random fill)
          "solution_grid": [[str, ...], ...],  # answer key with placed words marked
          "words": [str, ...],
          "placements": [{"word": str, "row": int, "col": int, "direction": str}, ...]
        }
    """
    if seed is not None:
        random.seed(seed)

    words = [w.upper().replace(" ", "") for w in words if w.strip()]
    words.sort(key=len, reverse=True)

    grid = [["" for _ in range(grid_size)] for _ in range(grid_size)]
    solution = [["." for _ in range(grid_size)] for _ in range(grid_size)]
    placements = []

    directions = [
        (0, 1, "right"), (1, 0, "down"), (1, 1, "diagonal_down_right"),
        (0, -1, "left"), (-1, 0, "up"), (-1, -1, "diagonal_up_left"),
        (1, -1, "diagonal_down_left"), (-1, 1, "diagonal_up_right"),
    ]

    for word in words:
        placed = False
        for _ in range(200):  # attempts
            dr, dc, dir_name = random.choice(directions)
            r = random.randint(0, grid_size - 1)
            c = random.randint(0, grid_size - 1)

            # Check if word fits
            end_r = r + dr * (len(word) - 1)
            end_c = c + dc * (len(word) - 1)
            if not (0 <= end_r < grid_size and 0 <= end_c < grid_size):
                continue

            # Check for conflicts
            ok = True
            for i, letter in enumerate(word):
                nr, nc = r + dr * i, c + dc * i
                existing = grid[nr][nc]
                if existing and existing != letter:
                    ok = False
                    break

            if ok:
                for i, letter in enumerate(word):
                    nr, nc = r + dr * i, c + dc * i
                    grid[nr][nc] = letter
                    solution[nr][nc] = letter
                placements.append({"word": word, "row": r, "col": c, "direction": dir_name})
                placed = True
                break

        if not placed:
            # Skip words that couldn't be placed
            pass

    # Fill empty cells with random letters
    for r in range(grid_size):
        for c in range(grid_size):
            if not grid[r][c]:
                grid[r][c] = random.choice(string.ascii_uppercase)

    placed_words = [p["word"] for p in placements]
    return {
        "grid": grid,
        "solution_grid": solution,
        "words": placed_words,
        "placements": placements,
        "grid_size": grid_size,
    }


# ---------------------------------------------------------------------------
# 2. Crossword
# ---------------------------------------------------------------------------

def generate_crossword(
    clues: list[dict],
    grid_size: int = 20,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a crossword puzzle from clue/answer pairs.

    Args:
        clues: [{"clue": str, "answer": str}, ...]
        grid_size: NxN grid dimension
        seed: random seed

    Returns:
        {
          "grid": [[str|None, ...], ...],  # None = black, "" = empty white
          "solution_grid": [[str|None, ...], ...],
          "across_clues": [{"number": int, "clue": str, "answer": str, "row": int, "col": int}, ...],
          "down_clues": [{"number": int, "clue": str, "answer": str, "row": int, "col": int}, ...],
          "numbers_grid": [[int|None, ...], ...],
        }
    """
    if seed is not None:
        random.seed(seed)

    entries = [{"clue": c["clue"], "answer": c["answer"].upper().replace(" ", "")} for c in clues]
    entries.sort(key=lambda x: len(x["answer"]), reverse=True)

    grid = [[None for _ in range(grid_size)] for _ in range(grid_size)]
    placed = []

    # Place first word horizontally in the middle
    if entries:
        first = entries[0]
        row = grid_size // 2
        col = (grid_size - len(first["answer"])) // 2
        for i, ch in enumerate(first["answer"]):
            grid[row][col + i] = ch
        placed.append({"entry": first, "row": row, "col": col, "direction": "across"})

    # Try to place remaining words by intersecting
    for entry in entries[1:]:
        word = entry["answer"]
        best = None
        best_score = -1

        for pi, p in enumerate(placed):
            p_word = p["entry"]["answer"]
            for wi, wc in enumerate(word):
                for pi2, pc in enumerate(p_word):
                    if wc != pc:
                        continue
                    # Try intersecting
                    if p["direction"] == "across":
                        # Place new word down
                        new_row = p["row"] - wi
                        new_col = p["col"] + pi2
                        if new_row < 0 or new_row + len(word) > grid_size:
                            continue
                        ok = True
                        for j, ch in enumerate(word):
                            r = new_row + j
                            existing = grid[r][new_col]
                            if existing is not None and existing != ch:
                                ok = False
                                break
                            # Check adjacent cells
                            if existing is None:
                                if new_col > 0 and grid[r][new_col - 1] is not None and j != wi:
                                    ok = False
                                    break
                                if new_col < grid_size - 1 and grid[r][new_col + 1] is not None and j != wi:
                                    ok = False
                                    break
                        if ok:
                            score = len(word) + random.random()
                            if score > best_score:
                                best = {"entry": entry, "row": new_row, "col": new_col, "direction": "down"}
                                best_score = score
                    else:
                        # Place new word across
                        new_row = p["row"] + pi2
                        new_col = p["col"] - wi
                        if new_col < 0 or new_col + len(word) > grid_size:
                            continue
                        ok = True
                        for j, ch in enumerate(word):
                            c = new_col + j
                            existing = grid[new_row][c]
                            if existing is not None and existing != ch:
                                ok = False
                                break
                            if existing is None:
                                if new_row > 0 and grid[new_row - 1][c] is not None and j != wi:
                                    ok = False
                                    break
                                if new_row < grid_size - 1 and grid[new_row + 1][c] is not None and j != wi:
                                    ok = False
                                    break
                        if ok:
                            score = len(word) + random.random()
                            if score > best_score:
                                best = {"entry": entry, "row": new_row, "col": new_col, "direction": "across"}
                                best_score = score

        if best:
            word = best["entry"]["answer"]
            if best["direction"] == "across":
                for i, ch in enumerate(word):
                    grid[best["row"]][best["col"] + i] = ch
            else:
                for i, ch in enumerate(word):
                    grid[best["row"] + i][best["col"]] = ch
            placed.append(best)

    # Assign clue numbers
    numbers = [[None for _ in range(grid_size)] for _ in range(grid_size)]
    across_clues = []
    down_clues = []
    num = 1

    for r in range(grid_size):
        for c in range(grid_size):
            if grid[r][c] is None:
                continue
            starts_across = (c == 0 or grid[r][c - 1] is None) and c + 1 < grid_size and grid[r][c + 1] is not None
            starts_down = (r == 0 or grid[r - 1][c] is None) and r + 1 < grid_size and grid[r + 1][c] is not None
            if starts_across or starts_down:
                numbers[r][c] = num
                for p in placed:
                    if p["row"] == r and p["col"] == c and p["direction"] == "across" and starts_across:
                        across_clues.append({"number": num, "clue": p["entry"]["clue"], "answer": p["entry"]["answer"], "row": r, "col": c})
                    if p["row"] == r and p["col"] == c and p["direction"] == "down" and starts_down:
                        down_clues.append({"number": num, "clue": p["entry"]["clue"], "answer": p["entry"]["answer"], "row": r, "col": c})
                num += 1

    # Create solution grid (copy) and empty grid
    solution = [row[:] for row in grid]
    empty = [[("" if cell is not None else None) for cell in row] for row in grid]

    return {
        "grid": empty,
        "solution_grid": solution,
        "across_clues": across_clues,
        "down_clues": down_clues,
        "numbers_grid": numbers,
        "grid_size": grid_size,
        "placed_count": len(placed),
    }


# ---------------------------------------------------------------------------
# 3. Board Game
# ---------------------------------------------------------------------------

def generate_board_game(
    questions: list[dict],
    total_spaces: int = 36,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a path-based board game.

    Every 3-4 spaces has a question. Special spaces scattered throughout.
    """
    if seed is not None:
        random.seed(seed)

    specials = ["Go back 2 spaces", "Roll again!", "Lose a turn", "Move ahead 2 spaces"]
    spaces = []
    q_idx = 0

    for i in range(total_spaces):
        if i == 0:
            spaces.append({"index": i, "type": "start", "label": "START"})
        elif i == total_spaces - 1:
            spaces.append({"index": i, "type": "finish", "label": "FINISH!"})
        elif (i % 4 == 0 or i % 3 == 0) and q_idx < len(questions) and i > 1:
            q = questions[q_idx]
            spaces.append({
                "index": i,
                "type": "question",
                "label": f"Q{q_idx + 1}",
                "question": q.get("question_text", ""),
                "answer": q.get("answer", ""),
            })
            q_idx += 1
        elif random.random() < 0.15 and i > 2 and i < total_spaces - 3:
            spaces.append({"index": i, "type": "special", "label": random.choice(specials)})
        else:
            spaces.append({"index": i, "type": "normal", "label": str(i)})

    return {
        "spaces": spaces,
        "total_spaces": total_spaces,
        "question_count": q_idx,
        "instructions": "Roll a die and move that many spaces. If you land on a question space, answer correctly to stay — wrong answer means go back to your previous spot. First to FINISH wins!",
    }


# ---------------------------------------------------------------------------
# 4. Scavenger Hunt
# ---------------------------------------------------------------------------

def generate_scavenger_hunt(
    questions: list[dict],
    locations: Optional[list[str]] = None,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a classroom scavenger hunt with clue cards.

    Each station has a question + a clue leading to the next location.
    """
    if seed is not None:
        random.seed(seed)

    default_locations = [
        "the teacher's desk", "the bookshelf", "the whiteboard",
        "the window sill", "the coat hooks", "the reading corner",
        "the supply shelf", "the calendar wall", "the art station",
        "the door", "the globe", "the computer station",
    ]
    locs = locations or default_locations
    random.shuffle(locs)

    stations = []
    num_stations = min(len(questions), len(locs) - 1, 12)

    for i in range(num_stations):
        q = questions[i] if i < len(questions) else {"question_text": "Bonus question!", "answer": ""}
        next_loc = locs[i + 1] if i + 1 < len(locs) else "the finish line"
        stations.append({
            "station_number": i + 1,
            "location": locs[i],
            "question": q.get("question_text", ""),
            "answer": q.get("answer", ""),
            "next_clue": f"Great job! Your next clue is at {next_loc}.",
            "standard_code": q.get("standard_code", ""),
        })

    return {
        "stations": stations,
        "start_location": locs[0],
        "teacher_setup": [
            f"Station {s['station_number']}: Place card at {s['location']}" for s in stations
        ],
        "instructions": f"Start at {locs[0]}. Read the question, write your answer, then follow the clue to the next station!",
    }


# ---------------------------------------------------------------------------
# 5. Escape Room
# ---------------------------------------------------------------------------

def generate_escape_room(
    questions: list[dict],
    num_stages: int = 4,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate an escape room with puzzle stages.

    Each stage's answer contributes a digit/letter to the final unlock code.
    """
    if seed is not None:
        random.seed(seed)

    stages = []
    final_code = ""

    # Use first N questions as stages
    stage_questions = questions[:num_stages]
    if len(stage_questions) < num_stages:
        stage_questions.extend(questions[:num_stages - len(stage_questions)])

    themes = [
        {"name": "The Cipher Lock", "desc": "Decode the message to find the first digit"},
        {"name": "The Number Puzzle", "desc": "Solve the math problem to find the next digit"},
        {"name": "The Pattern Breaker", "desc": "Find the pattern to reveal the code"},
        {"name": "The Final Challenge", "desc": "One last puzzle stands between you and freedom"},
        {"name": "The Hidden Clue", "desc": "Look carefully to find what's hidden"},
    ]

    for i, q in enumerate(stage_questions):
        answer = q.get("answer", "")
        # Extract a code digit from the answer
        digits = [c for c in str(answer) if c.isdigit()]
        code_digit = digits[0] if digits else str(random.randint(1, 9))
        final_code += code_digit

        theme = themes[i % len(themes)]
        stages.append({
            "stage_number": i + 1,
            "name": theme["name"],
            "description": theme["desc"],
            "question": q.get("question_text", ""),
            "answer": answer,
            "code_digit": code_digit,
            "hint": f"The answer to this problem gives you digit #{i + 1} of the lock code.",
            "standard_code": q.get("standard_code", ""),
        })

    return {
        "stages": stages,
        "final_code": final_code,
        "num_stages": len(stages),
        "instructions": f"You are locked in! Solve all {len(stages)} puzzles to find the {len(stages)}-digit code that opens the lock. Write each code digit on your recording sheet.",
        "teacher_guide": [
            f"Stage {s['stage_number']} ({s['name']}): Answer is '{s['answer']}', code digit is {s['code_digit']}"
            for s in stages
        ],
    }
