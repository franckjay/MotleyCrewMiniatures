import copy
from enum import Enum
from typing import List, Tuple, Optional, Dict, Set

class FigureType(Enum):
    KNIGHT = "Knight"
    BARBARIAN = "Barbarian"
    ARBALIST = "Arbalist"
    BLACK_MAGE = "Black Mage"
    WHITE_MAGE = "White Mage"

class Player(Enum):
    ONE = 1
    TWO = 2

class Figure:
    def __init__(self, figure_type: FigureType, player: Player):
        self.type = figure_type
        self.player = player
        self.position = None
        self.has_moved = False
        self.has_acted = False
        self.counter_containment_turns = 0

        # Set stats based on type
        if figure_type == FigureType.KNIGHT:
            self.max_life = 7
            self.move = 4
            self.attack = 3
            self.reach = 1
        elif figure_type == FigureType.BARBARIAN:
            self.max_life = 8
            self.move = 3
            self.attack = 4
            self.reach = 1
        elif figure_type == FigureType.ARBALIST:
            self.max_life = 5
            self.move = 2
            self.attack = 2
            self.reach = 3
        elif figure_type == FigureType.BLACK_MAGE:
            self.max_life = 7
            self.move = 2
            self.attack = 1
            self.reach = 2
        elif figure_type == FigureType.WHITE_MAGE:
            self.max_life = 4
            self.move = 2
            self.attack = 1
            self.reach = 2

        self.life = self.max_life
        self.is_dead = False

    def __repr__(self):
        return f"{self.type.value} (P{self.player.value}) [{self.life}/{self.max_life}]"

class GameState:
    def __init__(self):
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.current_player = Player.ONE
        self.figures = []
        self.dead_figures = {Player.ONE: [], Player.TWO: []}
        self.scores = {Player.ONE: 0, Player.TWO: 0}
        self.terrain = [(3, 0), (4, 7)]  # 4th row from left, 5th row from right
        self.magic_bomb_used = {Player.ONE: False, Player.TWO: False}
        self.turn_count = 0
        self.game_over = False
        self.winner = None

    def get_start_zone(self, player: Player):
        """Get the start zone rows for a player."""
        if player == Player.ONE:
            return [(row, col) for row in range(2) for col in range(8)]
        else:
            return [(row, col) for row in range(6, 8) for col in range(8)]

    def place_figure(self, figure: Figure, pos: Tuple[int, int]):
        """Place a figure on the board during setup."""
        row, col = pos
        if self.board[row][col] is not None:
            return False
        if pos not in self.get_start_zone(figure.player):
            return False

        self.board[row][col] = figure
        figure.position = pos
        self.figures.append(figure)
        return True

    def is_valid_position(self, pos: Tuple[int, int]):
        """Check if a position is within the board."""
        row, col = pos
        return 0 <= row < 8 and 0 <= col < 8

    def is_terrain(self, pos: Tuple[int, int]):
        """Check if a position is terrain."""
        return pos in self.terrain

    def get_figure_at(self, pos: Tuple[int, int]):
        """Get the figure at a given position."""
        if not self.is_valid_position(pos):
            return None
        row, col = pos
        return self.board[row][col]

    def move_figure(self, figure: Figure, new_pos: Tuple[int, int]):
        """Move a figure to a new position."""
        if figure.has_acted or figure.has_moved:
            return False, "Figure has already moved or acted this turn"

        if figure.counter_containment_turns > 0:
            return False, "Figure is contained and cannot move"

        if self.is_terrain(new_pos):
            return False, "Cannot move to terrain"

        if self.get_figure_at(new_pos) is not None:
            return False, "Position is occupied"

        # Check if move is within range
        old_row, old_col = figure.position
        new_row, new_col = new_pos

        # Arbalist can move diagonally
        if figure.type == FigureType.ARBALIST:
            distance = max(abs(new_row - old_row), abs(new_col - old_col))
        else:
            distance = abs(new_row - old_row) + abs(new_col - old_col)

        if distance > figure.move:
            return False, "Move is out of range"

        # Check path is clear (except for knight charge)
        if not self._is_path_clear(figure.position, new_pos, figure.type == FigureType.ARBALIST):
            return False, "Path is blocked"

        # Move the figure
        self.board[old_row][old_col] = None
        self.board[new_row][new_col] = figure
        figure.position = new_pos
        figure.has_moved = True

        return True, "Move successful"

    def knight_charge(self, knight: Figure, direction: str):
        """Perform knight charge special action."""
        if knight.type != FigureType.KNIGHT:
            return False, "Only knights can charge"

        if knight.has_moved or knight.has_acted:
            return False, "Cannot charge after moving or acting"

        if knight.counter_containment_turns > 0:
            return False, "Knight is contained"

        row, col = knight.position
        damaged_figures = []

        # Determine direction vector
        if direction == "up":
            dr, dc = -1, 0
        elif direction == "down":
            dr, dc = 1, 0
        elif direction == "left":
            dr, dc = 0, -1
        elif direction == "right":
            dr, dc = 0, 1
        else:
            return False, "Invalid direction"

        # Find final position and damage figures along the way
        final_pos = None
        for i in range(1, 5):  # Charge up to 4 spaces
            new_row, new_col = row + i * dr, col + i * dc
            if not self.is_valid_position((new_row, new_col)):
                break
            if self.is_terrain((new_row, new_col)):
                break

            target = self.get_figure_at((new_row, new_col))
            if target:
                if target.player != knight.player:
                    damaged_figures.append(target)
            else:
                final_pos = (new_row, new_col)

        if final_pos is None:
            return False, "No valid charge destination"

        # Move knight
        self.board[row][col] = None
        self.board[final_pos[0]][final_pos[1]] = knight
        knight.position = final_pos

        # Deal damage
        for target in damaged_figures:
            self._deal_damage(target, 2)

        knight.has_moved = True
        knight.has_acted = True

        return True, f"Charge successful, damaged {len(damaged_figures)} figures"

    def attack(self, attacker: Figure, target_pos: Tuple[int, int]):
        """Perform a basic attack."""
        if attacker.has_acted:
            return False, "Figure has already acted"

        if attacker.counter_containment_turns > 0:
            return False, "Figure is contained and cannot attack"

        target = self.get_figure_at(target_pos)
        if not target:
            return False, "No target at position"

        if target.player == attacker.player:
            return False, "Cannot attack friendly figures"

        # Check reach
        att_row, att_col = attacker.position
        tar_row, tar_col = target_pos

        if attacker.type == FigureType.ARBALIST:
            # Arbalist can attack diagonally
            distance = max(abs(tar_row - att_row), abs(tar_col - att_col))
        else:
            distance = abs(tar_row - att_row) + abs(tar_col - att_col)

        if distance > attacker.reach:
            return False, "Target out of reach"

        # Check line of sight (no blocking for basic attacks)
        if not self._is_path_clear(attacker.position, target_pos,
                                   attacker.type == FigureType.ARBALIST, check_target=False):
            return False, "No line of sight"

        # Deal damage
        damage = attacker.attack
        if attacker.type in [FigureType.BLACK_MAGE, FigureType.WHITE_MAGE] and target.type == FigureType.BARBARIAN:
            damage += 1  # Barbarian fear of occult

        self._deal_damage(target, damage)
        attacker.has_acted = True

        return True, f"Attack successful, dealt {damage} damage"

    def arbalist_long_eye(self, arbalist: Figure, direction: str):
        """Arbalist's Long Eye special action."""
        if arbalist.type != FigureType.ARBALIST:
            return False, "Only Arbalist can use Long Eye"

        if arbalist.has_acted:
            return False, "Already acted this turn"

        if arbalist.counter_containment_turns > 0:
            return False, "Arbalist is contained"

        row, col = arbalist.position

        # Direction vectors (including diagonals)
        directions = {
            "up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1),
            "up-left": (-1, -1), "up-right": (-1, 1),
            "down-left": (1, -1), "down-right": (1, 1)
        }

        if direction not in directions:
            return False, "Invalid direction"

        dr, dc = directions[direction]

        # Find first enemy in line
        for i in range(1, 8):
            new_row, new_col = row + i * dr, col + i * dc
            if not self.is_valid_position((new_row, new_col)):
                break

            target = self.get_figure_at((new_row, new_col))
            if target:
                if target.player != arbalist.player:
                    self._deal_damage(target, 1)
                    arbalist.has_acted = True
                    return True, "Long Eye hit target"
                else:
                    break  # Blocked by friendly

        return False, "No target in line"

    def black_mage_magic_bomb(self, mage: Figure, target_pos: Tuple[int, int]):
        """Black Mage's Magic Bomb spell."""
        if mage.type != FigureType.BLACK_MAGE:
            return False, "Only Black Mage can use Magic Bomb"

        if mage.has_acted:
            return False, "Already acted"

        if mage.counter_containment_turns > 0:
            return False, "Mage is contained"

        if self.magic_bomb_used[mage.player]:
            return False, "Magic Bomb already used this game"

        # Check reach
        if not self._in_reach(mage.position, target_pos, mage.reach):
            return False, "Target out of reach"

        # Get all affected positions
        affected = [target_pos]
        row, col = target_pos
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                adj_pos = (row + dr, col + dc)
                if self.is_valid_position(adj_pos):
                    affected.append(adj_pos)

        # Deal damage to all figures in affected area
        damaged = []
        for pos in affected:
            target = self.get_figure_at(pos)
            if target:
                self._deal_damage(target, 2)
                damaged.append(target)

        self.magic_bomb_used[mage.player] = True
        mage.has_acted = True

        return True, f"Magic Bomb damaged {len(damaged)} figures"

    def black_mage_plague(self, mage: Figure, target: Figure, x: int):
        """Black Mage's Plague spell."""
        if mage.type != FigureType.BLACK_MAGE:
            return False, "Only Black Mage can use Plague"

        if mage.has_acted:
            return False, "Already acted"

        if mage.counter_containment_turns > 0:
            return False, "Mage is contained"

        if x < 1 or x >= mage.life:
            return False, "Invalid X value"

        if target.player == mage.player:
            return False, "Cannot plague friendly figures"

        if not self._in_reach(mage.position, target.position, mage.reach):
            return False, "Target out of reach"

        # Mage loses X life
        self._deal_damage(mage, x)

        # Target loses X+1 life
        self._deal_damage(target, x + 1)

        mage.has_acted = True

        return True, f"Plague cast: Mage lost {x} life, target lost {x+1} life"

    def black_mage_vampiric_push(self, mage: Figure, dead_figure: Figure, pos: Tuple[int, int]):
        """Black Mage's Vampiric Push spell."""
        if mage.type != FigureType.BLACK_MAGE:
            return False, "Only Black Mage can use Vampiric Push"

        if mage.has_acted:
            return False, "Already acted"

        if mage.counter_containment_turns > 0:
            return False, "Mage is contained"

        if dead_figure not in self.dead_figures[mage.player]:
            return False, "Figure not in your dead pool"

        if pos not in self.get_start_zone(mage.player):
            return False, "Must resurrect in your start zone"

        if self.get_figure_at(pos) is not None:
            return False, "Position is occupied"

        # Mage loses 1 life
        self._deal_damage(mage, 1)

        if not mage.is_dead:  # Only resurrect if mage survives
            # Resurrect figure
            self.dead_figures[mage.player].remove(dead_figure)
            dead_figure.is_dead = False
            dead_figure.life = 2
            dead_figure.position = pos
            dead_figure.has_moved = False
            dead_figure.has_acted = False
            dead_figure.counter_containment_turns = 0
            self.board[pos[0]][pos[1]] = dead_figure
            self.figures.append(dead_figure)

            # Adjust score
            opponent = Player.TWO if mage.player == Player.ONE else Player.ONE
            self.scores[opponent] -= 1

            mage.has_acted = True
            return True, "Vampiric Push successful"

        return False, "Mage died during cast"

    def white_mage_conjure(self, mage: Figure, target: Figure):
        """White Mage's Conjure spell."""
        if mage.type != FigureType.WHITE_MAGE:
            return False, "Only White Mage can use Conjure"

        if mage.has_acted:
            return False, "Already acted"

        if mage.counter_containment_turns > 0:
            return False, "Mage is contained"

        if target.player == mage.player:
            return False, "Cannot conjure friendly figures"

        if target.life > 2:
            return False, "Target has too much life"

        if not self._in_reach(mage.position, target.position, mage.reach):
            return False, "Target out of reach"

        # Take control of target
        old_player = target.player
        target.player = mage.player

        mage.has_acted = True

        return True, f"Conjured {target.type.value}"

    def white_mage_heal(self, mage: Figure, target: Figure):
        """White Mage's Heal spell."""
        if mage.type != FigureType.WHITE_MAGE:
            return False, "Only White Mage can use Heal"

        if mage.has_acted:
            return False, "Already acted"

        if mage.counter_containment_turns > 0:
            return False, "Mage is contained"

        if not self._in_reach(mage.position, target.position, mage.reach):
            return False, "Target out of reach"

        # Heal target
        old_life = target.life
        target.life = min(target.life + 3, target.max_life)
        healed = target.life - old_life

        mage.has_acted = True

        return True, f"Healed {target.type.value} for {healed} life"

    def white_mage_counter_containment(self, mage: Figure, target: Figure):
        """White Mage's Counter Containment spell."""
        if mage.type != FigureType.WHITE_MAGE:
            return False, "Only White Mage can use Counter Containment"

        if mage.has_acted:
            return False, "Already acted"

        if mage.counter_containment_turns > 0:
            return False, "Mage is contained"

        if target.player == mage.player:
            return False, "Cannot contain friendly figures"

        if not self._in_reach(mage.position, target.position, mage.reach):
            return False, "Target out of reach"

        # Apply containment
        target.counter_containment_turns = 2

        mage.has_acted = True

        return True, f"Contained {target.type.value} for 2 turns"

    def end_turn(self):
        """End the current turn and switch players."""
        # Reset figure states
        for figure in self.figures:
            if figure.player == self.current_player:
                figure.has_moved = False
                figure.has_acted = False

        # Decrement containment counters
        for figure in self.figures:
            if figure.counter_containment_turns > 0:
                figure.counter_containment_turns -= 1

        # Switch player
        self.current_player = Player.TWO if self.current_player == Player.ONE else Player.ONE
        self.turn_count += 1

        # Check win conditions
        self._check_win_conditions()

    def _deal_damage(self, target: Figure, damage: int):
        """Deal damage to a figure."""
        target.life -= damage
        if target.life <= 0 and not target.is_dead:
            target.life = 0
            target.is_dead = True
            row, col = target.position
            self.board[row][col] = None
            self.figures.remove(target)
            self.dead_figures[target.player].append(target)

            # Award point to opponent
            opponent = Player.TWO if target.player == Player.ONE else Player.ONE
            self.scores[opponent] += 1

    def _in_reach(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], reach: int):
        """Check if a position is within reach."""
        fr, fc = from_pos
        tr, tc = to_pos
        distance = abs(tr - fr) + abs(tc - fc)
        return distance <= reach

    def _is_path_clear(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                       diagonal: bool = False, check_target: bool = True):
        """Check if path between two positions is clear."""
        fr, fc = from_pos
        tr, tc = to_pos

        if not diagonal:
            # Must be straight line
            if fr != tr and fc != tc:
                return False

        # Generate path
        steps = max(abs(tr - fr), abs(tc - fc))

        if steps == 0:
            return True

        dr = (tr - fr) / steps if steps > 0 else 0
        dc = (tc - fc) / steps if steps > 0 else 0

        for i in range(1, steps + (0 if check_target else 1)):
            r = int(fr + dr * i)
            c = int(fc + dc * i)
            if self.get_figure_at((r, c)) is not None:
                return False
            if self.is_terrain((r, c)):
                return False

        return True

    def _check_win_conditions(self):
        """Check if game is over."""
        # Check for 4 points
        for player in [Player.ONE, Player.TWO]:
            if self.scores[player] >= 4:
                self.game_over = True
                self.winner = player
                return

        # Check if a player has no figures
        player_one_figures = [f for f in self.figures if f.player == Player.ONE]
        player_two_figures = [f for f in self.figures if f.player == Player.TWO]

        if not player_one_figures:
            self.game_over = True
            self.winner = Player.TWO
        elif not player_two_figures:
            self.game_over = True
            self.winner = Player.ONE

    def display_board(self):
        """Display the current board state."""
        print("\n  0 1 2 3 4 5 6 7")
        for row in range(8):
            print(f"{row} ", end="")
            for col in range(8):
                if (row, col) in self.terrain:
                    print("XX", end="")
                else:
                    figure = self.board[row][col]
                    if figure:
                        # Display figure abbreviation with player indicator
                        abbr = {
                            FigureType.KNIGHT: "Kn",
                            FigureType.BARBARIAN: "Ba",
                            FigureType.ARBALIST: "Ar",
                            FigureType.BLACK_MAGE: "BM",
                            FigureType.WHITE_MAGE: "WM"
                        }
                        player_symbol = "1" if figure.player == Player.ONE else "2"
                        print(f"{abbr[figure.type]}{player_symbol}", end="")
                    else:
                        print("...", end="")
                print(" ", end="")
            print()

        print(f"\nScores - P1: {self.scores[Player.ONE]}, P2: {self.scores[Player.TWO]}")
        print(f"Current Player: {self.current_player.value}")
        if self.magic_bomb_used[Player.ONE]:
            print("Player 1 has used Magic Bomb")
        if self.magic_bomb_used[Player.TWO]:
            print("Player 2 has used Magic Bomb")


class Game:
    def __init__(self):
        self.state = GameState()
        self.setup_complete = False

    def setup_game(self):
        """Interactive setup for placing figures."""
        print("=== MOTLEY CREW - TACTICAL BOARD GAME ===")
        print("Game Setup - Each player places their 5 figures")
        print("Player 1 uses rows 0-1 (start zone)")
        print("Player 2 uses rows 6-7 (start zone)")
        print("Terrain: XX marks at (3,0) and (4,7)")
        print()

        # Players choose their figures
        available_types = [
            FigureType.KNIGHT,
            FigureType.BARBARIAN,
            FigureType.ARBALIST,
            FigureType.BLACK_MAGE,
            FigureType.WHITE_MAGE
        ]

        for player in [Player.ONE, Player.TWO]:
            self.current_player = player
            print(f"\nPlayer {player.value} - Place your figures in your start zone")
            for fig_type in available_types:
                figure = Figure(fig_type, player)

                while True:
                    self.state.display_board()
                    print(f"\nPlace your {fig_type.value} ({figure.max_life} HP)")
                    try:
                        row = int(input("Row (0-7): "))
                        col = int(input("Col (0-7): "))

                        if self.state.place_figure(figure, (row, col)):
                            print(f"Placed {fig_type.value} at ({row}, {col})")
                            break
                        else:
                            print("Invalid placement. Try again.")
                    except ValueError:
                        print("Invalid input. Enter numbers.")

        self.setup_complete = True
        print("\n=== Setup complete! Game begins ===")

    def play(self):
        """Main game loop."""
        if not self.setup_complete:
            self.setup_game()

        while not self.state.game_over:
            self.state.display_board()
            self.display_figures()

            print(f"\n=== Player {self.state.current_player.value}'s Turn ===")

            # Get player's figures
            player_figures = [f for f in self.state.figures
                            if f.player == self.state.current_player]

            if not player_figures:
                print("No figures to control!")
                self.state.end_turn()
                continue

            # Player actions
            while True:
                print("\nActions: move, attack, special, end")
                action = input("Choose action: ").strip().lower()

                if action == "end":
                    self.state.end_turn()
                    break
                elif action == "move":
                    self.handle_move()
                elif action == "attack":
                    self.handle_attack()
                elif action == "special":
                    self.handle_special()
                else:
                    print("Invalid action")

        # Game over
        print(f"\n=== GAME OVER ===")
        print(f"Winner: Player {self.state.winner.value}")
        print(f"Final Scores - P1: {self.state.scores[Player.ONE]}, P2: {self.state.scores[Player.TWO]}")

    def display_figures(self):
        """Display all figures and their status."""
        print("\n--- Active Figures ---")
        for player in [Player.ONE, Player.TWO]:
            print(f"Player {player.value}:")
            figures = [f for f in self.state.figures if f.player == player]
            if not figures:
                print("  No active figures")
            for fig in figures:
                status = []
                if fig.has_moved:
                    status.append("moved")
                if fig.has_acted:
                    status.append("acted")
                if fig.counter_containment_turns > 0:
                    status.append(f"contained({fig.counter_containment_turns})")
                status_str = f" [{', '.join(status)}]" if status else ""
                print(f"  {fig}{status_str} at {fig.position}")

        # Show dead figures
        for player in [Player.ONE, Player.TWO]:
            if self.state.dead_figures[player]:
                print(f"Player {player.value} dead figures:")
                for fig in self.state.dead_figures[player]:
                    print(f"  {fig.type.value}")

    def get_figure_at_position(self):
        """Helper to get a figure by position input."""
        try:
            row = int(input("Figure row (0-7): "))
            col = int(input("Figure col (0-7): "))
            figure = self.state.get_figure_at((row, col))
            if figure and figure.player == self.state.current_player:
                return figure
            else:
                print("No valid figure at that position")
                return None
        except ValueError:
            print("Invalid input")
            return None

    def handle_move(self):
        """Handle move action."""
        figure = self.get_figure_at_position()
        if not figure:
            return

        try:
            new_row = int(input("Move to row (0-7): "))
            new_col = int(input("Move to col (0-7): "))

            success, msg = self.state.move_figure(figure, (new_row, new_col))
            print(msg)
        except ValueError:
            print("Invalid input")

    def handle_attack(self):
        """Handle attack action."""
        figure = self.get_figure_at_position()
        if not figure:
            return

        try:
            target_row = int(input("Target row (0-7): "))
            target_col = int(input("Target col (0-7): "))

            success, msg = self.state.attack(figure, (target_row, target_col))
            print(msg)
        except ValueError:
            print("Invalid input")

    def handle_special(self):
        """Handle special actions based on figure type."""
        figure = self.get_figure_at_position()
        if not figure:
            return

        if figure.type == FigureType.KNIGHT:
            direction = input("Charge direction (up/down/left/right): ").strip().lower()
            success, msg = self.state.knight_charge(figure, direction)
            print(msg)

        elif figure.type == FigureType.ARBALIST:
            direction = input("Long Eye direction (up/down/left/right/up-left/up-right/down-left/down-right): ")
            success, msg = self.state.arbalist_long_eye(figure, direction)
            print(msg)

        elif figure.type == FigureType.BLACK_MAGE:
            print("Spells: 1) Magic Bomb, 2) Plague, 3) Vampiric Push")
            spell = input("Choose spell (1-3): ").strip()

            if spell == "1":
                try:
                    row = int(input("Bomb target row (0-7): "))
                    col = int(input("Bomb target col (0-7): "))
                    success, msg = self.state.black_mage_magic_bomb(figure, (row, col))
                    print(msg)
                except ValueError:
                    print("Invalid input")

            elif spell == "2":
                try:
                    row = int(input("Target row (0-7): "))
                    col = int(input("Target col (0-7): "))
                    target = self.state.get_figure_at((row, col))
                    if target:
                        x = int(input(f"Sacrifice life (1-{figure.life-1}): "))
                        success, msg = self.state.black_mage_plague(figure, target, x)
                        print(msg)
                    else:
                        print("No target at that position")
                except ValueError:
                    print("Invalid input")

            elif spell == "3":
                if not self.state.dead_figures[figure.player]:
                    print("No dead figures to resurrect")
                    return

                print("Dead figures:")
                for i, fig in enumerate(self.state.dead_figures[figure.player]):
                    print(f"{i}: {fig.type.value}")

                try:
                    fig_idx = int(input("Choose figure to resurrect: "))
                    if 0 <= fig_idx < len(self.state.dead_figures[figure.player]):
                        dead_fig = self.state.dead_figures[figure.player][fig_idx]
                        row = int(input("Resurrect at row (0-7): "))
                        col = int(input("Resurrect at col (0-7): "))
                        success, msg = self.state.black_mage_vampiric_push(figure, dead_fig, (row, col))
                        print(msg)
                    else:
                        print("Invalid figure selection")
                except ValueError:
                    print("Invalid input")

        elif figure.type == FigureType.WHITE_MAGE:
            print("Spells: 1) Conjure, 2) Heal, 3) Counter Containment")
            spell = input("Choose spell (1-3): ").strip()

            if spell == "1":
                try:
                    row = int(input("Target row (0-7): "))
                    col = int(input("Target col (0-7): "))
                    target = self.state.get_figure_at((row, col))
                    if target:
                        success, msg = self.state.white_mage_conjure(figure, target)
                        print(msg)
                    else:
                        print("No target at that position")
                except ValueError:
                    print("Invalid input")

            elif spell == "2":
                try:
                    row = int(input("Target row (0-7): "))
                    col = int(input("Target col (0-7): "))
                    target = self.state.get_figure_at((row, col))
                    if target:
                        success, msg = self.state.white_mage_heal(figure, target)
                        print(msg)
                    else:
                        print("No target at that position")
                except ValueError:
                    print("Invalid input")

            elif spell == "3":
                try:
                    row = int(input("Target row (0-7): "))
                    col = int(input("Target col (0-7): "))
                    target = self.state.get_figure_at((row, col))
                    if target:
                        success, msg = self.state.white_mage_counter_containment(figure, target)
                        print(msg)
                    else:
                        print("No target at that position")
                except ValueError:
                    print("Invalid input")

        elif figure.type == FigureType.BARBARIAN:
            print("Barbarian has no special actions, only basic attacks")

        else:
            print("No special actions available for this figure type")


def main():
    """Main function to start the game."""
    game = Game()
    try:
        game.play()
    except KeyboardInterrupt:
        print("\n\nGame interrupted. Thanks for playing!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Game terminated.")


if __name__ == "__main__":
    main()
