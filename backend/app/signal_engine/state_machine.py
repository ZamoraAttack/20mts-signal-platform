import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .buffers import TimestampedRingBuffer
from .indicators import (
    check_dia_diverging,
    check_joint_decline,
    check_reconnection,
    check_stock_lagging,
    check_synchronization,
)
from ..config import Settings

logger = logging.getLogger(__name__)


class SignalState(Enum):
    IDLE = "idle"
    MONITORING = "monitoring"           # synchronization regime confirmed
    JOINT_DECLINE = "joint_decline"     # both instruments declining together
    DIVERGENCE = "divergence"           # DIA rising, stock has not yet followed
    SIGNAL_FIRED = "signal_fired"       # reconnection confirmed — entry signal
    SIGNAL_EXPIRED = "signal_expired"   # divergence window elapsed with no reconnection
    COOLDOWN = "cooldown"               # waiting for the current decline to clear before re-arming


@dataclass
class SignalEvent:
    signal_id: str
    state: SignalState
    timestamp: datetime
    dia_price: float
    stock_price: float
    correlation: Optional[float]
    notes: str = ""
    divergence_start_time: Optional[datetime] = None
    divergence_seconds_elapsed: Optional[float] = None
    is_high_volatility: bool = False


@dataclass
class EngineStatus:
    state: SignalState
    tick_count: int
    correlation: Optional[float]
    is_synchronized: bool
    is_high_volatility: bool
    news_filter_active: bool
    dia_price: Optional[float]
    stock_price: Optional[float]
    divergence_start_time: Optional[datetime]
    active_signal_id: Optional[str]


class SignalStateMachine:
    """
    Implements the four-condition 20 MTS signal detection logic as a state machine.

    State transitions:
        IDLE → MONITORING          : correlation >= threshold
        MONITORING → JOINT_DECLINE : both instruments declining below EMA and threshold
        JOINT_DECLINE → DIVERGENCE : DIA turns up, stock still flat/down
        DIVERGENCE → SIGNAL_FIRED  : stock begins reconnecting within expiry window
        DIVERGENCE → SIGNAL_EXPIRED: 120s elapsed without reconnection
        SIGNAL_FIRED/EXPIRED → COOLDOWN   : the joint-decline conditions are still active
        SIGNAL_FIRED/EXPIRED → MONITORING : the joint-decline conditions have already cleared
        COOLDOWN → MONITORING      : joint-decline conditions clear (this decline is over —
                                      ready to detect a fresh one)
        Any active state → IDLE    : correlation drops (sync lost)
        Any active state → blocked : news filter active

    One signal per decline: after firing or expiring, the machine does not look
    for a new DIVERGENCE until the current joint-decline ("Stage 1") has fully
    ended and a fresh one begins — avoiding repeated signals on the same
    down-leg's noise.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state = SignalState.IDLE

        buffer_capacity = settings.sync_window_seconds + 120
        self.dia_buffer = TimestampedRingBuffer(buffer_capacity)
        self.stock_buffer = TimestampedRingBuffer(buffer_capacity)

        self._last_dia_price: Optional[float] = None
        self._last_stock_price: Optional[float] = None

        self._correlation: Optional[float] = None
        self._is_synchronized: bool = False

        self._divergence_start_time: Optional[datetime] = None
        self._active_signal_id: Optional[str] = None

        self._tick_count: int = 0

    def on_tick(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        news_filter_active: bool = False,
        is_high_volatility: bool = False,
    ) -> Optional[SignalEvent]:
        """
        Process a single price tick for either DIA or the stock.
        Returns a SignalEvent only at state transitions that produce actionable output:
          - DIVERGENCE (setup detected)
          - SIGNAL_FIRED (entry signal)
          - SIGNAL_EXPIRED (setup failed)
        """
        if symbol == self.settings.leader_symbol:
            self.dia_buffer.push(price, timestamp)
            self._last_dia_price = price
        else:
            self.stock_buffer.push(price, timestamp)
            self._last_stock_price = price

        self._tick_count += 1

        # Cannot evaluate until we have data for both instruments
        if self._last_dia_price is None or self._last_stock_price is None:
            return None

        # Update synchronization regime on every tick
        self._is_synchronized, self._correlation = check_synchronization(
            self.dia_buffer, self.stock_buffer, self.settings,
            currently_synchronized=self._is_synchronized,
        )

        # News filter: block all new signals, abort in-progress divergence
        if news_filter_active:
            if self.state not in (SignalState.IDLE, SignalState.MONITORING):
                self._reset(force_idle=True)
            return None

        return self._advance(
            self._last_dia_price,
            self._last_stock_price,
            timestamp,
            is_high_volatility,
        )

    def _advance(
        self,
        dia_price: float,
        stock_price: float,
        timestamp: datetime,
        is_high_volatility: bool,
    ) -> Optional[SignalEvent]:

        if self.state == SignalState.IDLE:
            if self._is_synchronized:
                self.state = SignalState.MONITORING
                logger.debug("IDLE → MONITORING  corr=%.3f", self._correlation)
            return None

        if self.state == SignalState.MONITORING:
            if not self._is_synchronized:
                self.state = SignalState.IDLE
                return None
            if check_joint_decline(self.dia_buffer, self.stock_buffer, self.settings):
                self.state = SignalState.JOINT_DECLINE
                logger.debug("MONITORING → JOINT_DECLINE")
            return None

        if self.state == SignalState.JOINT_DECLINE:
            if not self._is_synchronized:
                self.state = SignalState.IDLE
                return None

            if check_dia_diverging(self.dia_buffer, self.settings) and \
                    check_stock_lagging(self.stock_buffer, self.settings):
                self._divergence_start_time = timestamp
                self._active_signal_id = str(uuid.uuid4())
                self.state = SignalState.DIVERGENCE
                logger.info("JOINT_DECLINE → DIVERGENCE  signal=%s", self._active_signal_id)
                return SignalEvent(
                    signal_id=self._active_signal_id,
                    state=SignalState.DIVERGENCE,
                    timestamp=timestamp,
                    dia_price=dia_price,
                    stock_price=stock_price,
                    correlation=self._correlation,
                    divergence_start_time=timestamp,
                    divergence_seconds_elapsed=0.0,
                    is_high_volatility=is_high_volatility,
                    notes="Divergence detected: DIA rising, stock has not yet followed",
                )

            # Decline conditions broke without divergence — back to monitoring
            if not check_joint_decline(self.dia_buffer, self.stock_buffer, self.settings):
                self.state = SignalState.MONITORING
            return None

        if self.state == SignalState.DIVERGENCE:
            elapsed = (timestamp - self._divergence_start_time).total_seconds()  # type: ignore[operator]

            if elapsed > self.settings.divergence_expiry_seconds:
                logger.info(
                    "DIVERGENCE → SIGNAL_EXPIRED  signal=%s  elapsed=%.1fs",
                    self._active_signal_id, elapsed,
                )
                event = SignalEvent(
                    signal_id=self._active_signal_id,  # type: ignore[arg-type]
                    state=SignalState.SIGNAL_EXPIRED,
                    timestamp=timestamp,
                    dia_price=dia_price,
                    stock_price=stock_price,
                    correlation=self._correlation,
                    divergence_start_time=self._divergence_start_time,
                    divergence_seconds_elapsed=elapsed,
                    is_high_volatility=is_high_volatility,
                    notes=f"No reconnection within {elapsed:.0f}s — red herring",
                )
                self._reset()
                return event

            if check_reconnection(self.stock_buffer, self.settings):
                logger.info(
                    "DIVERGENCE → SIGNAL_FIRED  signal=%s  elapsed=%.1fs",
                    self._active_signal_id, elapsed,
                )
                event = SignalEvent(
                    signal_id=self._active_signal_id,  # type: ignore[arg-type]
                    state=SignalState.SIGNAL_FIRED,
                    timestamp=timestamp,
                    dia_price=dia_price,
                    stock_price=stock_price,
                    correlation=self._correlation,
                    divergence_start_time=self._divergence_start_time,
                    divergence_seconds_elapsed=elapsed,
                    is_high_volatility=is_high_volatility,
                    notes=f"Reconnection confirmed after {elapsed:.1f}s",
                )
                self._reset()
                return event

            return None

        if self.state == SignalState.COOLDOWN:
            if not self._is_synchronized:
                self.state = SignalState.IDLE
            elif not check_joint_decline(self.dia_buffer, self.stock_buffer, self.settings):
                self.state = SignalState.MONITORING
                logger.debug("COOLDOWN → MONITORING  decline cleared, re-armed")
            return None

        return None

    def _reset(self, force_idle: bool = False) -> None:
        self._divergence_start_time = None
        self._active_signal_id = None

        if force_idle or not self._is_synchronized:
            self.state = SignalState.IDLE
        elif check_joint_decline(self.dia_buffer, self.stock_buffer, self.settings):
            # Still in the same decline that produced this signal — wait for
            # it to clear before allowing another DIVERGENCE.
            self.state = SignalState.COOLDOWN
        else:
            self.state = SignalState.MONITORING

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def status(self) -> EngineStatus:
        return EngineStatus(
            state=self.state,
            tick_count=self._tick_count,
            correlation=self._correlation,
            is_synchronized=self._is_synchronized,
            is_high_volatility=False,
            news_filter_active=False,
            dia_price=self._last_dia_price,
            stock_price=self._last_stock_price,
            divergence_start_time=self._divergence_start_time,
            active_signal_id=self._active_signal_id,
        )
