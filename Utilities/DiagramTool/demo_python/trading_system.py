"""
demo_python/trading_system.py
Complex Python demo for DiagramTool code analysis.
Shows: inheritance, ABC interfaces, composition, aggregation,
       dependency injection, List/Optional types.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from dataclasses import dataclass
from enum import Enum


# ── Enums ────────────────────────────────────────────────────────────────────

class OrderSide(Enum):
    BUY  = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    PENDING   = "PENDING"
    FILLED    = "FILLED"
    CANCELLED = "CANCELLED"


# ── Domain Models ─────────────────────────────────────────────────────────────

@dataclass
class Candle:
    symbol:    str
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    int
    timestamp: int


@dataclass
class Order:
    symbol:   str
    side:     OrderSide
    qty:      int
    price:    float
    status:   OrderStatus = OrderStatus.PENDING


@dataclass
class Position:
    symbol:   str
    qty:      int
    avg_cost: float

    @property
    def market_value(self) -> float:
        return self.qty * self.avg_cost


@dataclass
class Trade:
    order:  Order
    fill_price: float
    fill_qty:   int


# ── Interfaces (ABC) ──────────────────────────────────────────────────────────

class DataFeed(ABC):
    @abstractmethod
    def subscribe(self, symbol: str) -> None: ...

    @abstractmethod
    def get_latest(self, symbol: str) -> Optional[Candle]: ...


class Strategy(ABC):
    @abstractmethod
    def on_candle(self, candle: Candle) -> Optional[Order]: ...

    @abstractmethod
    def name(self) -> str: ...


class RiskManager(ABC):
    @abstractmethod
    def validate(self, order: Order, portfolio: "Portfolio") -> bool: ...


class Broker(ABC):
    @abstractmethod
    def place_order(self, order: Order) -> Trade: ...

    @abstractmethod
    def cancel_order(self, order: Order) -> bool: ...

    @abstractmethod
    def get_balance(self) -> float: ...


class Notifier(ABC):
    @abstractmethod
    def send(self, message: str) -> None: ...


# ── Data Feed Implementations ─────────────────────────────────────────────────

class NSEDataFeed(DataFeed):
    """Pulls live data from NSE."""
    _cache: Dict[str, Candle]

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache = {}

    def subscribe(self, symbol: str) -> None:
        self._cache[symbol] = None

    def get_latest(self, symbol: str) -> Optional[Candle]:
        return self._cache.get(symbol)


class YFinanceDataFeed(DataFeed):
    """Pulls historical data via yfinance."""

    def __init__(self):
        self._symbols: List[str] = []

    def subscribe(self, symbol: str) -> None:
        self._symbols.append(symbol)

    def get_latest(self, symbol: str) -> Optional[Candle]:
        return None


# ── Strategy Implementations ──────────────────────────────────────────────────

class VCPStrategy(Strategy):
    """Volatility Contraction Pattern breakout strategy."""
    candle_history: List[Candle]

    def __init__(self, lookback: int = 20, volume_threshold: float = 1.5):
        self.lookback           = lookback
        self.volume_threshold   = volume_threshold
        self.candle_history     = []

    def on_candle(self, candle: Candle) -> Optional[Order]:
        self.candle_history.append(candle)
        if len(self.candle_history) < self.lookback:
            return None
        return self._check_breakout(candle)

    def _check_breakout(self, candle: Candle) -> Optional[Order]:
        recent = self.candle_history[-self.lookback:]
        pivot  = max(c.high for c in recent[:-1])
        if candle.close > pivot and candle.volume > recent[-2].volume * self.volume_threshold:
            return Order(candle.symbol, OrderSide.BUY, 10, candle.close)
        return None

    def name(self) -> str:
        return "VCP Breakout"


class MovingAverageCrossStrategy(Strategy):
    """Simple MA crossover strategy."""
    fast_prices: List[float]
    slow_prices: List[float]

    def __init__(self, fast: int = 9, slow: int = 21):
        self.fast = fast; self.slow = slow
        self.fast_prices = []; self.slow_prices = []

    def on_candle(self, candle: Candle) -> Optional[Order]:
        self.fast_prices.append(candle.close)
        self.slow_prices.append(candle.close)
        if len(self.slow_prices) < self.slow:
            return None
        fast_ma = sum(self.fast_prices[-self.fast:]) / self.fast
        slow_ma = sum(self.slow_prices[-self.slow:]) / self.slow
        if fast_ma > slow_ma:
            return Order(candle.symbol, OrderSide.BUY, 5, candle.close)
        return None

    def name(self) -> str:
        return "MA Cross"


# ── Risk Manager ──────────────────────────────────────────────────────────────

class MaxDrawdownRiskManager(RiskManager):
    """Blocks trades if portfolio drawdown exceeds threshold."""

    def __init__(self, max_drawdown_pct: float = 0.05):
        self.max_drawdown_pct = max_drawdown_pct

    def validate(self, order: Order, portfolio: "Portfolio") -> bool:
        if portfolio.drawdown > self.max_drawdown_pct:
            return False
        if order.qty * order.price > portfolio.balance * 0.1:
            return False
        return True


# ── Broker Implementations ────────────────────────────────────────────────────

class PaperBroker(Broker):
    """Simulated broker for backtesting."""
    trades: List[Trade]

    def __init__(self, initial_balance: float = 100000.0):
        self._balance = initial_balance
        self.trades   = []

    def place_order(self, order: Order) -> Trade:
        trade = Trade(order, order.price, order.qty)
        self._balance -= order.price * order.qty
        self.trades.append(trade)
        order.status = OrderStatus.FILLED
        return trade

    def cancel_order(self, order: Order) -> bool:
        order.status = OrderStatus.CANCELLED
        return True

    def get_balance(self) -> float:
        return self._balance


class ZerodhaKiteBroker(Broker):
    """Live broker integration via Kite Connect API."""

    def __init__(self, api_key: str, access_token: str):
        self.api_key      = api_key
        self.access_token = access_token

    def place_order(self, order: Order) -> Trade:
        # Real API call would go here
        return Trade(order, order.price, order.qty)

    def cancel_order(self, order: Order) -> bool:
        return True

    def get_balance(self) -> float:
        return 0.0


# ── Notifier ──────────────────────────────────────────────────────────────────

class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id   = chat_id

    def send(self, message: str) -> None:
        print(f"[Telegram] {message}")


class ConsoleNotifier(Notifier):
    def send(self, message: str) -> None:
        print(f"[Console] {message}")


# ── Portfolio ─────────────────────────────────────────────────────────────────

class Portfolio:
    """Tracks positions, P&L and drawdown."""
    positions: List[Position]
    trades:    List[Trade]

    def __init__(self, initial_balance: float):
        self.balance          = initial_balance
        self.peak_balance     = initial_balance
        self.positions: List[Position] = []
        self.trades:    List[Trade]    = []

    @property
    def drawdown(self) -> float:
        if self.peak_balance == 0:
            return 0.0
        return (self.peak_balance - self.balance) / self.peak_balance

    def add_trade(self, trade: Trade) -> None:
        self.trades.append(trade)
        self.balance -= trade.fill_price * trade.fill_qty
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance


# ── Engine ────────────────────────────────────────────────────────────────────

class TradingEngine:
    """
    Core engine — wires together feed, strategy, risk, broker, portfolio.
    All major dependencies are injected via constructor.
    """
    strategies:  List[Strategy]
    notifiers:   List[Notifier]

    def __init__(
        self,
        feed:         DataFeed,
        broker:       Broker,
        risk_manager: RiskManager,
        portfolio:    Portfolio,
    ):
        self.feed         = feed           # injected
        self.broker       = broker         # injected
        self.risk_manager = risk_manager   # injected
        self.portfolio    = portfolio      # injected (strong composition)
        self.strategies:  List[Strategy]  = []
        self.notifiers:   List[Notifier]  = []

    def add_strategy(self, strategy: Strategy) -> None:
        self.strategies.append(strategy)

    def add_notifier(self, notifier: Notifier) -> None:
        self.notifiers.append(notifier)

    def on_candle(self, candle: Candle) -> None:
        for strategy in self.strategies:
            order = strategy.on_candle(candle)
            if order and self.risk_manager.validate(order, self.portfolio):
                trade = self.broker.place_order(order)
                self.portfolio.add_trade(trade)
                for notifier in self.notifiers:
                    notifier.send(f"Trade: {trade.fill_qty}x{candle.symbol} @ {trade.fill_price}")


# ── Backtest Runner ───────────────────────────────────────────────────────────

class BacktestRunner:
    """Runs the engine against historical candles."""

    def __init__(self, engine: TradingEngine, feed: DataFeed):
        self.engine = engine   # injected
        self.feed   = feed     # injected

    def run(self, symbols: List[str], start: str, end: str) -> Portfolio:
        for symbol in symbols:
            self.feed.subscribe(symbol)
        # Simulate candle loop
        return self.engine.portfolio


# ── Report Generator ──────────────────────────────────────────────────────────

class PerformanceReport:
    """Generates HTML/CSV reports from portfolio data."""

    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio   # injected

    def summary(self) -> Dict[str, float]:
        return {
            "balance":  self.portfolio.balance,
            "drawdown": self.portfolio.drawdown,
            "trades":   len(self.portfolio.trades),
        }

    def to_html(self, path: str) -> None:
        summary = self.summary()
        with open(path, "w") as f:
            f.write(f"<h1>Performance Report</h1><pre>{summary}</pre>")
