"""
Replay (legado: `ReplayRecorder`, entities.py:4988-5029 — "W — Ver
replay" na tela de fim de jogo). O port não usa RNG global em nenhum
sistema (grep confirma: zero `random`/`np.random` em game_systems.py —
toda "aleatoriedade" é hash determinístico por contador de emissor), então
a simulação já é 100% determinística pela sequência de inputs — não é
preciso gravar/replantar uma seed como no legado, só os frames de input.

`ReplayInputProvider` implementa o mesmo contrato de `IInputProvider`
(load_bindings/poll/is_action_pressed/is_action_held/is_action_released/
wants_quit) alimentando, a cada `poll()`, o próximo bitmask gravado em vez
de ler o SO — o `World` roda os MESMOS sistemas sem saber que é replay.
"""
from __future__ import annotations

from typing import List, Tuple

# Ações lidas pelos sistemas de gameplay durante PLAYING (game_systems.py:
# SkillSystem/PlayerControlSystem/WeaponFireSystem/FuseSystem/ChakramSystem).
REPLAY_ACTIONS = ("move_up", "move_down", "move_left", "move_right",
                 "fire", "skill", "toggle_plus", "toggle_skill_plus")


def encode_frame(input_provider) -> int:
    """Bitmask do estado `is_action_held` atual (uma leitura por ação —
    permitido alocar aqui, é a camada de apresentação, não o game loop)."""
    bits = 0
    for i, action in enumerate(REPLAY_ACTIONS):
        if input_provider.is_action_held(action):
            bits |= (1 << i)
    return bits


class ReplayInputProvider:
    """`IInputProvider` sintético: cada `poll()` avança para o próximo
    frame gravado (bits, dt) em vez de consultar o SO."""

    def __init__(self, frames: List[Tuple[int, float]]) -> None:
        self._frames = frames
        self._idx = -1
        self._current = 0
        self._previous = 0

    # -- IInputProvider ---------------------------------------------------
    def load_bindings(self, bindings_path: str) -> None:
        pass

    def poll(self) -> None:
        self._previous = self._current
        self._idx += 1
        self._current = self._frames[self._idx][0] if self.has_more() else 0

    def is_action_pressed(self, action_name: str) -> bool:
        b = self._bit(action_name)
        if b < 0:
            return False
        return bool(self._current & b) and not bool(self._previous & b)

    def is_action_held(self, action_name: str) -> bool:
        b = self._bit(action_name)
        return bool(b >= 0 and self._current & b)

    def is_action_released(self, action_name: str) -> bool:
        b = self._bit(action_name)
        if b < 0:
            return False
        return bool(self._previous & b) and not bool(self._current & b)

    def wants_quit(self) -> bool:
        return False

    # -- driver do replay ---------------------------------------------------
    def has_more(self) -> bool:
        return self._idx < len(self._frames)

    def current_dt(self) -> float:
        """dt gravado para o frame que acabou de ser `poll()`ado."""
        return self._frames[self._idx][1] if self.has_more() else 1 / 60

    @staticmethod
    def _bit(action_name: str) -> int:
        try:
            return 1 << REPLAY_ACTIONS.index(action_name)
        except ValueError:
            return -1
