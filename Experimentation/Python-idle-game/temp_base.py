from __future__ import annotations

from collections.abc import Iterable
import copy
from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
import logging
import math
import numbers
from typing import TYPE_CHECKING
from typing import Callable
from typing import ClassVar
from typing import Collection
from typing import Mapping

from autofighter.character import CharacterType
from autofighter.mapgen import MapNode
from autofighter.stats import BUS
from autofighter.stats import Stats
from plugins.damage_types import random_damage_type
from plugins.damage_types._base import DamageTypeBase

# Module-level cache to avoid repeatedly loading SentenceTransformer
_EMBEDDINGS: object | None = None

log = logging.getLogger(__name__)


class SimpleConversationMemory:
    """Lightweight, dependency-free memory used as a safe default.

    Provides the minimal interface expected by PlayerBase methods without
    bringing in external dependencies that can break deepcopy/pickling.
    """

    def __init__(self) -> None:
        self._history: list[tuple[str, str]] = []

    def save_context(self, inputs: dict[str, str], outputs: dict[str, str]) -> None:
        self._history.append((inputs.get("input", ""), outputs.get("output", "")))

    def load_memory_variables(self, _: dict[str, str]) -> dict[str, str]:
        lines: list[str] = []
        for human, ai in self._history:
            if human:
                lines.append(f"Human: {human}")
            if ai:
                lines.append(f"AI: {ai}")
        return {"history": "\n".join(lines)}


if TYPE_CHECKING:
    from autofighter.passives import PassiveRegistry


@dataclass
class PlayerBase(Stats):
    plugin_type = "player"

    spawn_weight_multiplier: ClassVar[
        float | Mapping[str, float] | Callable[..., float | None] | None
    ] = None
    music_weight: ClassVar[float | Mapping[str, float] | None] = None
    music_weights: ClassVar[Mapping[str, float] | None] = None
    music_playlist_weights: ClassVar[Mapping[str, float] | None] = None

    # Override Stats defaults with PlayerBase-specific values
    hp: int = 1000
    char_type: CharacterType = CharacterType.C
    prompt: str = "Player prompt placeholder"
    about: str = "Player description placeholder"
    voice_sample: str | None = None
    voice_gender: str | None = None

    exp: int = 1
    level: int = 1
    exp_multiplier: float = 1.0
    actions_per_turn: int = 1

    damage_type: DamageTypeBase = field(default_factory=random_damage_type)

    action_points: int = 1
    damage_taken: int = 1
    damage_dealt: int = 1
    kills: int = 1

    last_damage_taken: int = 1

    passives: list[str] = field(default_factory=list)
    dots: list[str] = field(default_factory=list)
    hots: list[str] = field(default_factory=list)
    special_abilities: list[str] = field(default_factory=list)

    stat_gain_map: dict[str, str] = field(default_factory=dict)
    stat_loss_map: dict[str, str] = field(default_factory=dict)
    lrm_memory: object | None = field(default=None, init=False, repr=False)
    ui_flags: ClassVar[Iterable[str] | str | None] = None
    ui_non_selectable: ClassVar[bool] = False
    ui_portrait_pool: ClassVar[str | None] = None
    ui_metadata: ClassVar[dict[str, object] | None] = None

    @classmethod
    def get_spawn_weight(
        cls,
        *,
        node: MapNode,
        party_ids: Collection[str],
        recent_ids: Collection[str] | None = None,
        boss: bool = False,
    ) -> float:
        configured = cls._get_configured_spawn_weight_multiplier(
            node=node,
            party_ids=party_ids,
            recent_ids=recent_ids,
            boss=boss,
        )
        if configured is not None:
            return configured
        return 1.0

    @classmethod
    def _get_configured_spawn_weight_multiplier(
        cls,
        *,
        node: MapNode,
        party_ids: Collection[str],
        recent_ids: Collection[str] | None,
        boss: bool,
    ) -> float | None:
        """Resolve configured spawn multipliers without subclass overrides."""

        configs = (
            getattr(cls, "spawn_weight_multiplier", None),
            getattr(cls, "spawn_weight_multipliers", None),
        )
        for config in configs:
            if config is None:
                continue
            value = cls._normalize_spawn_weight_config(
                config,
                node=node,
                party_ids=party_ids,
                recent_ids=recent_ids,
                boss=boss,
            )
            if value is not None:
                return value
        return None

    @staticmethod
    def _normalize_spawn_weight_config(
        config: object,
        *,
        node: MapNode,
        party_ids: Collection[str],
        recent_ids: Collection[str] | None,
        boss: bool,
    ) -> float | None:
        if callable(config):
            try:
                result = config(
                    node=node,
                    party_ids=party_ids,
                    recent_ids=recent_ids,
                    boss=boss,
                )
            except Exception:
                return None
            if result is None:
                return None
            try:
                return float(result)
            except (TypeError, ValueError):
                return None

        if isinstance(config, Mapping):
            lookup_keys: list[object] = []
            if boss:
                lookup_keys.extend(("boss", True))
            else:
                lookup_keys.extend(("non_boss", False))
            lookup_keys.append("default")
            for key in lookup_keys:
                if key not in config:
                    continue
                try:
                    return float(config[key])
                except (TypeError, ValueError):
                    continue
            return None

        if isinstance(config, numbers.Real):
            return float(config)

        try:
            return float(config)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @classmethod
    def get_music_metadata(cls) -> dict[str, object]:
        """Expose normalized music weighting metadata for clients."""

        return {"weights": cls._resolve_music_weights()}

    @classmethod
    def get_ui_metadata(cls) -> dict[str, object]:
        """Return metadata that helps the WebUI decide conditional behavior."""

        metadata: dict[str, object] = {}
        explicit = getattr(cls, "ui_metadata", None)
        if isinstance(explicit, dict):
            metadata.update(explicit)

        portrait_pool = getattr(cls, "ui_portrait_pool", None)
        if portrait_pool:
            metadata.setdefault("portrait_pool", str(portrait_pool))

        flags: set[str] = set()

        configured_flags = getattr(cls, "ui_flags", None)
        if isinstance(configured_flags, str):
            flags.add(configured_flags)
        elif isinstance(configured_flags, Iterable):
            for flag in configured_flags:
                if not flag:
                    continue
                flags.add(str(flag))

        existing_flags = metadata.get("flags")
        if isinstance(existing_flags, str):
            flags.add(existing_flags)
        elif isinstance(existing_flags, Iterable):
            for flag in existing_flags:
                if not flag:
                    continue
                flags.add(str(flag))

        if metadata.get("non_selectable") is None:
            if getattr(cls, "ui_non_selectable", False):
                metadata["non_selectable"] = True
            elif getattr(cls, "gacha_rarity", None) == 0 and getattr(cls, "id", "") != "player":
                metadata["non_selectable"] = True

        if metadata.get("non_selectable"):
            flags.add("non_selectable")

        if flags:
            metadata["flags"] = sorted(flags)

        return metadata

    @classmethod
    def _resolve_music_weights(cls) -> dict[str, float]:
        """Gather playlist weighting hints with sane defaults."""

        merged: dict[str, float] = {"default": 1.0}
        configs = (
            getattr(cls, "music_playlist_weights", None),
            getattr(cls, "music_weights", None),
            getattr(cls, "music_weight", None),
        )
        for config in configs:
            normalized = cls._normalize_music_weights(config)
            if not normalized:
                continue
            merged.update(normalized)

        # Ensure encounter categories are present even when not explicitly set
        for key in ("normal", "weak", "boss"):
            if key not in merged:
                merged[key] = merged.get("default", 1.0)

        cleaned: dict[str, float] = {}
        for key, value in merged.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric) or numeric <= 0:
                continue
            cleaned[str(key).lower()] = numeric

        if "default" not in cleaned:
            cleaned["default"] = 1.0
        for key in ("normal", "weak", "boss"):
            if key not in cleaned:
                cleaned[key] = cleaned.get("default", 1.0)

        return cleaned

    @staticmethod
    def _normalize_music_weights(config: object) -> dict[str, float] | None:
        """Normalize class-level music weight configuration."""

        if config is None:
            return None

        if isinstance(config, Mapping):
            results: dict[str, float] = {}
            for key, raw in config.items():
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(value) or value <= 0:
                    continue
                results[str(key).lower()] = value
            return results or None

        if isinstance(config, numbers.Real):
            value = float(config)
        else:
            try:
                value = float(config)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        if not math.isfinite(value) or value <= 0:
            return None

        return {"default": value}

    def __post_init__(self) -> None:
        if self.voice_gender is None:
            self.voice_gender = {
                CharacterType.A: "male",
                CharacterType.B: "female",
                CharacterType.C: "neutral",
            }.get(self.char_type)

        # Initialize base stats with PlayerBase defaults
        self._base_max_hp = 1000
        self._base_atk = 100
        self._base_defense = 50
        self._base_crit_rate = 0.05
        self._base_crit_damage = 2.0
        self._base_effect_hit_rate = 1.1
        self._base_mitigation = 1.0
        self._base_regain = 1
        self._base_dodge_odds = 0.0
        self._base_effect_resistance = 1.0
        self._base_vitality = 1.0

        # Call parent post_init
        super().__post_init__()

        # Use centralized torch checker instead of individual import attempts
        from llms.torch_checker import is_torch_available

        if not is_torch_available():
            # Fall back to simple in-process memory without dependencies
            self.lrm_memory = SimpleConversationMemory()
            return

        try:
            from langchain.memory import VectorStoreRetrieverMemory
            from langchain_chroma import Chroma
            from langchain_huggingface import HuggingFaceEmbeddings
        except (ImportError, ModuleNotFoundError):
            # Fallback if imports still fail despite torch being available
            self.lrm_memory = SimpleConversationMemory()
            return

        run = getattr(self, "run_id", "run")
        ident = getattr(self, "id", type(self).__name__)
        collection = f"{run}-{ident}"
        global _EMBEDDINGS
        if _EMBEDDINGS is None:
            _EMBEDDINGS = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
            )
        embeddings = _EMBEDDINGS
        try:
            store = Chroma(
                collection_name=collection,
                embedding_function=embeddings,
            )
        except Exception:
            # If vector store init fails, use simple memory
            self.lrm_memory = SimpleConversationMemory()
            return

        self.lrm_memory = VectorStoreRetrieverMemory(
            retriever=store.as_retriever()
        )

    def __deepcopy__(self, memo):  # type: ignore[override]
        """Custom deepcopy that skips copying non-serializable memory bindings.

        - Deep-copies all dataclass fields except `lrm_memory`.
        - Replaces `lrm_memory` with a fresh SimpleConversationMemory instance.
        This avoids pydantic/langchain binding errors during deepcopy while
        ensuring lists/dicts are independently copied for battle simulation.
        """
        cls = type(self)
        result = cls.__new__(cls)  # Do not call __init__/__post_init__
        memo[id(self)] = result
        for f in fields(cls):
            name = f.name
            if name == "lrm_memory":
                setattr(result, name, SimpleConversationMemory())
                continue
            val = getattr(self, name)
            setattr(result, name, copy.deepcopy(val, memo))
        return result

    def prepare_for_battle(
        self,
        node: MapNode,
        registry: "PassiveRegistry",
    ) -> None:
        """Hook for subclasses to adjust state prior to entering battle."""

    def apply_boss_scaling(self) -> None:
        """Hook for subclasses to tweak scaled stats when treated as bosses."""

    async def use_ultimate(self) -> bool:
        """Consume charge and emit an event when firing the ultimate."""
        if not getattr(self, "ultimate_ready", False):
            return False
        self.ultimate_charge = 0
        self.ultimate_ready = False
        await BUS.emit_async("ultimate_used", self)
        return True


    async def send_lrm_message(self, message: str) -> dict[str, object]:
        import asyncio
        from pathlib import Path

        from llms.torch_checker import is_torch_available
        from tts import generate_voice

        if not is_torch_available():
            response = ""
            self.lrm_memory.save_context({"input": message}, {"output": response})
            return {"text": response, "voice": None}

        try:
            from llms.loader import load_llm
            llm = await asyncio.to_thread(load_llm)
        except Exception:
            class _LLM:
                async def generate_stream(self, text: str):
                    yield ""

            llm = _LLM()

        context = self.lrm_memory.load_memory_variables({}).get("history", "")
        prompt = f"{context}\n{message}".strip()
        chunks: list[str] = []
        async for chunk in llm.generate_stream(prompt):
            chunks.append(chunk)
        response = "".join(chunks)

        voice_path: str | None = None
        audio = await asyncio.to_thread(
            generate_voice, response, self.voice_sample
        )
        if audio:
            voices = Path("assets/voices")
            voices.mkdir(parents=True, exist_ok=True)
            fname = f"{getattr(self, 'id', type(self).__name__)}.wav"
            (voices / fname).write_bytes(audio)
            voice_path = f"/assets/voices/{fname}"

        self.lrm_memory.save_context({"input": message}, {"output": response})
        return {"text": response, "voice": voice_path}

    async def receive_lrm_message(self, message: str) -> None:
        self.lrm_memory.save_context({"input": ""}, {"output": message})
