from dataclasses import dataclass


@dataclass
class StrategyParams:
    entry_lookback: int = 20
    exit_lookback: int = 10
    atr_length: int = 14
    use_filter: bool = False
    use_ema_filter: bool = False
    ema_length: int = 200
    buffer: float = 0.0
