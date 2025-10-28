#!/usr/bin/env python3
"""
PennyHunter Paper Trading Dashboard

Beautiful GUI for monitoring and controlling the paper trading system.

Features:
- Real-time market conditions (VIX, SPY, regime)
- Live position tracking with P&L
- Trade history and performance metrics
- Memory system status (active/monitored/ejected tickers)
- Scanner controls (start/stop)
- Adjustment calculator
- Performance charts
- System logs

Usage:
    python gui_trading_dashboard.py
"""

import sys
import json
import sqlite3
import threading
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("⚠️  matplotlib not installed - charts will be disabled")
    print("   Install with: pip install matplotlib")

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

try:
    from ib_insync import IB, Stock, util
    HAS_IBKR = True
except ImportError:
    HAS_IBKR = False
    print("⚠️  ib-insync not installed - IBKR features will be disabled")
    print("   Install with: pip install ib-insync")

# Phase 2.5 Memory System
try:
    from src.bouncehunter.memory_tracker import MemoryTracker
    from src.bouncehunter.auto_ejector import AutoEjector
    HAS_MEMORY_SYSTEM = True
except ImportError:
    HAS_MEMORY_SYSTEM = False
    print("⚠️  Phase 2.5 memory system not available")
    print("   Run: python patch_v2.5_hotfix.py")

# Modern Color Palette - Enhanced
BG_DARK = "#0d1117"  # Rich dark background
BG_MEDIUM = "#161b22"  # Card background
BG_LIGHT = "#21262d"  # Elevated elements
BG_HOVER = "#30363d"  # Hover state
FG_MAIN = "#e6edf3"  # Primary text - brighter
FG_DIM = "#7d8590"  # Secondary text
FG_BRIGHT = "#ffffff"  # Emphasis text
ACCENT_BLUE = "#58a6ff"  # Vibrant blue
ACCENT_GREEN = "#3fb950"  # Success green
ACCENT_RED = "#f85149"  # Error red
ACCENT_YELLOW = "#d29922"  # Warning yellow
ACCENT_PURPLE = "#bc8cff"  # Info purple
ACCENT_CYAN = "#39c5cf"  # Data cyan
ACCENT_ORANGE = "#ff7b72"  # Alert orange
BORDER_COLOR = "#30363d"  # Subtle borders
BORDER_ACCENT = "#58a6ff"  # Active borders
GRADIENT_START = "#161b22"
GRADIENT_END = "#0d1117"

# Modern Typography
FONT_MAIN = ("SF Pro Display", 10) if sys.platform == 'darwin' else ("Segoe UI", 10)
FONT_BOLD = ("SF Pro Display", 10, "bold") if sys.platform == 'darwin' else ("Segoe UI", 10, "bold")
FONT_TITLE = ("SF Pro Display", 16, "bold") if sys.platform == 'darwin' else ("Segoe UI", 16, "bold")
FONT_HEADING = ("SF Pro Display", 13, "bold") if sys.platform == 'darwin' else ("Segoe UI", 13, "bold")
FONT_MONO = ("SF Mono", 9) if sys.platform == 'darwin' else ("Consolas", 9)
FONT_NUMBER = ("SF Mono", 11, "bold") if sys.platform == 'darwin' else ("Consolas", 11, "bold")

# Visual Effects
CORNER_RADIUS = 8  # For rounded corners effect
PADDING = 12  # Consistent spacing
SPACING = 8  # Between elements


class TradingDashboard:
    """Main GUI dashboard for paper trading system."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("PennyHunter Paper Trading Dashboard")
        self.root.geometry("1400x900")
        self.root.configure(bg=BG_DARK)
        
        # Paths
        self.project_root = Path(__file__).parent
        self.config_path = self.project_root / "configs" / "my_paper_config.yaml"
        self.db_path = self.project_root / "bouncehunter_memory.db"
        self.memory_db_path = self.project_root / "reports" / "pennyhunter_memory.db"
        self.cumulative_history_path = self.project_root / "reports" / "pennyhunter_cumulative_history.json"
        self.validation_tracker_path = self.project_root / "PHASE2_VALIDATION_TRACKER.md"
        
        # State
        self.is_running = False
        self.current_positions = []
        self.market_data = {}
        self.update_thread = None
        self.stop_update = threading.Event()
        
        # IBKR connection
        self.ib = None
        self.ibkr_connected = False
        self.scanner_process = None
        
        # Load configuration
        self.load_config()
        
        # Build UI first (so log_text exists)
        self.create_ui()
        
        # Phase 2.5 Memory System (after UI so log() works)
        self.memory_tracker = None
        self.auto_ejector = None
        if HAS_MEMORY_SYSTEM:
            try:
                self.memory_tracker = MemoryTracker(str(self.db_path))
                self.auto_ejector = AutoEjector(str(self.db_path))
                self.log("[OK] Phase 2.5 Memory System initialized")
            except Exception as e:
                self.log(f"[X] Memory system init failed: {e}")
                print(f"⚠️  Memory system init failed: {e}")
        
        # Connect to IBKR (after UI is ready)
        self.connect_ibkr()
        
        # Start updates
        self.start_updates()
        
    def load_config(self):
        """Load paper trading configuration."""
        try:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    self.config = yaml.safe_load(f)
            else:
                self.config = {}
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = {}
    
    def create_styled_panel(self, parent, title, icon=""):
        """Create a beautifully styled panel with consistent design.
        
        Args:
            parent: Parent widget
            title: Panel title
            icon: Optional emoji icon
            
        Returns:
            Tuple of (frame, content_frame) where content_frame is for adding widgets
        """
        # Outer frame with subtle border
        outer = tk.Frame(parent, bg=BORDER_COLOR, relief=tk.FLAT)
        outer.pack(fill=tk.BOTH, expand=True, pady=SPACING)
        
        # Main panel frame
        frame = tk.Frame(outer, bg=BG_MEDIUM, relief=tk.FLAT)
        frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Header with gradient effect (simulated with multiple frames)
        header = tk.Frame(frame, bg=BG_LIGHT, height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Title with icon
        title_text = f"{icon} {title}" if icon else title
        title_label = tk.Label(
            header,
            text=title_text,
            font=FONT_HEADING,
            bg=BG_LIGHT,
            fg=FG_BRIGHT,
            anchor=tk.W
        )
        title_label.pack(side=tk.LEFT, padx=PADDING, pady=10)
        
        # Content area
        content_frame = tk.Frame(frame, bg=BG_MEDIUM)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=PADDING)
        
        return frame, content_frame
    
    def create_metric_card(self, parent, label, value="--", color=FG_MAIN, icon=""):
        """Create a beautiful metric card with icon and color.
        
        Args:
            parent: Parent widget
            label: Metric label
            value: Metric value
            color: Value color
            icon: Optional emoji icon
            
        Returns:
            Tuple of (label_widget, value_widget) for updating
        """
        card = tk.Frame(parent, bg=BG_LIGHT, relief=tk.FLAT)
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # Icon and label
        label_text = f"{icon} {label}" if icon else label
        label_widget = tk.Label(
            card,
            text=label_text,
            font=FONT_MAIN,
            bg=BG_LIGHT,
            fg=FG_DIM,
            anchor=tk.W
        )
        label_widget.pack(padx=PADDING, pady=(PADDING, 2))
        
        # Value
        value_widget = tk.Label(
            card,
            text=value,
            font=FONT_NUMBER,
            bg=BG_LIGHT,
            fg=color,
            anchor=tk.W
        )
        value_widget.pack(padx=PADDING, pady=(2, PADDING))
        
        return label_widget, value_widget
    
    def format_currency(self, value):
        """Format currency with color coding."""
        if value is None or value == "--":
            return "--", FG_DIM
        
        try:
            num_value = float(value) if isinstance(value, str) else value
            color = ACCENT_GREEN if num_value >= 0 else ACCENT_RED
            prefix = "+" if num_value > 0 else ""
            return f"{prefix}${num_value:,.2f}", color
        except:
            return str(value), FG_MAIN
    
    def format_percentage(self, value):
        """Format percentage with color coding."""
        if value is None or value == "--":
            return "--", FG_DIM
        
        try:
            num_value = float(value) if isinstance(value, str) else value
            color = ACCENT_GREEN if num_value >= 0 else ACCENT_RED
            prefix = "+" if num_value > 0 else ""
            return f"{prefix}{num_value:.1f}%", color
        except:
            return str(value), FG_MAIN
    
    def connect_ibkr(self):
        """Connect to IBKR TWS/Gateway."""
        if not HAS_IBKR:
            self.log("IBKR not available - install ib-insync")
            return

        try:
            # Get connection params from config
            broker_config = self.config.get('broker', {})
            host = broker_config.get('host', '127.0.0.1')
            port = broker_config.get('port', 7497)
            client_id = broker_config.get('client_id', 43)  # Different from scanner

            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id, readonly=True, timeout=5)  # Reduced timeout
            self.ibkr_connected = True

            account = self.ib.managedAccounts()[0] if self.ib.managedAccounts() else "N/A"
            self.log(f"[OK] Connected to IBKR - Account: {account}")
            
            # Update account label
            self.account_label.config(text=f"Account: {account}")
            self.connection_label.config(text="LIVE", fg=ACCENT_GREEN)
        except Exception as e:
            self.ibkr_connected = False
            self.ib = None
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                self.log("[INFO] IBKR not running - dashboard will work in demo mode")
                self.log("       Start TWS/Gateway to enable live trading features")
                self.connection_label.config(text="DEMO", fg=ACCENT_YELLOW)
                self.account_label.config(text="Demo Mode")
            else:
                self.log(f"[X] IBKR connection failed: {e}")
                self.connection_label.config(text="ERROR", fg=ACCENT_RED)
                self.account_label.config(text="Connection Failed")
            self.log("    Make sure TWS/Gateway is running on port 7497")
    
    def create_ui(self):
        """Create the main UI layout."""
        # Main container
        main_frame = tk.Frame(self.root, bg=BG_DARK)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Top: Title bar
        self.create_title_bar(main_frame)
        
        # Middle: Main content (left + right panels)
        content_frame = tk.Frame(main_frame, bg=BG_DARK)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Left panel (2/3 width)
        left_panel = tk.Frame(content_frame, bg=BG_DARK)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Right panel (1/3 width)
        right_panel = tk.Frame(content_frame, bg=BG_DARK, width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        # Left panel content
        self.create_market_status(left_panel)
        self.create_validation_panel(left_panel)
        self.create_positions_panel(left_panel)
        self.create_trade_history_panel(left_panel)
        self.create_performance_charts_panel(left_panel)
        self.create_risk_management_panel(left_panel)
        
        # Right panel content
        self.create_controls_panel(right_panel)
        self.create_scanner_stats_panel(right_panel)
        self.create_live_signal_feed_panel(right_panel)
        self.create_memory_panel(right_panel)
        self.create_alerts_panel(right_panel)
        self.create_logs_panel(right_panel)
        
        # Bottom: Status bar
        self.create_status_bar(main_frame)
    
    def create_title_bar(self, parent):
        """Create beautiful title bar with branding and status."""
        # Gradient-style title bar (simulated with layered frames)
        title_outer = tk.Frame(parent, bg=BORDER_ACCENT, height=70)
        title_outer.pack(fill=tk.X, pady=(0, SPACING))
        title_outer.pack_propagate(False)
        
        title_frame = tk.Frame(title_outer, bg=BG_LIGHT)
        title_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Left side - Title with icon
        left_frame = tk.Frame(title_frame, bg=BG_LIGHT)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=20, pady=15)
        
        title = tk.Label(
            left_frame,
            text="🎯 ",
            font=("Segoe UI", 24),
            bg=BG_LIGHT,
            fg=ACCENT_CYAN
        )
        title.pack(side=tk.LEFT)
        
        title_text = tk.Label(
            left_frame,
            text="PennyHunter",
            font=FONT_TITLE,
            bg=BG_LIGHT,
            fg=FG_BRIGHT
        )
        title_text.pack(side=tk.LEFT, padx=(5, 0))
        
        subtitle = tk.Label(
            left_frame,
            text="Paper Trading",
            font=FONT_MAIN,
            bg=BG_LIGHT,
            fg=FG_DIM
        )
        subtitle.pack(side=tk.LEFT, padx=(10, 0), pady=(5, 0))
        
        # Right side - Status indicators
        right_frame = tk.Frame(title_frame, bg=BG_LIGHT)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=20, pady=15)
        
        # Connection status with animated indicator
        connection_frame = tk.Frame(right_frame, bg=BG_MEDIUM, relief=tk.FLAT)
        connection_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.connection_indicator = tk.Label(
            connection_frame,
            text="●",
            font=("Segoe UI", 16),
            bg=BG_MEDIUM,
            fg=ACCENT_GREEN
        )
        self.connection_indicator.pack(side=tk.LEFT, padx=(10, 5))
        
        self.connection_label = tk.Label(
            connection_frame,
            text="CONNECTING...",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT
        )
        self.connection_label.pack(side=tk.LEFT, padx=(0, 10), pady=5)
        
        # Account card
        account_frame = tk.Frame(right_frame, bg=BG_MEDIUM, relief=tk.FLAT)
        account_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        account_icon = tk.Label(
            account_frame,
            text="👤",
            font=("Segoe UI", 14),
            bg=BG_MEDIUM,
            fg=ACCENT_BLUE
        )
        account_icon.pack(side=tk.LEFT, padx=(10, 5))
        
        self.account_label = tk.Label(
            account_frame,
            text="Demo Mode",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_MAIN
        )
        self.account_label.pack(side=tk.LEFT, padx=(0, 10), pady=5)
        
        # Capital card
        capital_frame = tk.Frame(right_frame, bg=BG_MEDIUM, relief=tk.FLAT)
        capital_frame.pack(side=tk.RIGHT)
        
        capital_icon = tk.Label(
            capital_frame,
            text="💰",
            font=("Segoe UI", 14),
            bg=BG_MEDIUM,
            fg=ACCENT_GREEN
        )
        capital_icon.pack(side=tk.LEFT, padx=(10, 5))
        
        self.capital_label = tk.Label(
            capital_frame,
            text="$200.00",
            font=FONT_NUMBER,
            bg=BG_MEDIUM,
            fg=ACCENT_GREEN
        )
        self.capital_label.pack(side=tk.LEFT, padx=(0, 10), pady=5)
        
        # Start pulsing animation for connection indicator
        self.pulse_connection_indicator()
    
    def create_validation_panel(self, parent):
        """Create Phase 2 validation tracking panel."""
        frame = tk.LabelFrame(
            parent,
            text="🎯 Phase 2 Validation (Target: 70% WR on 20 Trades)",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT,
            borderwidth=2
        )
        frame.pack(fill=tk.X, pady=(0, 5))
        
        # Progress frame
        progress_frame = tk.Frame(frame, bg=BG_MEDIUM)
        progress_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Trades progress
        trades_frame = tk.Frame(progress_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        trades_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        tk.Label(trades_frame, text="TRADES", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=2)
        self.validation_trades = tk.Label(trades_frame, text="0/20", font=("Segoe UI", 16, "bold"), bg=BG_LIGHT, fg=ACCENT_BLUE)
        self.validation_trades.pack(pady=2)
        self.validation_progress = tk.Label(trades_frame, text="0%", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.validation_progress.pack(pady=2)
        
        # Win rate
        wr_frame = tk.Frame(progress_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        wr_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Label(wr_frame, text="WIN RATE", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=2)
        self.validation_wr = tk.Label(wr_frame, text="--", font=("Segoe UI", 16, "bold"), bg=BG_LIGHT, fg=ACCENT_GREEN)
        self.validation_wr.pack(pady=2)
        self.validation_wr_status = tk.Label(wr_frame, text="Need 5 trades", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.validation_wr_status.pack(pady=2)
        
        # Signal quality
        quality_frame = tk.Frame(progress_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        quality_frame.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        tk.Label(quality_frame, text="SIGNAL QUALITY", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=2)
        self.validation_quality = tk.Label(quality_frame, text="--", font=("Segoe UI", 16, "bold"), bg=BG_LIGHT, fg=ACCENT_PURPLE)
        self.validation_quality.pack(pady=2)
        self.validation_quality_status = tk.Label(quality_frame, text="Optimal filters", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.validation_quality_status.pack(pady=2)
        
        # Configure grid
        for i in range(3):
            progress_frame.columnconfigure(i, weight=1)
    
    def create_market_status(self, parent):
        """Create market status panel with beautiful styling."""
        _, content = self.create_styled_panel(parent, "Market Conditions", "📊")
        
        # Metrics row
        metrics_frame = tk.Frame(content, bg=BG_MEDIUM)
        metrics_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # VIX Card
        _, self.vix_value = self.create_metric_card(
            metrics_frame, "VIX", "--", ACCENT_YELLOW, "�"
        )
        
        # SPY Card
        _, self.spy_value = self.create_metric_card(
            metrics_frame, "SPY", "--", ACCENT_BLUE, "📉"
        )
        
        # Regime Card with special styling
        regime_card = tk.Frame(metrics_frame, bg=BG_LIGHT, relief=tk.FLAT)
        regime_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        regime_label = tk.Label(
            regime_card,
            text="🎯 Market Regime",
            font=FONT_MAIN,
            bg=BG_LIGHT,
            fg=FG_DIM,
            anchor=tk.W
        )
        regime_label.pack(padx=PADDING, pady=(PADDING, 2))
        
        self.regime_value = tk.Label(
            regime_card,
            text="ANALYZING...",
            font=FONT_NUMBER,
            bg=BG_LIGHT,
            fg=ACCENT_PURPLE,
            anchor=tk.W
        )
        self.regime_value.pack(padx=PADDING, pady=(2, PADDING))
        
        # Trading status indicator
        status_frame = tk.Frame(content, bg=BG_LIGHT, relief=tk.FLAT, height=50)
        status_frame.pack(fill=tk.X, pady=(SPACING, 0))
        status_frame.pack_propagate(False)
        
        self.trading_status = tk.Label(
            status_frame,
            text="⏸️ Market Status: Checking...",
            font=FONT_BOLD,
            bg=BG_LIGHT,
            fg=FG_MAIN,
            anchor=tk.W
        )
        self.trading_status.pack(fill=tk.BOTH, padx=PADDING, pady=PADDING)
    
    def create_positions_panel(self, parent):
        """Create beautifully styled positions table."""
        _, content = self.create_styled_panel(parent, "Active Positions", "📈")
        
        # Summary cards at top
        summary_frame = tk.Frame(content, bg=BG_MEDIUM)
        summary_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # Position count
        _, self.position_count_label = self.create_metric_card(
            summary_frame, "Open Positions", "0", ACCENT_CYAN, "📊"
        )
        
        # Total P&L
        _, self.total_pnl_label = self.create_metric_card(
            summary_frame, "Total P&L", "$0.00", ACCENT_GREEN, "💰"
        )
        
        # Win rate
        _, self.positions_wr_label = self.create_metric_card(
            summary_frame, "Win Rate", "--", ACCENT_PURPLE, "📈"
        )
        
        # Treeview with custom style
        tree_frame = tk.Frame(content, bg=BG_LIGHT)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Style configuration for treeview
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Custom.Treeview",
                       background=BG_MEDIUM,
                       foreground=FG_MAIN,
                       rowheight=28,
                       fieldbackground=BG_MEDIUM,
                       borderwidth=0)
        style.configure("Custom.Treeview.Heading",
                       background=BG_LIGHT,
                       foreground=FG_BRIGHT,
                       relief=tk.FLAT,
                       font=FONT_BOLD)
        style.map("Custom.Treeview",
                 background=[('selected', ACCENT_BLUE)])
        
        columns = ("Symbol", "Shares", "Entry", "Current", "P&L", "P&L%", "Target", "Stop")
        self.positions_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=8,
            style="Custom.Treeview"
        )
        
        # Configure columns
        for col in columns:
            self.positions_tree.heading(col, text=col)
            width = 80 if col in ["Symbol", "Shares"] else 100
            self.positions_tree.column(col, width=width, anchor=tk.CENTER)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.positions_tree.yview)
        self.positions_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_trade_history_panel(self, parent):
        """Create beautifully styled recent trade history table."""
        _, content = self.create_styled_panel(parent, "Recent Trades (Last 10)", "📜")
        
        # Export buttons frame
        export_frame = tk.Frame(content, bg=BG_MEDIUM)
        export_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # Export buttons
        export_csv_btn = tk.Button(
            export_frame,
            text="📊 Export CSV",
            command=self.export_trades_csv,
            font=FONT_MAIN,
            bg=ACCENT_BLUE,
            fg=FG_BRIGHT,
            relief=tk.FLAT,
            padx=15,
            pady=5
        )
        export_csv_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        export_json_btn = tk.Button(
            export_frame,
            text="📄 Export JSON",
            command=self.export_trades_json,
            font=FONT_MAIN,
            bg=ACCENT_GREEN,
            fg=FG_BRIGHT,
            relief=tk.FLAT,
            padx=15,
            pady=5
        )
        export_json_btn.pack(side=tk.LEFT)
        
        # Tree frame
        tree_frame = tk.Frame(content, bg=BG_LIGHT)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for history
        columns = ("Date", "Symbol", "Gap%", "Vol", "Score", "Entry", "Exit", "P&L")
        self.history_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=6,
            style="Custom.Treeview"
        )
        
        # Configure columns
        widths = {"Date": 80, "Symbol": 60, "Gap%": 60, "Vol": 60, "Score": 50, "Entry": 70, "Exit": 70, "P&L": 80}
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=widths.get(col, 70), anchor=tk.CENTER)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_performance_charts_panel(self, parent):
        """Create performance charts panel with P&L and win rate graphs."""
        _, content = self.create_styled_panel(parent, "Performance Charts", "📊")
        
        if not HAS_MATPLOTLIB:
            # Show message if matplotlib not available
            msg = tk.Label(
                content,
                text="📊 Charts require matplotlib\n\nInstall with: pip install matplotlib",
                font=FONT_MAIN,
                bg=BG_MEDIUM,
                fg=FG_DIM,
                justify=tk.CENTER
            )
            msg.pack(expand=True)
            return
        
        # Chart container
        chart_frame = tk.Frame(content, bg=BG_MEDIUM)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=PADDING)
        
        # P&L Chart
        pnl_frame = tk.Frame(chart_frame, bg=BG_LIGHT, relief=tk.FLAT)
        pnl_frame.pack(fill=tk.BOTH, expand=True, pady=(0, SPACING))
        
        pnl_title = tk.Label(
            pnl_frame,
            text="💰 Cumulative P&L Over Time",
            font=FONT_HEADING,
            bg=BG_LIGHT,
            fg=FG_BRIGHT
        )
        pnl_title.pack(pady=(PADDING, 5))
        
        self.pnl_figure = Figure(figsize=(6, 3), dpi=100, facecolor=BG_LIGHT)
        self.pnl_ax = self.pnl_figure.add_subplot(111)
        self.pnl_ax.set_facecolor(BG_MEDIUM)
        self.pnl_ax.tick_params(colors=FG_MAIN, labelsize=8)
        self.pnl_ax.spines['bottom'].set_color(FG_DIM)
        self.pnl_ax.spines['top'].set_color(FG_DIM)
        self.pnl_ax.spines['right'].set_color(FG_DIM)
        self.pnl_ax.spines['left'].set_color(FG_DIM)
        
        self.pnl_canvas = FigureCanvasTkAgg(self.pnl_figure, pnl_frame)
        self.pnl_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=(0, PADDING))
        
        # Win Rate Chart
        wr_frame = tk.Frame(chart_frame, bg=BG_LIGHT, relief=tk.FLAT)
        wr_frame.pack(fill=tk.BOTH, expand=True)
        
        wr_title = tk.Label(
            wr_frame,
            text="📈 Win Rate Trend (Rolling 10 Trades)",
            font=FONT_HEADING,
            bg=BG_LIGHT,
            fg=FG_BRIGHT
        )
        wr_title.pack(pady=(PADDING, 5))
        
        self.wr_figure = Figure(figsize=(6, 3), dpi=100, facecolor=BG_LIGHT)
        self.wr_ax = self.wr_figure.add_subplot(111)
        self.wr_ax.set_facecolor(BG_MEDIUM)
        self.wr_ax.tick_params(colors=FG_MAIN, labelsize=8)
        self.wr_ax.spines['bottom'].set_color(FG_DIM)
        self.wr_ax.spines['top'].set_color(FG_DIM)
        self.wr_ax.spines['right'].set_color(FG_DIM)
        self.wr_ax.spines['left'].set_color(FG_DIM)
        
        self.wr_canvas = FigureCanvasTkAgg(self.wr_figure, wr_frame)
        self.wr_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=(0, PADDING))
        
        # Signal Quality Trend Chart
        sq_frame = tk.Frame(chart_frame, bg=BG_LIGHT, relief=tk.FLAT)
        sq_frame.pack(fill=tk.BOTH, expand=True, pady=(0, SPACING))
        
        sq_title = tk.Label(
            sq_frame,
            text="🎯 Signal Quality Trend Over Time",
            font=FONT_HEADING,
            bg=BG_LIGHT,
            fg=FG_BRIGHT
        )
        sq_title.pack(pady=(PADDING, 5))
        
        self.sq_figure = Figure(figsize=(6, 3), dpi=100, facecolor=BG_LIGHT)
        self.sq_ax = self.sq_figure.add_subplot(111)
        self.sq_ax.set_facecolor(BG_MEDIUM)
        self.sq_ax.tick_params(colors=FG_MAIN, labelsize=8)
        self.sq_ax.spines['bottom'].set_color(FG_DIM)
        self.sq_ax.spines['top'].set_color(FG_DIM)
        self.sq_ax.spines['right'].set_color(FG_DIM)
        self.sq_ax.spines['left'].set_color(FG_DIM)
        
        self.sq_canvas = FigureCanvasTkAgg(self.sq_figure, sq_frame)
        self.sq_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=(0, PADDING))
        
        # Regime Performance Chart
        regime_frame = tk.Frame(chart_frame, bg=BG_LIGHT, relief=tk.FLAT)
        regime_frame.pack(fill=tk.BOTH, expand=True)
        
        regime_title = tk.Label(
            regime_frame,
            text="🌊 Market Regime Performance",
            font=FONT_HEADING,
            bg=BG_LIGHT,
            fg=FG_BRIGHT
        )
        regime_title.pack(pady=(PADDING, 5))
        
        self.regime_figure = Figure(figsize=(6, 3), dpi=100, facecolor=BG_LIGHT)
        self.regime_ax = self.regime_figure.add_subplot(111)
        self.regime_ax.set_facecolor(BG_MEDIUM)
        self.regime_ax.tick_params(colors=FG_MAIN, labelsize=8)
        self.regime_ax.spines['bottom'].set_color(FG_DIM)
        self.regime_ax.spines['top'].set_color(FG_DIM)
        self.regime_ax.spines['right'].set_color(FG_DIM)
        self.regime_ax.spines['left'].set_color(FG_DIM)
        
        self.regime_canvas = FigureCanvasTkAgg(self.regime_figure, regime_frame)
        self.regime_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=(0, PADDING))
        
        # Initialize charts
        self.update_performance_charts()
    
    def create_performance_panel(self, parent):
        """Create performance metrics panel."""
        frame = tk.LabelFrame(
            parent,
            text="📊 Performance",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT,
            borderwidth=2,
            height=150
        )
        frame.pack(fill=tk.X, pady=(0, 5))
        frame.pack_propagate(False)
        
        # Grid for metrics
        metrics_frame = tk.Frame(frame, bg=BG_MEDIUM)
        metrics_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Row 1
        self.create_metric(metrics_frame, "Total P&L", "$0.00", ACCENT_GREEN, 0, 0)
        self.create_metric(metrics_frame, "Win Rate", "0%", ACCENT_BLUE, 0, 1)
        self.create_metric(metrics_frame, "Total Trades", "0", ACCENT_PURPLE, 0, 2)
        
        # Row 2
        self.create_metric(metrics_frame, "Wins", "0", ACCENT_GREEN, 1, 0)
        self.create_metric(metrics_frame, "Losses", "0", ACCENT_RED, 1, 1)
        self.create_metric(metrics_frame, "Active", "0", ACCENT_YELLOW, 1, 2)
        
        # Configure grid
        for i in range(3):
            metrics_frame.columnconfigure(i, weight=1)
    
    def create_metric(self, parent, label, value, color, row, col):
        """Create a metric display box."""
        box = tk.Frame(parent, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        box.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        
        tk.Label(box, text=label, font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=(5, 0))
        metric_label = tk.Label(box, text=value, font=("Segoe UI", 14, "bold"), bg=BG_LIGHT, fg=color)
        metric_label.pack(pady=(0, 5))
        
        # Store reference - normalize label name
        attr_name = label.lower().replace(' ', '_').replace('%', '').replace('&', 'and')
        setattr(self, f"{attr_name}_label", metric_label)
    
    def create_controls_panel(self, parent):
        """Create beautifully styled control buttons panel."""
        _, content = self.create_styled_panel(parent, "Controls", "⚙️")
        
        # Start/Stop button with gradient effect
        self.start_btn = tk.Button(
            content,
            text="▶️  START SCANNER",
            command=self.toggle_scanner,
            bg=ACCENT_GREEN,
            fg=FG_BRIGHT,
            font=FONT_HEADING,
            relief=tk.FLAT,
            cursor="hand2",
            height=2,
            activebackground="#2ea043",  # Darker green on click
            activeforeground=FG_BRIGHT
        )
        self.start_btn.pack(fill=tk.X, pady=(0, SPACING))
        
        # Add hover effect
        self.start_btn.bind("<Enter>", lambda e: self.start_btn.config(bg="#3fb950"))
        self.start_btn.bind("<Leave>", lambda e: self.start_btn.config(bg=ACCENT_GREEN if not self.is_running else ACCENT_RED))
        
        # Refresh button
        refresh_btn = tk.Button(
            content,
            text="🔄  REFRESH DATA",
            command=self.refresh_data,
            bg=BG_HOVER,
            fg=ACCENT_CYAN,
            font=FONT_BOLD,
            relief=tk.FLAT,
            cursor="hand2",
            height=1,
            activebackground=ACCENT_BLUE,
            activeforeground=FG_BRIGHT
        )
        refresh_btn.pack(fill=tk.X, pady=(0, SPACING))
        refresh_btn.bind("<Enter>", lambda e: refresh_btn.config(bg=ACCENT_BLUE, fg=FG_BRIGHT))
        refresh_btn.bind("<Leave>", lambda e: refresh_btn.config(bg=BG_HOVER, fg=ACCENT_CYAN))
        
        # Settings button
        settings_btn = tk.Button(
            content,
            text="⚙️  SETTINGS",
            command=self.show_settings,
            bg=BG_HOVER,
            fg=FG_MAIN,
            font=FONT_BOLD,
            relief=tk.FLAT,
            cursor="hand2",
            height=1,
            activebackground=ACCENT_PURPLE,
            activeforeground=FG_BRIGHT
        )
        settings_btn.pack(fill=tk.X)
        settings_btn.bind("<Enter>", lambda e: settings_btn.config(bg=ACCENT_PURPLE, fg=FG_BRIGHT))
        settings_btn.bind("<Leave>", lambda e: settings_btn.config(bg=BG_HOVER, fg=FG_MAIN))
    
    def create_scanner_stats_panel(self, parent):
        """Create scanner statistics panel."""
        frame = tk.LabelFrame(
            parent,
            text="📈 Scanner Stats",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT,
            borderwidth=2
        )
        frame.pack(fill=tk.X, pady=(0, 5))
        
        stats_frame = tk.Frame(frame, bg=BG_MEDIUM)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Universe size
        universe_box = tk.Frame(stats_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        universe_box.pack(fill=tk.X, pady=2)
        tk.Label(universe_box, text="Universe", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM, anchor=tk.W).pack(side=tk.LEFT, padx=5, pady=3)
        self.universe_size = tk.Label(universe_box, text="-- tickers", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_BLUE, anchor=tk.E)
        self.universe_size.pack(side=tk.RIGHT, padx=5, pady=3)
        
        # Active tickers
        active_box = tk.Frame(stats_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        active_box.pack(fill=tk.X, pady=2)
        tk.Label(active_box, text="Active", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM, anchor=tk.W).pack(side=tk.LEFT, padx=5, pady=3)
        self.active_tickers = tk.Label(active_box, text="--", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_GREEN, anchor=tk.E)
        self.active_tickers.pack(side=tk.RIGHT, padx=5, pady=3)
        
        # Blocklisted
        blocked_box = tk.Frame(stats_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        blocked_box.pack(fill=tk.X, pady=2)
        tk.Label(blocked_box, text="Blocklisted", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM, anchor=tk.W).pack(side=tk.LEFT, padx=5, pady=3)
        self.blocklist_count = tk.Label(blocked_box, text="--", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_RED, anchor=tk.E)
        self.blocklist_count.pack(side=tk.RIGHT, padx=5, pady=3)
        
        # Signal match rate
        match_box = tk.Frame(stats_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        match_box.pack(fill=tk.X, pady=2)
        tk.Label(match_box, text="Match Rate", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM, anchor=tk.W).pack(side=tk.LEFT, padx=5, pady=3)
        self.match_rate = tk.Label(match_box, text="--", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_PURPLE, anchor=tk.E)
        self.match_rate.pack(side=tk.RIGHT, padx=5, pady=3)
    
    def create_live_signal_feed_panel(self, parent):
        """Create live signal feed panel showing real-time scanner activity."""
        _, content = self.create_styled_panel(parent, "📡 Live Signal Feed", "")
        
        # Status indicator at top
        status_frame = tk.Frame(content, bg=BG_MEDIUM)
        status_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # Scanner status
        self.scanner_status_label = tk.Label(
            status_frame,
            text="⏸️ Scanner: Stopped",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=ACCENT_RED
        )
        self.scanner_status_label.pack(side=tk.LEFT, padx=PADDING)
        
        # Last scan time
        self.last_scan_label = tk.Label(
            status_frame,
            text="Last Scan: Never",
            font=FONT_MAIN,
            bg=BG_MEDIUM,
            fg=FG_DIM
        )
        self.last_scan_label.pack(side=tk.RIGHT, padx=PADDING)
        
        # Signals found today
        signals_frame = tk.Frame(content, bg=BG_MEDIUM)
        signals_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # Today's signals summary
        self.live_signals_today_label = tk.Label(
            signals_frame,
            text="📊 Today's Signals: 0",
            font=FONT_HEADING,
            bg=BG_MEDIUM,
            fg=ACCENT_BLUE
        )
        self.live_signals_today_label.pack(anchor=tk.W, padx=PADDING, pady=(0, 5))
        
        # Signal quality breakdown
        quality_frame = tk.Frame(signals_frame, bg=BG_LIGHT, relief=tk.FLAT)
        quality_frame.pack(fill=tk.X, padx=PADDING, pady=(0, PADDING))
        
        # Quality metrics in a row
        self.live_perfect_label = tk.Label(quality_frame, text="⭐ Perfect: 0", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_GREEN)
        self.live_perfect_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.live_good_label = tk.Label(quality_frame, text="✓ Good: 0", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_BLUE)
        self.live_good_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.live_marginal_label = tk.Label(quality_frame, text="⚠ Marginal: 0", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_YELLOW)
        self.live_marginal_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.live_poor_label = tk.Label(quality_frame, text="✗ Poor: 0", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_RED)
        self.live_poor_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Export buttons for signals
        export_signals_frame = tk.Frame(signals_frame, bg=BG_MEDIUM)
        export_signals_frame.pack(fill=tk.X, padx=PADDING, pady=(5, 0))
        
        export_signals_csv_btn = tk.Button(
            export_signals_frame,
            text="📊 Export Signals CSV",
            command=self.export_signals_csv,
            font=FONT_MAIN,
            bg=ACCENT_BLUE,
            fg=FG_BRIGHT,
            relief=tk.FLAT,
            padx=10,
            pady=3
        )
        export_signals_csv_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        export_signals_json_btn = tk.Button(
            export_signals_frame,
            text="📄 Export Signals JSON",
            command=self.export_signals_json,
            font=FONT_MAIN,
            bg=ACCENT_GREEN,
            fg=FG_BRIGHT,
            relief=tk.FLAT,
            padx=10,
            pady=3
        )
        export_signals_json_btn.pack(side=tk.LEFT)
        
        # Live signals table
        table_frame = tk.Frame(content, bg=BG_LIGHT)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("Time", "Symbol", "Score", "Gap%", "Vol", "Price", "Status")
        self.live_signals_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=8,
            style="Custom.Treeview"
        )
        
        # Configure columns
        self.live_signals_tree.heading("Time", text="Time")
        self.live_signals_tree.heading("Symbol", text="Symbol")
        self.live_signals_tree.heading("Score", text="Score")
        self.live_signals_tree.heading("Gap%", text="Gap%")
        self.live_signals_tree.heading("Vol", text="Vol")
        self.live_signals_tree.heading("Price", text="Price")
        self.live_signals_tree.heading("Status", text="Status")
        
        self.live_signals_tree.column("Time", width=80, anchor=tk.CENTER)
        self.live_signals_tree.column("Symbol", width=60, anchor=tk.CENTER)
        self.live_signals_tree.column("Score", width=50, anchor=tk.CENTER)
        self.live_signals_tree.column("Gap%", width=60, anchor=tk.CENTER)
        self.live_signals_tree.column("Vol", width=50, anchor=tk.CENTER)
        self.live_signals_tree.column("Price", width=70, anchor=tk.CENTER)
        self.live_signals_tree.column("Status", width=80, anchor=tk.CENTER)
        
        # Scrollbar
        live_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.live_signals_tree.yview)
        self.live_signals_tree.configure(yscrollcommand=live_scrollbar.set)
        
        self.live_signals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        live_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure tags for color coding
        self.live_signals_tree.tag_configure("perfect", foreground=ACCENT_GREEN, background=BG_LIGHT)
        self.live_signals_tree.tag_configure("good", foreground=ACCENT_BLUE, background=BG_LIGHT)
        self.live_signals_tree.tag_configure("marginal", foreground=ACCENT_YELLOW, background=BG_LIGHT)
        self.live_signals_tree.tag_configure("poor", foreground=ACCENT_RED, background=BG_LIGHT)
        self.live_signals_tree.tag_configure("executed", background="#e6f3ff")  # Light blue background for executed
        
        # Initialize live signals storage
        self.live_signals = []
    
    def create_memory_panel(self, parent):
        """Create Phase 2.5 memory system panel with full features."""
        _, content = self.create_styled_panel(parent, "🧠 Memory System (Phase 2.5)", "")
        
        # === TODAY'S SUMMARY SECTION ===
        summary_frame = tk.LabelFrame(
            content,
            text="📅 Today's Summary",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT
        )
        summary_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        summary_grid = tk.Frame(summary_frame, bg=BG_MEDIUM)
        summary_grid.pack(fill=tk.X, padx=PADDING, pady=PADDING)
        
        # Signals found today
        signals_box = tk.Frame(summary_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        signals_box.pack(fill=tk.X, pady=2)
        tk.Label(signals_box, text="Signals Found", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM, anchor=tk.W).pack(side=tk.LEFT, padx=5, pady=3)
        self.daily_signals_label = tk.Label(signals_box, text="0", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_BLUE, anchor=tk.E)
        self.daily_signals_label.pack(side=tk.RIGHT, padx=5, pady=3)
        
        # Trades taken
        trades_box = tk.Frame(summary_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        trades_box.pack(fill=tk.X, pady=2)
        tk.Label(trades_box, text="Trades Taken", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM, anchor=tk.W).pack(side=tk.LEFT, padx=5, pady=3)
        self.daily_trades_label = tk.Label(trades_box, text="0", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_GREEN, anchor=tk.E)
        self.daily_trades_label.pack(side=tk.RIGHT, padx=5, pady=3)
        
        # Daily P&L
        pnl_box = tk.Frame(summary_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        pnl_box.pack(fill=tk.X, pady=2)
        tk.Label(pnl_box, text="Daily P&L", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM, anchor=tk.W).pack(side=tk.LEFT, padx=5, pady=3)
        self.daily_pnl_label = tk.Label(pnl_box, text="$0.00", font=FONT_MONO, bg=BG_LIGHT, fg=FG_MAIN, anchor=tk.E)
        self.daily_pnl_label.pack(side=tk.RIGHT, padx=5, pady=3)
        
        # Win streak
        streak_box = tk.Frame(summary_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        streak_box.pack(fill=tk.X, pady=2)
        tk.Label(streak_box, text="Win Streak", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM, anchor=tk.W).pack(side=tk.LEFT, padx=5, pady=3)
        self.win_streak_label = tk.Label(streak_box, text="0", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_YELLOW, anchor=tk.E)
        self.win_streak_label.pack(side=tk.RIGHT, padx=5, pady=3)
        
        # === SIGNAL QUALITY SECTION ===
        quality_frame = tk.LabelFrame(
            content,
            text="📊 Signal Quality Distribution",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT
        )
        quality_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # Quality metrics grid
        quality_grid = tk.Frame(quality_frame, bg=BG_MEDIUM)
        quality_grid.pack(fill=tk.X, padx=PADDING, pady=PADDING)
        
        # Perfect signals
        perfect_box = tk.Frame(quality_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        perfect_box.grid(row=0, column=0, padx=3, pady=3, sticky="ew")
        tk.Label(perfect_box, text="⭐ Perfect", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_GREEN).pack(pady=(3, 0))
        self.perfect_count_label = tk.Label(perfect_box, text="0", font=("Segoe UI", 12, "bold"), bg=BG_LIGHT, fg=ACCENT_GREEN)
        self.perfect_count_label.pack()
        self.perfect_wr_label = tk.Label(perfect_box, text="--% WR", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.perfect_wr_label.pack(pady=(0, 3))
        
        # Good signals
        good_box = tk.Frame(quality_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        good_box.grid(row=0, column=1, padx=3, pady=3, sticky="ew")
        tk.Label(good_box, text="✓ Good", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_BLUE).pack(pady=(3, 0))
        self.good_count_label = tk.Label(good_box, text="0", font=("Segoe UI", 12, "bold"), bg=BG_LIGHT, fg=ACCENT_BLUE)
        self.good_count_label.pack()
        self.good_wr_label = tk.Label(good_box, text="--% WR", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.good_wr_label.pack(pady=(0, 3))
        
        # Marginal signals
        marginal_box = tk.Frame(quality_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        marginal_box.grid(row=0, column=2, padx=3, pady=3, sticky="ew")
        tk.Label(marginal_box, text="⚠ Marginal", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_YELLOW).pack(pady=(3, 0))
        self.marginal_count_label = tk.Label(marginal_box, text="0", font=("Segoe UI", 12, "bold"), bg=BG_LIGHT, fg=ACCENT_YELLOW)
        self.marginal_count_label.pack()
        self.marginal_wr_label = tk.Label(marginal_box, text="--% WR", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.marginal_wr_label.pack(pady=(0, 3))
        
        # Poor signals
        poor_box = tk.Frame(quality_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        poor_box.grid(row=0, column=3, padx=3, pady=3, sticky="ew")
        tk.Label(poor_box, text="✗ Poor", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_RED).pack(pady=(3, 0))
        self.poor_count_label = tk.Label(poor_box, text="0", font=("Segoe UI", 12, "bold"), bg=BG_LIGHT, fg=ACCENT_RED)
        self.poor_count_label.pack()
        self.poor_wr_label = tk.Label(poor_box, text="--% WR", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.poor_wr_label.pack(pady=(0, 3))
        
        # Configure grid weights
        for i in range(4):
            quality_grid.columnconfigure(i, weight=1)
        
        # === TICKER PERFORMANCE SECTION ===
        perf_frame = tk.LabelFrame(
            content,
            text="🏆 Top/Bottom Performers",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT
        )
        perf_frame.pack(fill=tk.BOTH, expand=True, pady=(0, SPACING))
        
        # Performance table
        perf_table_frame = tk.Frame(perf_frame, bg=BG_LIGHT)
        perf_table_frame.pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=PADDING)
        
        columns = ("Ticker", "Trades", "WR%", "Avg Return", "Status")
        self.perf_tree = ttk.Treeview(
            perf_table_frame,
            columns=columns,
            show="headings",
            height=5,
            style="Custom.Treeview"
        )
        
        # Configure columns
        self.perf_tree.heading("Ticker", text="Ticker")
        self.perf_tree.heading("Trades", text="Trades")
        self.perf_tree.heading("WR%", text="Win Rate")
        self.perf_tree.heading("Avg Return", text="Avg Return")
        self.perf_tree.heading("Status", text="Status")
        
        self.perf_tree.column("Ticker", width=60, anchor=tk.CENTER)
        self.perf_tree.column("Trades", width=50, anchor=tk.CENTER)
        self.perf_tree.column("WR%", width=60, anchor=tk.CENTER)
        self.perf_tree.column("Avg Return", width=80, anchor=tk.CENTER)
        self.perf_tree.column("Status", width=80, anchor=tk.CENTER)
        
        self.perf_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar
        perf_scroll = ttk.Scrollbar(perf_table_frame, orient=tk.VERTICAL, command=self.perf_tree.yview)
        perf_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.perf_tree.configure(yscrollcommand=perf_scroll.set)
        
        # Configure tags for color coding
        self.perf_tree.tag_configure("winner", foreground=ACCENT_GREEN)
        self.perf_tree.tag_configure("loser", foreground=ACCENT_RED)
        self.perf_tree.tag_configure("at_risk", foreground=ACCENT_YELLOW)
        
        # === AUTO-EJECTOR CONTROLS ===
        ejector_frame = tk.LabelFrame(
            content,
            text="⚡ Auto-Ejector",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT
        )
        ejector_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # Status and controls
        ejector_top = tk.Frame(ejector_frame, bg=BG_MEDIUM)
        ejector_top.pack(fill=tk.X, padx=PADDING, pady=PADDING)
        
        # Status indicators
        status_left = tk.Frame(ejector_top, bg=BG_MEDIUM)
        status_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(status_left, text="Candidates:", font=FONT_MONO, bg=BG_MEDIUM, fg=FG_DIM).pack(side=tk.LEFT, padx=(0, 5))
        self.ejection_candidates_label = tk.Label(status_left, text="0", font=FONT_BOLD, bg=BG_MEDIUM, fg=ACCENT_YELLOW)
        self.ejection_candidates_label.pack(side=tk.LEFT, padx=(0, 15))
        
        tk.Label(status_left, text="Ejected:", font=FONT_MONO, bg=BG_MEDIUM, fg=FG_DIM).pack(side=tk.LEFT, padx=(0, 5))
        self.ejected_count_label = tk.Label(status_left, text="0", font=FONT_BOLD, bg=BG_MEDIUM, fg=ACCENT_RED)
        self.ejected_count_label.pack(side=tk.LEFT)
        
        # Control buttons
        btn_frame = tk.Frame(ejector_top, bg=BG_MEDIUM)
        btn_frame.pack(side=tk.RIGHT)
        
        self.dry_run_var = tk.BooleanVar(value=True)
        dry_run_check = tk.Checkbutton(
            btn_frame,
            text="Dry Run",
            variable=self.dry_run_var,
            font=FONT_MONO,
            bg=BG_MEDIUM,
            fg=FG_MAIN,
            selectcolor=BG_LIGHT,
            activebackground=BG_MEDIUM,
            activeforeground=ACCENT_GREEN
        )
        dry_run_check.pack(side=tk.LEFT, padx=5)
        
        self.evaluate_btn = tk.Button(
            btn_frame,
            text="🔍 Evaluate",
            command=self.run_ejection_evaluation,
            bg=ACCENT_BLUE,
            fg=FG_BRIGHT,
            font=FONT_MONO,
            relief=tk.FLAT,
            cursor="hand2",
            padx=10
        )
        self.evaluate_btn.pack(side=tk.LEFT, padx=2)
        
        # Ejection candidates list
        candidates_scroll = tk.Frame(ejector_frame, bg=BG_LIGHT)
        candidates_scroll.pack(fill=tk.X, padx=PADDING, pady=(0, PADDING))
        
        self.ejection_text = scrolledtext.ScrolledText(
            candidates_scroll,
            bg=BG_LIGHT,
            fg=FG_MAIN,
            font=FONT_MONO,
            height=4,
            wrap=tk.WORD,
            relief=tk.FLAT
        )
        self.ejection_text.pack(fill=tk.BOTH, expand=True)
        self.ejection_text.insert("1.0", "No ejection candidates. Click 'Evaluate' to check.")
        self.ejection_text.configure(state=tk.DISABLED)
        
        # === REGIME CORRELATION ===
        regime_frame = tk.LabelFrame(
            content,
            text="🌡️ Regime Correlation",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT
        )
        regime_frame.pack(fill=tk.X)
        
        regime_grid = tk.Frame(regime_frame, bg=BG_MEDIUM)
        regime_grid.pack(fill=tk.X, padx=PADDING, pady=PADDING)
        
        # Normal regime
        normal_box = tk.Frame(regime_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        normal_box.grid(row=0, column=0, padx=5, pady=3, sticky="ew")
        tk.Label(normal_box, text="🟢 RISK ON", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_GREEN).pack(pady=(3, 0))
        self.normal_regime_wr_label = tk.Label(normal_box, text="--% WR", font=("Segoe UI", 12, "bold"), bg=BG_LIGHT, fg=ACCENT_GREEN)
        self.normal_regime_wr_label.pack()
        self.normal_regime_count_label = tk.Label(normal_box, text="0 trades", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.normal_regime_count_label.pack(pady=(0, 3))
        
        # High VIX regime
        highvix_box = tk.Frame(regime_grid, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        highvix_box.grid(row=0, column=1, padx=5, pady=3, sticky="ew")
        tk.Label(highvix_box, text="🔴 HIGH VIX", font=FONT_MONO, bg=BG_LIGHT, fg=ACCENT_RED).pack(pady=(3, 0))
        self.highvix_regime_wr_label = tk.Label(highvix_box, text="--% WR", font=("Segoe UI", 12, "bold"), bg=BG_LIGHT, fg=ACCENT_RED)
        self.highvix_regime_wr_label.pack()
        self.highvix_regime_count_label = tk.Label(highvix_box, text="0 trades", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM)
        self.highvix_regime_count_label.pack(pady=(0, 3))
        
        # Configure grid
        for i in range(2):
            regime_grid.columnconfigure(i, weight=1)
    
    def create_alerts_panel(self, parent):
        """Create alerts and notifications panel."""
        _, content = self.create_styled_panel(parent, "Alerts & Notifications", "🚨")
        
        # Alert types selector
        alert_types_frame = tk.Frame(content, bg=BG_MEDIUM)
        alert_types_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # Alert type buttons
        self.alert_types = {
            'all': {'label': 'All', 'active': True},
            'positions': {'label': 'Positions', 'active': False},
            'validation': {'label': 'Validation', 'active': False},
            'system': {'label': 'System', 'active': False}
        }
        
        for alert_type, info in self.alert_types.items():
            btn = tk.Button(
                alert_types_frame,
                text=info['label'],
                command=lambda t=alert_type: self.set_alert_filter(t),
                bg=ACCENT_BLUE if info['active'] else BG_HOVER,
                fg=FG_BRIGHT if info['active'] else FG_MAIN,
                font=FONT_MONO,
                relief=tk.FLAT,
                cursor="hand2",
                padx=10
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.alert_types[alert_type]['button'] = btn
        
        # Alerts list
        alerts_frame = tk.Frame(content, bg=BG_LIGHT, relief=tk.FLAT)
        alerts_frame.pack(fill=tk.BOTH, expand=True)
        
        # Alerts treeview
        columns = ("Time", "Type", "Message")
        self.alerts_tree = ttk.Treeview(
            alerts_frame,
            columns=columns,
            show="headings",
            height=8,
            style="Custom.Treeview"
        )
        
        # Configure columns
        self.alerts_tree.heading("Time", text="Time")
        self.alerts_tree.heading("Type", text="Type")
        self.alerts_tree.heading("Message", text="Alert Message")
        
        self.alerts_tree.column("Time", width=80, anchor=tk.CENTER)
        self.alerts_tree.column("Type", width=80, anchor=tk.CENTER)
        self.alerts_tree.column("Message", width=300, anchor=tk.W)
        
        # Scrollbar
        alerts_scrollbar = ttk.Scrollbar(alerts_frame, orient=tk.VERTICAL, command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=alerts_scrollbar.set)
        
        self.alerts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        alerts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure tags for color coding
        self.alerts_tree.tag_configure("position", foreground=ACCENT_BLUE)
        self.alerts_tree.tag_configure("validation", foreground=ACCENT_GREEN)
        self.alerts_tree.tag_configure("system", foreground=ACCENT_RED)
        self.alerts_tree.tag_configure("info", foreground=ACCENT_PURPLE)
        
        # Clear alerts button
        clear_btn = tk.Button(
            content,
            text="🗑️ Clear All",
            command=self.clear_alerts,
            bg=BG_HOVER,
            fg=FG_MAIN,
            font=FONT_MONO,
            relief=tk.FLAT,
            cursor="hand2"
        )
        clear_btn.pack(pady=(SPACING, 0))
        
        # Initialize alerts storage
        self.active_alerts = []
    
    def set_alert_filter(self, alert_type):
        """Set the active alert filter."""
        # Update button states
        for t, info in self.alert_types.items():
            info['active'] = (t == alert_type)
            btn = info['button']
            if info['active']:
                btn.config(bg=ACCENT_BLUE, fg=FG_BRIGHT)
            else:
                btn.config(bg=BG_HOVER, fg=FG_MAIN)
        
        # Refresh alerts display
        self.refresh_alerts_display()
    
    def add_alert(self, alert_type, message, priority="normal"):
        """Add a new alert to the system.
        
        Args:
            alert_type: 'position', 'validation', 'system', or 'info'
            message: Alert message
            priority: 'low', 'normal', 'high'
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        alert = {
            'time': timestamp,
            'type': alert_type,
            'message': message,
            'priority': priority,
            'id': len(self.active_alerts)
        }
        
        self.active_alerts.append(alert)
        
        # Keep only last 50 alerts
        if len(self.active_alerts) > 50:
            self.active_alerts = self.active_alerts[-50:]
        
        # Log to system log
        emoji_map = {
            'position': '📈',
            'validation': '🎯',
            'system': '⚙️',
            'info': 'ℹ️'
        }
        emoji = emoji_map.get(alert_type, '🚨')
        self.log(f"{emoji} ALERT: {message}")
        
        # Refresh display
        self.refresh_alerts_display()
        
        # Show popup for high priority alerts
        if priority == "high":
            self.show_alert_popup(alert)
    
    def refresh_alerts_display(self):
        """Refresh the alerts display based on current filter."""
        # Clear existing
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)
        
        # Get active filter
        active_filter = None
        for alert_type, info in self.alert_types.items():
            if info['active']:
                active_filter = alert_type
                break
        
        # Add filtered alerts
        for alert in reversed(self.active_alerts):  # Most recent first
            if active_filter == 'all' or alert['type'] == active_filter:
                self.alerts_tree.insert("", tk.END, values=(
                    alert['time'],
                    alert['type'].title(),
                    alert['message']
                ), tags=(alert['type'],))
    
    def clear_alerts(self):
        """Clear all alerts."""
        self.active_alerts.clear()
        self.refresh_alerts_display()
        self.log("🗑️ All alerts cleared")
    
    def show_alert_popup(self, alert):
        """Show a popup notification for high-priority alerts."""
        try:
            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title("🚨 Alert Notification")
            popup.geometry("400x150")
            popup.configure(bg=BG_DARK)
            popup.attributes("-topmost", True)  # Always on top
            
            # Center on screen
            popup.transient(self.root)
            popup.grab_set()
            
            # Content
            frame = tk.Frame(popup, bg=BG_MEDIUM, relief=tk.RAISED, borderwidth=2)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Icon and title
            emoji_map = {
                'position': '📈',
                'validation': '🎯',
                'system': '⚙️',
                'info': 'ℹ️'
            }
            emoji = emoji_map.get(alert['type'], '🚨')
            
            title_label = tk.Label(
                frame,
                text=f"{emoji} {alert['type'].title()} Alert",
                font=FONT_HEADING,
                bg=BG_MEDIUM,
                fg=FG_BRIGHT
            )
            title_label.pack(pady=(10, 5))
            
            # Message
            msg_label = tk.Label(
                frame,
                text=alert['message'],
                font=FONT_MAIN,
                bg=BG_MEDIUM,
                fg=FG_MAIN,
                wraplength=350,
                justify=tk.CENTER
            )
            msg_label.pack(pady=(0, 10))
            
            # OK button
            ok_btn = tk.Button(
                frame,
                text="OK",
                command=popup.destroy,
                bg=ACCENT_BLUE,
                fg=FG_BRIGHT,
                font=FONT_BOLD,
                relief=tk.FLAT,
                cursor="hand2",
                width=10
            )
            ok_btn.pack(pady=(0, 10))
            
            # Auto-close after 10 seconds
            popup.after(10000, popup.destroy)
            
        except Exception as e:
            self.log(f"[X] Error showing alert popup: {e}")
    
    def check_for_alerts(self):
        """Check for new alerts based on current data."""
        try:
            # === POSITION ALERTS ===
            # Check for positions hitting targets/stops
            if self.ibkr_connected and self.ib:
                positions = self.ib.positions()
                for pos in positions:
                    symbol = pos.contract.symbol
                    current_price = self.get_current_price(pos.contract)
                    
                    if current_price:
                        # Mock target/stop calculation (in real system, load from position tracking)
                        entry_price = pos.avgCost
                        target_price = entry_price * 1.05  # +5%
                        stop_price = entry_price * 0.95    # -5%
                        
                        if current_price >= target_price:
                            self.add_alert('position', f"{symbol} hit target at ${current_price:.2f}", 'high')
                        elif current_price <= stop_price:
                            self.add_alert('position', f"{symbol} hit stop at ${current_price:.2f}", 'high')
            
            # === VALIDATION ALERTS ===
            # Check validation progress
            if self.cumulative_history_path.exists():
                with open(self.cumulative_history_path) as f:
                    history = json.load(f)
                
                phase2_trades = [t for t in history if 
                                 datetime.fromisoformat(t.get('entry_date', '2025-01-01')).date() >= datetime(2025, 10, 20).date()]
                completed_trades = [t for t in phase2_trades if t.get('exit_date')]
                total_trades = len(completed_trades)
                
                if total_trades >= 5:
                    wins = len([t for t in completed_trades if float(t.get('pnl', 0)) > 0])
                    win_rate = (wins / total_trades) * 100
                    
                    # Alert when reaching validation milestones
                    if total_trades == 10 and not hasattr(self, '_alerted_10_trades'):
                        self.add_alert('validation', f"Phase 2: 10 trades completed! Win rate: {win_rate:.1f}%", 'normal')
                        self._alerted_10_trades = True
                    
                    if total_trades == 20 and not hasattr(self, '_alerted_20_trades'):
                        status = "✅ PASSED" if win_rate >= 70 else "❌ FAILED"
                        self.add_alert('validation', f"Phase 2 Complete: {status} (WR: {win_rate:.1f}%)", 'high')
                        self._alerted_20_trades = True
                    
                    # Alert if win rate drops below 60% after 10+ trades
                    if total_trades >= 10 and win_rate < 60 and not hasattr(self, '_alerted_low_wr'):
                        self.add_alert('validation', f"Warning: Win rate dropped to {win_rate:.1f}%", 'normal')
                        self._alerted_low_wr = True
            
            # === SYSTEM ALERTS ===
            # Check memory system status
            if HAS_MEMORY_SYSTEM and self.memory_tracker:
                # Alert if too many tickers are ejected
                if self.memory_db_path.exists():
                    conn = sqlite3.connect(self.memory_db_path)
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT COUNT(*) FROM ticker_performance WHERE ejection_eligible = 1")
                    ejected_count = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM ticker_performance")
                    total_count = cursor.fetchone()[0]
                    
                    conn.close()
                    
                    if total_count > 0:
                        ejected_pct = (ejected_count / total_count) * 100
                        if ejected_pct > 50 and not hasattr(self, '_alerted_high_ejection'):
                            self.add_alert('system', f"High ejection rate: {ejected_pct:.1f}% of tickers removed", 'normal')
                            self._alerted_high_ejection = True
            
            # === CONNECTION ALERTS ===
            # Alert on connection issues
            if not self.ibkr_connected and HAS_IBKR and not hasattr(self, '_alerted_connection'):
                self.add_alert('system', "IBKR connection lost - dashboard in demo mode", 'normal')
                self._alerted_connection = True
            elif self.ibkr_connected and hasattr(self, '_alerted_connection'):
                self.add_alert('system', "IBKR connection restored", 'normal')
                delattr(self, '_alerted_connection')
        
        except Exception as e:
            self.log(f"[X] Error checking for alerts: {e}")
    
    def get_current_price(self, contract):
        """Get current price for a contract."""
        try:
            if self.ib and self.ib.isConnected():
                ticker = self.ib.reqMktData(contract, '', snapshot=True)
                self.ib.sleep(0.5)
                return ticker.last if ticker.last and ticker.last > 0 else ticker.close
        except:
            pass
        return None
    
    def create_risk_management_panel(self, parent):
        """Create risk management panel with position sizing and portfolio metrics."""
        _, content = self.create_styled_panel(parent, "Risk Management", "⚠️")
        
        # === PORTFOLIO RISK METRICS ===
        metrics_frame = tk.LabelFrame(
            content,
            text="📊 Portfolio Risk Metrics",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT
        )
        metrics_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        metrics_grid = tk.Frame(metrics_frame, bg=BG_MEDIUM)
        metrics_grid.pack(fill=tk.X, padx=PADDING, pady=PADDING)
        
        # Row 1: Current Risk Metrics
        self.create_risk_metric(metrics_grid, "Total Exposure", "$0.00", ACCENT_BLUE, 0, 0)
        self.create_risk_metric(metrics_grid, "Daily VaR (95%)", "$0.00", ACCENT_YELLOW, 0, 1)
        self.create_risk_metric(metrics_grid, "Max Drawdown", "0.00%", ACCENT_RED, 0, 2)
        
        # Row 2: Risk Limits
        self.create_risk_metric(metrics_grid, "Risk Limit", "$200.00", ACCENT_PURPLE, 1, 0)
        self.create_risk_metric(metrics_grid, "Utilization", "0.00%", ACCENT_CYAN, 1, 1)
        self.create_risk_metric(metrics_grid, "Risk Status", "LOW", ACCENT_GREEN, 1, 2)
        
        # Configure grid
        for i in range(3):
            metrics_grid.columnconfigure(i, weight=1)
        
        # === POSITION SIZING CALCULATOR ===
        sizing_frame = tk.LabelFrame(
            content,
            text="🧮 Position Sizing Calculator",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT
        )
        sizing_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        sizing_content = tk.Frame(sizing_frame, bg=BG_MEDIUM)
        sizing_content.pack(fill=tk.X, padx=PADDING, pady=PADDING)
        
        # Input fields
        inputs_frame = tk.Frame(sizing_content, bg=BG_MEDIUM)
        inputs_frame.pack(fill=tk.X, pady=(0, SPACING))
        
        # Account balance
        balance_frame = tk.Frame(inputs_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        balance_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        tk.Label(balance_frame, text="Account Balance ($)", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=(5, 0))
        self.balance_var = tk.StringVar(value="200.00")
        balance_entry = tk.Entry(balance_frame, textvariable=self.balance_var, font=FONT_MONO, bg=BG_LIGHT, fg=FG_BRIGHT, width=12)
        balance_entry.pack(pady=(0, 5))
        
        # Risk per trade (%)
        risk_frame = tk.Frame(inputs_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        risk_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Label(risk_frame, text="Risk per Trade (%)", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=(5, 0))
        self.risk_pct_var = tk.StringVar(value="1.0")
        risk_entry = tk.Entry(risk_frame, textvariable=self.risk_pct_var, font=FONT_MONO, bg=BG_LIGHT, fg=FG_BRIGHT, width=12)
        risk_entry.pack(pady=(0, 5))
        
        # Stop loss (%)
        stop_frame = tk.Frame(inputs_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        stop_frame.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        tk.Label(stop_frame, text="Stop Loss (%)", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=(5, 0))
        self.stop_pct_var = tk.StringVar(value="5.0")
        stop_entry = tk.Entry(stop_frame, textvariable=self.stop_pct_var, font=FONT_MONO, bg=BG_LIGHT, fg=FG_BRIGHT, width=12)
        stop_entry.pack(pady=(0, 5))
        
        # Entry price
        entry_price_frame = tk.Frame(inputs_frame, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        entry_price_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        tk.Label(entry_price_frame, text="Entry Price ($)", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=(5, 0))
        self.entry_price_var = tk.StringVar(value="10.00")
        entry_price_entry = tk.Entry(entry_price_frame, textvariable=self.entry_price_var, font=FONT_MONO, bg=BG_LIGHT, fg=FG_BRIGHT, width=12)
        entry_price_entry.pack(pady=(0, 5))
        
        # Calculate button
        calc_btn = tk.Button(
            inputs_frame,
            text="🧮 CALCULATE",
            command=self.calculate_position_size,
            bg=ACCENT_BLUE,
            fg=FG_BRIGHT,
            font=FONT_BOLD,
            relief=tk.FLAT,
            cursor="hand2"
        )
        calc_btn.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Configure grid
        for i in range(3):
            inputs_frame.columnconfigure(i, weight=1)
        
        # Results display
        results_frame = tk.Frame(sizing_content, bg=BG_LIGHT, relief=tk.FLAT)
        results_frame.pack(fill=tk.X)
        
        # Position size result
        size_result_frame = tk.Frame(results_frame, bg=BG_MEDIUM, relief=tk.RAISED, borderwidth=1)
        size_result_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(size_result_frame, text="Position Size (Shares)", font=FONT_MONO, bg=BG_MEDIUM, fg=FG_DIM).pack(side=tk.LEFT, padx=10, pady=5)
        self.position_size_result = tk.Label(size_result_frame, text="0", font=("Segoe UI", 14, "bold"), bg=BG_MEDIUM, fg=ACCENT_GREEN)
        self.position_size_result.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # Risk amount result
        risk_result_frame = tk.Frame(results_frame, bg=BG_MEDIUM, relief=tk.RAISED, borderwidth=1)
        risk_result_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(risk_result_frame, text="Risk Amount ($)", font=FONT_MONO, bg=BG_MEDIUM, fg=FG_DIM).pack(side=tk.LEFT, padx=10, pady=5)
        self.risk_amount_result = tk.Label(risk_result_frame, text="$0.00", font=("Segoe UI", 14, "bold"), bg=BG_MEDIUM, fg=ACCENT_YELLOW)
        self.risk_amount_result.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # === RISK LIMITS SETTINGS ===
        limits_frame = tk.LabelFrame(
            content,
            text="⚙️ Risk Limits",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT
        )
        limits_frame.pack(fill=tk.X)
        
        limits_content = tk.Frame(limits_frame, bg=BG_MEDIUM)
        limits_content.pack(fill=tk.X, padx=PADDING, pady=PADDING)
        
        # Daily loss limit
        daily_limit_frame = tk.Frame(limits_content, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        daily_limit_frame.pack(fill=tk.X, pady=2)
        tk.Label(daily_limit_frame, text="Daily Loss Limit ($)", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(side=tk.LEFT, padx=10, pady=5)
        self.daily_limit_var = tk.StringVar(value="20.00")
        daily_limit_entry = tk.Entry(daily_limit_frame, textvariable=self.daily_limit_var, font=FONT_MONO, bg=BG_LIGHT, fg=FG_BRIGHT, width=10)
        daily_limit_entry.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # Max position size
        max_pos_frame = tk.Frame(limits_content, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        max_pos_frame.pack(fill=tk.X, pady=2)
        tk.Label(max_pos_frame, text="Max Position Size ($)", font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(side=tk.LEFT, padx=10, pady=5)
        self.max_pos_var = tk.StringVar(value="50.00")
        max_pos_entry = tk.Entry(max_pos_frame, textvariable=self.max_pos_var, font=FONT_MONO, bg=BG_LIGHT, fg=FG_BRIGHT, width=10)
        max_pos_entry.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def create_risk_metric(self, parent, label, value, color, row, col):
        """Create a risk metric display box."""
        box = tk.Frame(parent, bg=BG_LIGHT, relief=tk.RAISED, borderwidth=1)
        box.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        
        tk.Label(box, text=label, font=FONT_MONO, bg=BG_LIGHT, fg=FG_DIM).pack(pady=(5, 0))
        metric_label = tk.Label(box, text=value, font=("Segoe UI", 12, "bold"), bg=BG_LIGHT, fg=color)
        metric_label.pack(pady=(0, 5))
        
        # Store reference
        attr_name = label.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('%', 'pct')
        setattr(self, f"{attr_name}_label", metric_label)
    
    def calculate_position_size(self):
        """Calculate position size based on risk parameters."""
        try:
            # Get inputs
            balance = float(self.balance_var.get())
            risk_pct = float(self.risk_pct_var.get()) / 100  # Convert to decimal
            stop_pct = float(self.stop_pct_var.get()) / 100  # Convert to decimal
            entry_price = float(self.entry_price_var.get())
            
            # Calculate risk amount per trade
            risk_amount = balance * risk_pct
            
            # Calculate position size
            # Risk = Position Size * Entry Price * Stop Loss %
            # Position Size = Risk / (Entry Price * Stop Loss %)
            position_size = risk_amount / (entry_price * stop_pct)
            
            # Round down to whole shares
            position_size = int(position_size)
            
            # Check against max position size
            max_pos_value = float(self.max_pos_var.get())
            max_position_size = max_pos_value / entry_price
            
            if position_size > max_position_size:
                position_size = int(max_position_size)
                risk_amount = position_size * entry_price * stop_pct
            
            # Update results
            self.position_size_result.config(text=f"{position_size:,}")
            self.risk_amount_result.config(text=f"${risk_amount:.2f}")
            
            # Log calculation
            self.log(f"🧮 Position sizing: {position_size} shares, risk ${risk_amount:.2f}")
            
        except ValueError as e:
            self.log(f"[X] Invalid input for position sizing: {e}")
            self.position_size_result.config(text="ERROR")
            self.risk_amount_result.config(text="ERROR")
        except Exception as e:
            self.log(f"[X] Error calculating position size: {e}")
            self.position_size_result.config(text="ERROR")
            self.risk_amount_result.config(text="ERROR")
    
    def update_risk_metrics(self):
        """Update portfolio risk metrics."""
        try:
            # Calculate total exposure
            total_exposure = 0.0
            if self.ibkr_connected and self.ib:
                positions = self.ib.positions()
                for pos in positions:
                    current_price = self.get_current_price(pos.contract) or pos.avgCost
                    exposure = abs(pos.position) * current_price
                    total_exposure += exposure
            
            self.total_exposure_label.config(text=f"${total_exposure:.2f}")
            
            # Calculate daily VaR (simplified - using historical volatility proxy)
            # In a real system, this would use proper VaR calculation
            if total_exposure > 0:
                # Assume 2% daily volatility for demo
                daily_var = total_exposure * 0.02
                self.daily_var_95pct_label.config(text=f"${daily_var:.2f}")
            else:
                self.daily_var_95pct_label.config(text="$0.00")
            
            # Calculate max drawdown from trade history
            max_drawdown = 0.0
            if self.cumulative_history_path.exists():
                with open(self.cumulative_history_path) as f:
                    history = json.load(f)
                
                completed_trades = [t for t in history if t.get('exit_date')]
                if completed_trades:
                    # Calculate cumulative P&L
                    cumulative = []
                    running_total = 0
                    peak = 0
                    
                    for trade in sorted(completed_trades, key=lambda x: x.get('exit_date')):
                        pnl = float(trade.get('pnl', 0))
                        running_total += pnl
                        cumulative.append(running_total)
                        
                        if running_total > peak:
                            peak = running_total
                        
                        drawdown = peak - running_total
                        if drawdown > max_drawdown:
                            max_drawdown = drawdown
                    
                    if peak > 0:
                        max_drawdown_pct = (max_drawdown / peak) * 100
                        self.max_drawdown_label.config(text=f"{max_drawdown_pct:.2f}%")
                    else:
                        self.max_drawdown_label.config(text="0.00%")
            
            # Update risk utilization
            risk_limit = float(self.daily_limit_var.get())
            if risk_limit > 0:
                utilization = (max_drawdown / risk_limit) * 100
                self.utilization_label.config(text=f"{utilization:.1f}%")
                
                # Update risk status
                if utilization < 25:
                    status = "LOW"
                    color = ACCENT_GREEN
                elif utilization < 50:
                    status = "MODERATE"
                    color = ACCENT_YELLOW
                elif utilization < 75:
                    status = "HIGH"
                    color = ACCENT_ORANGE
                else:
                    status = "CRITICAL"
                    color = ACCENT_RED
                
                self.risk_status_label.config(text=status, fg=color)
            
            # Update risk limit display
            self.risk_limit_label.config(text=f"${risk_limit:.2f}")
            
        except Exception as e:
            self.log(f"[X] Error updating risk metrics: {e}")
    
    def create_logs_panel(self, parent):
        """Create system logs panel."""
        frame = tk.LabelFrame(
            parent,
            text="📝 System Logs",
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_BRIGHT,
            relief=tk.FLAT,
            borderwidth=2,
            height=200
        )
        frame.pack(fill=tk.X)
        frame.pack_propagate(False)
        
        self.log_text = scrolledtext.ScrolledText(
            frame,
            bg=BG_LIGHT,
            fg=FG_MAIN,
            font=FONT_MONO,
            height=10,
            wrap=tk.WORD,
            relief=tk.FLAT
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def create_status_bar(self, parent):
        """Create bottom status bar."""
        status_frame = tk.Frame(parent, bg=BG_MEDIUM, height=30)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_frame,
            text="● Ready",
            font=FONT_MONO,
            bg=BG_MEDIUM,
            fg=ACCENT_GREEN,
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.time_label = tk.Label(
            status_frame,
            text="",
            font=FONT_MONO,
            bg=BG_MEDIUM,
            fg=FG_DIM,
            anchor=tk.E
        )
        self.time_label.pack(side=tk.RIGHT, padx=10)
        
        # Update time
        self.update_time()
    
    def update_time(self):
        """Update time label."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=now)
        self.root.after(1000, self.update_time)
    
    def toggle_scanner(self):
        """Toggle scanner on/off."""
        if self.is_running:
            self.stop_scanner()
        else:
            self.start_scanner()
    
    def start_scanner(self):
        """Start the paper trading scanner as subprocess."""
        if self.scanner_process and self.scanner_process.poll() is None:
            self.log("[NOTE] Scanner already running")
            return
        
        try:
            # Path to scanner script
            scanner_path = self.project_root / "run_pennyhunter_paper.py"
            
            if not scanner_path.exists():
                self.log(f"[X] Scanner script not found: {scanner_path}")
                messagebox.showerror("Error", f"Scanner script not found:\n{scanner_path}")
                return
            
            # Start as subprocess
            self.scanner_process = subprocess.Popen(
                [sys.executable, str(scanner_path)],
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            self.is_running = True
            self.start_btn.config(text="⏸️ STOP SCANNER", bg=ACCENT_RED)
            self.log("[OK] Scanner started (PID: {})".format(self.scanner_process.pid))
            self.status_label.config(text="● Running", fg=ACCENT_GREEN)
            
            # Start thread to capture output
            threading.Thread(target=self.capture_scanner_output, daemon=True).start()
            
        except Exception as e:
            self.log(f"[X] Failed to start scanner: {e}")
            messagebox.showerror("Scanner Error", f"Failed to start scanner:\n{e}")
    
    def stop_scanner(self):
        """Stop the paper trading scanner."""
        if not self.scanner_process or self.scanner_process.poll() is not None:
            self.log("[NOTE] Scanner not running")
            self.is_running = False
            self.start_btn.config(text="▶️ START SCANNER", bg=ACCENT_GREEN)
            self.status_label.config(text="● Ready", fg=ACCENT_YELLOW)
            return
        
        try:
            self.log("[NOTE] Stopping scanner...")
            self.scanner_process.terminate()
            
            # Wait up to 5 seconds for graceful shutdown
            try:
                self.scanner_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log("[NOTE] Force killing scanner...")
                self.scanner_process.kill()
                self.scanner_process.wait()
            
            self.is_running = False
            self.start_btn.config(text="▶️ START SCANNER", bg=ACCENT_GREEN)
            self.log("[OK] Scanner stopped")
            self.status_label.config(text="● Ready", fg=ACCENT_YELLOW)
            
        except Exception as e:
            self.log(f"[X] Error stopping scanner: {e}")
    
    def capture_scanner_output(self):
        """Capture scanner subprocess output and log it.""" 
        try:
            for line in iter(self.scanner_process.stdout.readline, ''):
                if line:
                    # Clean and log
                    clean_line = line.strip()
                    if clean_line:
                        self.root.after(0, lambda l=clean_line: self.log(f"[SCANNER] {l}"))
                
                # Check if process ended
                if self.scanner_process.poll() is not None:
                    break
            
            # Process ended - trigger automatic refresh
            exit_code = self.scanner_process.poll()
            self.root.after(0, lambda: self.log(f"[NOTE] Scanner exited (code: {exit_code})"))
            
            # Automatically refresh dashboard data after scanner completes
            self.root.after(0, lambda: self.log("[INFO] Scanner completed - refreshing dashboard data..."))
            self.root.after(1000, self.refresh_data)  # Small delay to ensure files are written
            
            self.root.after(0, lambda: self.stop_scanner())
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"[X] Error capturing output: {e}"))
    
    def refresh_data(self):
        """Refresh all data displays."""
        self.log("Refreshing data...")
        self.update_validation_metrics()
        self.update_market_data()
        self.update_positions()
        self.update_performance()
        self.update_trade_history()
        self.update_scanner_stats()
        self.update_memory_status()
        self.update_performance_charts()
        self.update_risk_metrics()
        self.check_for_alerts()
        self.log("Data refreshed ✓")
    
    def update_market_data(self):
        """Update market status display with beautiful formatting."""
        try:
            if HAS_YFINANCE:
                # Fetch VIX
                vix = yf.Ticker("^VIX")
                vix_data = vix.history(period="1d")
                if not vix_data.empty:
                    vix_value = vix_data['Close'].iloc[-1]
                    self.vix_value.config(text=f"{vix_value:.2f}")
                    
                    # Determine VIX regime with beautiful color coding
                    if vix_value < 15:
                        regime = "LOW - Calm"
                        vix_color = ACCENT_GREEN
                    elif vix_value < 25:
                        regime = "NORMAL"
                        vix_color = ACCENT_CYAN
                    elif vix_value < 35:
                        regime = "ELEVATED"
                        vix_color = ACCENT_YELLOW
                    else:
                        regime = "HIGH - Fear"
                        vix_color = ACCENT_RED
                    
                    self.vix_value.config(fg=vix_color)
                
                # Fetch SPY
                spy = yf.Ticker("SPY")
                spy_data = spy.history(period="2d")
                if len(spy_data) >= 2:
                    spy_current = spy_data['Close'].iloc[-1]
                    spy_prev = spy_data['Close'].iloc[-2]
                    spy_change = ((spy_current - spy_prev) / spy_prev) * 100
                    
                    self.spy_value.config(text=f"${spy_current:.2f}")
                    spy_color = ACCENT_GREEN if spy_change >= 0 else ACCENT_RED
                    self.spy_value.config(fg=spy_color)
                
                # Update market regime with emoji
                if vix_value < 20 and spy_change > 0:
                    regime_text = "🟢 RISK ON"
                    regime_color = ACCENT_GREEN
                    status_text = "✓ Trading Enabled"
                elif vix_value > 30 or spy_change < -2:
                    regime_text = "🔴 RISK OFF"
                    regime_color = ACCENT_RED
                    status_text = "⚠ Caution Advised"
                else:
                    regime_text = "🟡 NEUTRAL"
                    regime_color = ACCENT_YELLOW
                    status_text = "⏸ Selective Trading"
                
                self.regime_value.config(text=regime_text, fg=regime_color)
                self.trading_status.config(text=status_text, fg=regime_color)
            
        except Exception as e:
            self.log(f"❌ Error updating market data: {e}")
    
    def update_positions(self):
        """Update positions table with live IBKR data."""
        # Clear existing
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)

        if not self.ibkr_connected or not self.ib:
            self.positions_tree.insert("", tk.END, values=("IBKR not connected - Demo Mode", "", "", "", "", "", "", ""))
            # Update summary with demo data
            self.position_count_label.config(text="0")
            self.total_pnl_label.config(text="$0.00", fg=FG_DIM)
            return

        try:
            # Get positions from IBKR
            positions = self.ib.positions()

            if not positions:
                self.positions_tree.insert("", tk.END, values=("No active positions", "", "", "", "", "", "", ""))
                self.position_count_label.config(text="0")
                self.total_pnl_label.config(text="$0.00", fg=FG_DIM)
                return

            total_pnl = 0.0
            position_count = 0

            for pos in positions:
                # Get current market data
                contract = pos.contract

                try:
                    # Request market data snapshot
                    ticker = self.ib.reqMktData(contract, '', snapshot=True)
                    self.ib.sleep(0.5)  # Brief wait for data

                    # Calculate values
                    symbol = contract.symbol
                    shares = int(pos.position)
                    avg_cost = pos.avgCost

                    # Get current price (use last or close)
                    current_price = ticker.last if ticker.last and ticker.last > 0 else (ticker.close if ticker.close else avg_cost)

                    # Calculate P&L
                    pnl = (current_price - avg_cost) * shares
                    pnl_pct = ((current_price - avg_cost) / avg_cost) * 100 if avg_cost > 0 else 0

                    # Mock targets/stops (TODO: load from position tracking)
                    target = current_price * 1.05  # +5%
                    stop = current_price * 0.95    # -5%

                    # Add to tree
                    pnl_color = "green" if pnl >= 0 else "red"
                    self.positions_tree.insert("", tk.END, values=(
                        symbol,
                        shares,
                        f"${avg_cost:.2f}",
                        f"${current_price:.2f}",
                        f"${pnl:.2f}",
                        f"{pnl_pct:+.2f}%",
                        f"${target:.2f}",
                        f"${stop:.2f}"
                    ), tags=(pnl_color,))

                    total_pnl += pnl
                    position_count += 1

                    # Cancel market data subscription
                    self.ib.cancelMktData(contract)

                except Exception as e:
                    # Handle market data subscription errors
                    error_msg = str(e).lower()
                    if "subscription" in error_msg or "market data" in error_msg:
                        # No market data subscription - show position with N/A prices
                        symbol = contract.symbol
                        shares = int(pos.position)
                        avg_cost = pos.avgCost

                        self.positions_tree.insert("", tk.END, values=(
                            symbol,
                            shares,
                            f"${avg_cost:.2f}",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A"
                        ), tags=("grey",))

                        position_count += 1
                        self.log(f"[INFO] No market data for {symbol} - subscription required")
                    else:
                        self.log(f"[X] Error getting data for {contract.symbol}: {e}")

            # Update performance metrics
            self.total_pnl_label.config(text=f"${total_pnl:.2f}")
            self.total_pnl_label.config(fg=ACCENT_GREEN if total_pnl >= 0 else ACCENT_RED)
            self.position_count_label.config(text=str(position_count))

            # Configure tag colors
            self.positions_tree.tag_configure("green", foreground=ACCENT_GREEN)
            self.positions_tree.tag_configure("red", foreground=ACCENT_RED)
            self.positions_tree.tag_configure("grey", foreground=FG_DIM)

        except Exception as e:
            self.log(f"[X] Error updating positions: {e}")
            self.positions_tree.insert("", tk.END, values=(f"Error: {e}", "", "", "", "", "", "", ""))
    
    def update_performance(self):
        """Update performance metrics from database."""
        try:
            if self.db_path.exists():
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Check if position_exits table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='position_exits'")
                if not cursor.fetchone():
                    # No trades yet
                    self.total_pnl_label.config(text="$0.00")
                    self.win_rate_label.config(text="0%")
                    self.total_trades_label.config(text="0")
                    self.wins_label.config(text="0")
                    self.losses_label.config(text="0")
                    conn.close()
                    return
                
                # Get total P&L
                cursor.execute("SELECT SUM(pnl) FROM position_exits")
                total_pnl = cursor.fetchone()[0] or 0.0
                
                # Get win/loss stats
                cursor.execute("SELECT COUNT(*) FROM position_exits WHERE pnl > 0")
                wins = cursor.fetchone()[0] or 0
                
                cursor.execute("SELECT COUNT(*) FROM position_exits WHERE pnl <= 0")
                losses = cursor.fetchone()[0] or 0
                
                total_trades = wins + losses
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
                
                # Update labels
                self.total_pnl_label.config(text=f"${total_pnl:.2f}")
                self.total_pnl_label.config(fg=ACCENT_GREEN if total_pnl >= 0 else ACCENT_RED)
                self.win_rate_label.config(text=f"{win_rate:.1f}%")
                self.total_trades_label.config(text=str(total_trades))
                self.wins_label.config(text=str(wins))
                self.losses_label.config(text=str(losses))
                
                conn.close()
                
            # Update account value from IBKR
            if self.ibkr_connected and self.ib:
                account_values = self.ib.accountSummary()
                for av in account_values:
                    if av.tag == 'NetLiquidation':
                        self.capital_label.config(text=f"Capital: ${float(av.value):,.2f}")
                        break
                        
        except Exception as e:
            self.log(f"[X] Error updating performance: {e}")
    
    def update_validation_metrics(self):
        """Update Phase 2 validation tracking."""
        try:
            # Load cumulative history
            if self.cumulative_history_path.exists():
                with open(self.cumulative_history_path) as f:
                    history = json.load(f)
                
                # Count Phase 2 trades (after Oct 20, 2025)
                phase2_trades = [t for t in history if 
                                 datetime.fromisoformat(t.get('entry_date', '2025-01-01')).date() >= datetime(2025, 10, 20).date()]
                
                completed_trades = [t for t in phase2_trades if t.get('exit_date')]
                total_trades = len(completed_trades)
                
                # Update trades progress
                progress_pct = (total_trades / 20) * 100
                self.validation_trades.config(text=f"{total_trades}/20")
                self.validation_progress.config(text=f"{progress_pct:.0f}%")
                
                # Calculate win rate
                if total_trades >= 5:
                    wins = len([t for t in completed_trades if float(t.get('pnl', 0)) > 0])
                    win_rate = (wins / total_trades) * 100
                    self.validation_wr.config(text=f"{win_rate:.1f}%")
                    
                    # Color code based on target
                    if win_rate >= 70:
                        color = ACCENT_GREEN
                        status = "✓ Target met!"
                    elif win_rate >= 65:
                        color = ACCENT_YELLOW
                        status = "On track"
                    else:
                        color = ACCENT_RED
                        status = "Below target"
                    
                    self.validation_wr.config(fg=color)
                    self.validation_wr_status.config(text=status, fg=color)
                else:
                    self.validation_wr.config(text="--")
                    self.validation_wr_status.config(text=f"Need {5-total_trades} more")
                
                # Signal quality check (Gap 10-15%, Vol 4-10x or 15x+)
                optimal_count = 0
                for t in phase2_trades:
                    gap = abs(float(t.get('gap_percent', 0)))
                    vol_mult = float(t.get('volume_multiplier', 0))
                    
                    if 10 <= gap <= 15 and (4 <= vol_mult <= 10 or vol_mult >= 15):
                        optimal_count += 1
                
                if phase2_trades:
                    quality_pct = (optimal_count / len(phase2_trades)) * 100
                    self.validation_quality.config(text=f"{quality_pct:.0f}%")
                    
                    if quality_pct >= 80:
                        self.validation_quality_status.config(text="✓ Excellent", fg=ACCENT_GREEN)
                    elif quality_pct >= 60:
                        self.validation_quality_status.config(text="Good", fg=ACCENT_YELLOW)
                    else:
                        self.validation_quality_status.config(text="Check filters", fg=ACCENT_RED)
                
        except Exception as e:
            self.log(f"[X] Error updating validation metrics: {e}")
    
    def update_trade_history(self):
        """Update recent trade history table."""
        # Clear existing
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        try:
            if self.cumulative_history_path.exists():
                with open(self.cumulative_history_path) as f:
                    history = json.load(f)
                
                # Get last 10 completed trades
                completed = [t for t in history if t.get('exit_date')]
                recent = sorted(completed, key=lambda x: x.get('exit_date', ''), reverse=True)[:10]
                
                for trade in recent:
                    # Handle case where trade might be a JSON string instead of dict
                    if isinstance(trade, str):
                        try:
                            trade = json.loads(trade)
                        except json.JSONDecodeError:
                            self.log(f"[X] Invalid trade payload (skipping): {trade[:50]}...")
                            continue
                    
                    date = trade.get('exit_date', '')[:10] if trade.get('exit_date') else '--'
                    symbol = trade.get('symbol', '--')
                    gap = f"{float(trade.get('gap_percent', 0)):.1f}%"
                    vol = f"{float(trade.get('volume_multiplier', 0)):.1f}x"
                    score = f"{float(trade.get('signal_score', 0)):.1f}"
                    entry = f"${float(trade.get('entry_price', 0)):.2f}"
                    exit_price = f"${float(trade.get('exit_price', 0)):.2f}"
                    pnl = float(trade.get('pnl', 0))
                    pnl_str = f"${pnl:.2f}"
                    
                    # Color code
                    tag = "profit" if pnl > 0 else "loss"
                    
                    self.history_tree.insert("", tk.END, values=(
                        date, symbol, gap, vol, score, entry, exit_price, pnl_str
                    ), tags=(tag,))
                
                # Configure tag colors
                self.history_tree.tag_configure("profit", foreground=ACCENT_GREEN)
                self.history_tree.tag_configure("loss", foreground=ACCENT_RED)
                
        except Exception as e:
            self.log(f"[X] Error updating trade history: {e}")
    
    def update_scanner_stats(self):
        """Update scanner statistics."""
        try:
            # Read universe file
            universe_file = self.project_root / "configs" / "under10_tickers.txt"
            if universe_file.exists():
                with open(universe_file) as f:
                    universe = [line.strip() for line in f if line.strip()]
                self.universe_size.config(text=f"{len(universe)} tickers")
            
            # Count active/blocklisted from memory
            if self.memory_db_path.exists():
                conn = sqlite3.connect(self.memory_db_path)
                cursor = conn.cursor()
                
                # Active tickers (not ejection-eligible)
                cursor.execute("SELECT COUNT(*) FROM ticker_performance WHERE ejection_eligible = 0")
                active = cursor.fetchone()[0]
                self.active_tickers.config(text=str(active))
                
                # At-risk tickers (ejection-eligible)
                cursor.execute("SELECT COUNT(*) FROM ticker_performance WHERE ejection_eligible = 1")
                blocked = cursor.fetchone()[0]
                self.blocklist_count.config(text=str(blocked))
                
                # Match rate (recent signals that passed optimal filters)
                if self.cumulative_history_path.exists():
                    with open(self.cumulative_history_path) as f:
                        history = json.load(f)
                    
                    recent_trades = history[-20:] if len(history) >= 20 else history
                    optimal_count = 0
                    
                    for t in recent_trades:
                        gap = abs(float(t.get('gap_percent', 0)))
                        vol_mult = float(t.get('volume_multiplier', 0))
                        if 10 <= gap <= 15 and (4 <= vol_mult <= 10 or vol_mult >= 15):
                            optimal_count += 1
                    
                    if recent_trades:
                        match_rate = (optimal_count / len(recent_trades)) * 100
                        self.match_rate.config(text=f"{match_rate:.0f}%")
                
                conn.close()
                
        except Exception as e:
            self.log(f"[X] Error updating scanner stats: {e}")
    
    def update_live_signal_feed(self):
        """Update the live signal feed panel with current scanner status and signals."""
        try:
            # Update scanner status
            self.update_scanner_status()
            
            # Update signal quality counts
            self.update_signal_quality_counts()
            
            # Update live signals table
            self.update_live_signals_table()
            
        except Exception as e:
            self.log(f"[X] Error updating live signal feed: {e}")
    
    def update_scanner_status(self):
        """Update scanner status indicators."""
        try:
            # Check if scanner is running
            if self.scanner_process and self.scanner_process.poll() is None:
                self.scanner_status_label.config(text="🟢 RUNNING", fg=ACCENT_GREEN)
                
                # Get last run time from scanner output or log
                if hasattr(self, 'last_scanner_run'):
                    elapsed = datetime.now() - self.last_scanner_run
                    self.last_run_label.config(text=f"{elapsed.seconds}s ago")
                else:
                    self.last_run_label.config(text="Just now")
            else:
                self.scanner_status_label.config(text="🔴 STOPPED", fg=ACCENT_RED)
                self.last_run_label.config(text="Never")
            
            # Update market regime
            if HAS_MARKET_REGIME:
                try:
                    from market_regime import MarketRegimeDetector
                    detector = MarketRegimeDetector()
                    regime = detector.get_current_regime()
                    self.market_regime_label.config(text=regime.upper())
                    
                    # Color code regime
                    if regime == 'normal':
                        self.market_regime_label.config(fg=ACCENT_GREEN)
                    elif regime == 'highvix':
                        self.market_regime_label.config(fg=ACCENT_YELLOW)
                    else:
                        self.market_regime_label.config(fg=ACCENT_RED)
                except:
                    self.market_regime_label.config(text="UNKNOWN", fg=FG_DIM)
            else:
                self.market_regime_label.config(text="N/A", fg=FG_DIM)
            
        except Exception as e:
            self.log(f"[X] Error updating scanner status: {e}")
    
    def update_signal_quality_counts(self):
        """Update signal quality distribution counts."""
        try:
            if not HAS_MEMORY_SYSTEM or not self.memory_tracker:
                # Show zeros if memory system not available
                self.live_perfect_count.config(text="0")
                self.live_good_count.config(text="0")
                self.live_marginal_count.config(text="0")
                self.live_poor_count.config(text="0")
                return
            
            # Get today's signal counts by quality
            today = datetime.now().strftime("%Y-%m-%d")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if signal_quality table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='signal_quality'
            """)
            
            if cursor.fetchone():
                # Count signals by quality for today
                quality_counts = {}
                for quality in ['perfect', 'good', 'marginal', 'poor']:
                    cursor.execute("""
                        SELECT COUNT(*) FROM signal_quality
                        WHERE quality_tier = ? AND date(timestamp) = date(?)
                    """, (quality, today))
                    count = cursor.fetchone()[0] or 0
                    quality_counts[quality] = count
                
                # Update labels
                self.live_perfect_count.config(text=str(quality_counts.get('perfect', 0)))
                self.live_good_count.config(text=str(quality_counts.get('good', 0)))
                self.live_marginal_count.config(text=str(quality_counts.get('marginal', 0)))
                self.live_poor_count.config(text=str(quality_counts.get('poor', 0)))
            else:
                # Table doesn't exist yet
                self.live_perfect_count.config(text="0")
                self.live_good_count.config(text="0")
                self.live_marginal_count.config(text="0")
                self.live_poor_count.config(text="0")
            
            conn.close()
            
        except Exception as e:
            self.log(f"[X] Error updating signal quality counts: {e}")
    
    def update_live_signals_table(self):
        """Update the live signals table with recent signals."""
        try:
            # Clear existing items
            for item in self.live_signals_tree.get_children():
                self.live_signals_tree.delete(item)
            
            if not HAS_MEMORY_SYSTEM or not self.memory_tracker:
                return
            
            # Get recent signals from memory system
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if signal_quality table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='signal_quality'
            """)
            
            if cursor.fetchone():
                # Get recent signals (last 20)
                cursor.execute("""
                    SELECT 
                        sq.ticker,
                        sq.quality_tier,
                        sq.signal_score,
                        sq.gap_percent,
                        sq.volume_multiplier,
                        sq.timestamp,
                        sq.regime_at_signal
                    FROM signal_quality sq
                    ORDER BY sq.timestamp DESC
                    LIMIT 20
                """)
                
                recent_signals = cursor.fetchall()
                
                for signal in recent_signals:
                    ticker, quality, score, gap, vol_mult, timestamp, regime = signal
                    
                    # Format data
                    score_str = f"{score:.1f}" if score else "--"
                    gap_str = f"{gap:.1f}%" if gap else "--"
                    vol_str = f"{vol_mult:.1f}x" if vol_mult else "--"
                    
                    # Format timestamp
                    if timestamp:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%H:%M:%S")
                    else:
                        time_str = "--"
                    
                    # Determine tag based on quality
                    if quality == 'perfect':
                        tag = 'perfect'
                    elif quality == 'good':
                        tag = 'good'
                    elif quality == 'marginal':
                        tag = 'marginal'
                    else:
                        tag = 'poor'
                    
                    # Insert into tree
                    self.live_signals_tree.insert("", tk.END, values=(
                        ticker, quality.upper(), score_str, gap_str, vol_str, time_str
                    ), tags=(tag,))
            
            conn.close()
            
        except Exception as e:
            self.log(f"[X] Error updating live signals table: {e}")
    
    def refresh_data(self):
        """Refresh all dashboard data."""
        try:
            self.log("[*] Refreshing dashboard data...")
            
            # Update market data
            self.update_market_data()
            
            # Update scanner stats
            self.update_scanner_stats()
            
            # Update memory system
            self.update_memory_status()
            
            # Update live signal feed
            self.update_live_signal_feed()
            
            # Update performance charts
            self.update_performance_charts()
            
            # Update risk metrics
            self.update_risk_metrics()
            
            # Update validation tracking
            self.update_validation_metrics()
            
            # Check for alerts
            self.check_for_alerts()
            
            self.log("[OK] Dashboard data refreshed")
            
        except Exception as e:
            self.log(f"[X] Error refreshing data: {e}")
    
    def update_memory_status(self):
        """Update Phase 2.5 memory system displays."""
        if not HAS_MEMORY_SYSTEM or not self.memory_tracker:
            return
        
        try:
            # === UPDATE TODAY'S SUMMARY ===
            # Check if tables exist first
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for signal_quality table
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='signal_quality'
            """)
            has_signals_table = cursor.fetchone() is not None
            
            if has_signals_table:
                # Count signals found today (if table has timestamp column)
                try:
                    today = datetime.now().strftime("%Y-%m-%d")
                    cursor.execute("""
                        SELECT COUNT(*) FROM signal_quality
                        WHERE date(timestamp) = date(?)
                    """, (today,))
                    daily_signals = cursor.fetchone()[0] or 0
                    self.daily_signals_label.config(text=str(daily_signals))
                except sqlite3.OperationalError:
                    # Table exists but doesn't have timestamp column yet
                    self.daily_signals_label.config(text="0")
            else:
                self.daily_signals_label.config(text="0")
            
            # For trades and P&L, use simple counts from existing data
            # These will populate as the system runs
            self.daily_trades_label.config(text="0")  # Will update when cumulative history exists
            self.daily_pnl_label.config(text="$0.00", fg=FG_MAIN)
            self.win_streak_label.config(text="0")
            
            # === UPDATE SIGNAL QUALITY DISTRIBUTION ===
            quality_tiers = ['perfect', 'good', 'marginal', 'poor']
            labels = {
                'perfect': (self.perfect_count_label, self.perfect_wr_label),
                'good': (self.good_count_label, self.good_wr_label),
                'marginal': (self.marginal_count_label, self.marginal_wr_label),
                'poor': (self.poor_count_label, self.poor_wr_label)
            }
            
            for quality in quality_tiers:
                stats = self.memory_tracker.get_quality_stats(quality)
                count_label, wr_label = labels[quality]
                
                total = stats.get('total_signals', 0)
                wins = stats.get('total_wins', 0)
                wr = (wins / total * 100) if total > 0 else 0
                
                count_label.config(text=str(total))
                wr_label.config(text=f"{wr:.1f}% WR" if total > 0 else "-- WR")
            
            # === UPDATE TICKER PERFORMANCE LEADERBOARD ===
            # Clear existing
            for item in self.perf_tree.get_children():
                self.perf_tree.delete(item)
            
            # Calculate win rate by counting wins vs total outcomes (reuse existing connection)
            cursor.execute("""
                SELECT 
                    tp.ticker,
                    tp.total_outcomes,
                    CAST(SUM(CASE WHEN o.return_pct > 0 THEN 1 ELSE 0 END) AS REAL) / 
                        NULLIF(COUNT(o.outcome_id), 0) * 100 as win_rate,
                    tp.avg_return,
                    tp.ejection_eligible
                FROM ticker_performance tp
                LEFT JOIN outcomes o ON o.ticker = tp.ticker
                WHERE tp.total_outcomes > 0
                GROUP BY tp.ticker
                ORDER BY win_rate DESC
                LIMIT 10
            """)
            
            top_performers = cursor.fetchall()
            
            for ticker, trades, wr, avg_ret, ejected in top_performers:
                wr = wr or 0  # Handle None
                wr_str = f"{wr:.1f}%"
                ret_str = f"+{avg_ret:.2f}%" if avg_ret >= 0 else f"{avg_ret:.2f}%"
                
                # Determine status display and tag
                if ejected:
                    status_str = "⚠️ At Risk"
                    tag = "at_risk"
                elif wr >= 70:
                    status_str = "✅ Strong"
                    tag = "winner"
                elif wr < 40 and trades >= 5:
                    status_str = "⚠️ At Risk"
                    tag = "at_risk"
                else:
                    status_str = "📊 Active"
                    tag = ""
                
                self.perf_tree.insert("", tk.END, values=(
                    ticker, trades, wr_str, ret_str, status_str
                ), tags=(tag,) if tag else ())
            
            # === UPDATE AUTO-EJECTOR STATUS ===
            if self.auto_ejector:
                # Get ejection candidates
                candidates = self.auto_ejector.evaluate_all()
                self.ejection_candidates_label.config(text=str(len(candidates)))
                
                # Count ejection-eligible tickers
                cursor.execute("""
                    SELECT COUNT(*) FROM ticker_performance 
                    WHERE ejection_eligible = 1
                """)
                ejected_count = cursor.fetchone()[0] or 0
                self.ejected_count_label.config(text=str(ejected_count))
            
            # === UPDATE REGIME CORRELATION ===
            # Check if signal_quality table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='signal_quality'
            """)
            
            if cursor.fetchone():
                # Table exists - query regime stats by joining with outcomes
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN o.return_pct > 0 THEN 1 ELSE 0 END) as wins
                    FROM signal_quality sq
                    JOIN fills f ON sq.signal_id = f.signal_id
                    JOIN outcomes o ON f.fill_id = o.fill_id
                    WHERE sq.regime_at_signal = 'normal'
                """)
                normal_data = cursor.fetchone()
                if normal_data and normal_data[0] > 0:
                    normal_total, normal_wins = normal_data
                    normal_wr = (normal_wins / normal_total * 100)
                    self.normal_regime_wr_label.config(text=f"{normal_wr:.1f}%")
                    self.normal_regime_count_label.config(text=f"{normal_total} trades")
                else:
                    self.normal_regime_wr_label.config(text="--")
                    self.normal_regime_count_label.config(text="0 trades")
                
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN o.return_pct > 0 THEN 1 ELSE 0 END) as wins
                    FROM signal_quality sq
                    JOIN fills f ON sq.signal_id = f.signal_id
                    JOIN outcomes o ON f.fill_id = o.fill_id
                    WHERE sq.regime_at_signal = 'highvix'
                """)
                highvix_data = cursor.fetchone()
                if highvix_data and highvix_data[0] > 0:
                    highvix_total, highvix_wins = highvix_data
                    highvix_wr = (highvix_wins / highvix_total * 100)
                    self.highvix_regime_wr_label.config(text=f"{highvix_wr:.1f}%")
                    self.highvix_regime_count_label.config(text=f"{highvix_total} trades")
                else:
                    self.highvix_regime_wr_label.config(text="--")
                    self.highvix_regime_count_label.config(text="0 trades")
            else:
                # Table doesn't exist yet - show zeros
                self.normal_regime_wr_label.config(text="--")
                self.normal_regime_count_label.config(text="0 trades")
                self.highvix_regime_wr_label.config(text="--")
                self.highvix_regime_count_label.config(text="0 trades")
            
            conn.close()
            
        except Exception as e:
            self.log(f"[X] Error updating memory system: {e}")
            import traceback
            traceback.print_exc()
    
    def update_performance_charts(self):
        """Update performance charts with latest data."""
        if not HAS_MATPLOTLIB:
            return
        
        try:
            # Load cumulative history for chart data
            if not self.cumulative_history_path.exists():
                return
            
            with open(self.cumulative_history_path) as f:
                history = json.load(f)
            
            # Filter completed trades
            completed_trades = [t for t in history if t.get('exit_date')]
            if not completed_trades:
                return
            
            # Sort by exit date
            completed_trades.sort(key=lambda x: x.get('exit_date', ''))
            
            # === P&L CHART ===
            self.pnl_ax.clear()
            
            # Calculate cumulative P&L
            dates = []
            cumulative_pnl = []
            running_total = 0
            
            for trade in completed_trades:
                exit_date = trade.get('exit_date', '')
                if exit_date:
                    dates.append(datetime.fromisoformat(exit_date))
                    pnl = float(trade.get('pnl', 0))
                    running_total += pnl
                    cumulative_pnl.append(running_total)
            
            if dates and cumulative_pnl:
                self.pnl_ax.plot(dates, cumulative_pnl, 'o-', linewidth=2, markersize=4, 
                               color=ACCENT_GREEN if cumulative_pnl[-1] >= 0 else ACCENT_RED)
                
                # Format axes
                self.pnl_ax.set_title('Cumulative P&L', fontsize=10, color=FG_BRIGHT, pad=10)
                self.pnl_ax.set_ylabel('P&L ($)', fontsize=8, color=FG_MAIN)
                self.pnl_ax.grid(True, alpha=0.3, color=FG_DIM)
                
                # Format x-axis dates
                import matplotlib.dates as mdates
                self.pnl_ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                self.pnl_ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))  # Weekly ticks
                
                # Rotate date labels
                for label in self.pnl_ax.get_xticklabels():
                    label.set_rotation(45)
                    label.set_fontsize(7)
                
                # Add current P&L annotation
                current_pnl = cumulative_pnl[-1]
                color = ACCENT_GREEN if current_pnl >= 0 else ACCENT_RED
                self.pnl_ax.text(0.02, 0.98, f'Current: ${current_pnl:.2f}', 
                               transform=self.pnl_ax.transAxes, fontsize=9, 
                               verticalalignment='top', color=color,
                               bbox=dict(boxstyle='round,pad=0.3', facecolor=BG_LIGHT, alpha=0.8))
            
            self.pnl_canvas.draw()
            
            # === WIN RATE CHART ===
            self.wr_ax.clear()
            
            if len(completed_trades) >= 5:  # Need minimum trades for meaningful win rate
                # Calculate rolling win rate (last 10 trades)
                wr_dates = []
                wr_values = []
                
                for i in range(9, len(completed_trades)):  # Start from 10th trade
                    window = completed_trades[i-9:i+1]  # Last 10 trades
                    wins = sum(1 for t in window if float(t.get('pnl', 0)) > 0)
                    win_rate = (wins / len(window)) * 100
                    
                    # Use the exit date of the most recent trade in window
                    wr_dates.append(datetime.fromisoformat(window[-1].get('exit_date', '')))
                    wr_values.append(win_rate)
                
                if wr_dates and wr_values:
                    self.wr_ax.plot(wr_dates, wr_values, 's-', linewidth=2, markersize=4, color=ACCENT_BLUE)
                    
                    # Add target line at 70%
                    self.wr_ax.axhline(y=70, color=ACCENT_GREEN, linestyle='--', alpha=0.7, linewidth=1)
                    self.wr_ax.text(wr_dates[-1], 72, 'Target: 70%', fontsize=7, color=ACCENT_GREEN)
                    
                    # Format axes
                    self.wr_ax.set_title('Rolling Win Rate (10 Trades)', fontsize=10, color=FG_BRIGHT, pad=10)
                    self.wr_ax.set_ylabel('Win Rate (%)', fontsize=8, color=FG_MAIN)
                    self.wr_ax.set_ylim(0, 100)
                    self.wr_ax.grid(True, alpha=0.3, color=FG_DIM)
                    
                    # Format x-axis dates
                    self.wr_ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                    self.wr_ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))
                    
                    # Rotate date labels
                    for label in self.wr_ax.get_xticklabels():
                        label.set_rotation(45)
                        label.set_fontsize(7)
                    
                    # Add current win rate annotation
                    current_wr = wr_values[-1]
                    color = ACCENT_GREEN if current_wr >= 70 else ACCENT_RED if current_wr < 50 else ACCENT_YELLOW
                    self.wr_ax.text(0.02, 0.98, f'Current: {current_wr:.1f}%', 
                                   transform=self.wr_ax.transAxes, fontsize=9, 
                                   verticalalignment='top', color=color,
                                   bbox=dict(boxstyle='round,pad=0.3', facecolor=BG_LIGHT, alpha=0.8))
            
            self.wr_canvas.draw()
            
            # === SIGNAL QUALITY TREND CHART ===
            self.sq_ax.clear()
            
            # Get signal quality data from memory database
            if self.memory_db_path.exists():
                conn = sqlite3.connect(self.memory_db_path)
                cursor = conn.cursor()
                
                # Check if signal_quality table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signal_quality'")
                if cursor.fetchone():
                    # Get signal quality over time (last 50 signals)
                    cursor.execute("""
                        SELECT 
                            DATE(created_at) as date,
                            quality_score,
                            COUNT(*) as count
                        FROM signal_quality 
                        WHERE created_at >= date('now', '-30 days')
                        GROUP BY DATE(created_at), quality_score
                        ORDER BY DATE(created_at)
                    """)
                    
                    sq_data = cursor.fetchall()
                    if sq_data:
                        # Group by date
                        dates = []
                        perfect_counts = []
                        good_counts = []
                        marginal_counts = []
                        poor_counts = []
                        
                        date_dict = {}
                        for row in sq_data:
                            date_str, quality, count = row
                            date = datetime.strptime(date_str, '%Y-%m-%d').date()
                            
                            if date not in date_dict:
                                date_dict[date] = {'perfect': 0, 'good': 0, 'marginal': 0, 'poor': 0}
                            
                            if quality >= 9:
                                date_dict[date]['perfect'] += count
                            elif quality >= 7:
                                date_dict[date]['good'] += count
                            elif quality >= 5:
                                date_dict[date]['marginal'] += count
                            else:
                                date_dict[date]['poor'] += count
                        
                        # Sort dates and create arrays
                        sorted_dates = sorted(date_dict.keys())
                        for date in sorted_dates:
                            dates.append(date)
                            perfect_counts.append(date_dict[date]['perfect'])
                            good_counts.append(date_dict[date]['good'])
                            marginal_counts.append(date_dict[date]['marginal'])
                            poor_counts.append(date_dict[date]['poor'])
                        
                        if dates:
                            # Create stacked bar chart
                            self.sq_ax.bar(dates, perfect_counts, label='Perfect (9-10)', 
                                         color=ACCENT_GREEN, alpha=0.8, width=0.8)
                            self.sq_ax.bar(dates, good_counts, bottom=perfect_counts, 
                                         label='Good (7-8)', color=ACCENT_BLUE, alpha=0.8, width=0.8)
                            self.sq_ax.bar(dates, marginal_counts, 
                                         bottom=[p+g for p,g in zip(perfect_counts, good_counts)], 
                                         label='Marginal (5-6)', color=ACCENT_YELLOW, alpha=0.8, width=0.8)
                            self.sq_ax.bar(dates, poor_counts, 
                                         bottom=[p+g+m for p,g,m in zip(perfect_counts, good_counts, marginal_counts)], 
                                         label='Poor (0-4)', color=ACCENT_RED, alpha=0.8, width=0.8)
                            
                            # Format axes
                            self.sq_ax.set_title('Signal Quality Distribution (Last 30 Days)', 
                                               fontsize=10, color=FG_BRIGHT, pad=10)
                            self.sq_ax.set_ylabel('Signal Count', fontsize=8, color=FG_MAIN)
                            self.sq_ax.grid(True, alpha=0.3, color=FG_DIM)
                            
                            # Format x-axis dates
                            self.sq_ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                            self.sq_ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
                            
                            # Rotate date labels
                            for label in self.sq_ax.get_xticklabels():
                                label.set_rotation(45)
                                label.set_fontsize(7)
                            
                            # Add legend
                            self.sq_ax.legend(fontsize=7, loc='upper left', framealpha=0.9)
                    
                conn.close()
            
            self.sq_canvas.draw()
            
            # === REGIME PERFORMANCE CHART ===
            self.regime_ax.clear()
            
            # Get regime performance data from memory database
            if self.memory_db_path.exists():
                conn = sqlite3.connect(self.memory_db_path)
                cursor = conn.cursor()
                
                # Check if outcomes table exists with regime data
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='outcomes'")
                if cursor.fetchone():
                    # Get performance by regime
                    cursor.execute("""
                        SELECT 
                            sq.regime_at_signal,
                            COUNT(*) as total_trades,
                            SUM(CASE WHEN o.return_pct > 0 THEN 1 ELSE 0 END) as wins,
                            AVG(o.return_pct) as avg_return
                        FROM signal_quality sq
                        JOIN fills f ON sq.signal_id = f.signal_id
                        JOIN outcomes o ON f.fill_id = o.fill_id
                        GROUP BY sq.regime_at_signal
                        HAVING total_trades >= 3
                        ORDER BY total_trades DESC
                    """)
                    
                    regime_data = cursor.fetchall()
                    if regime_data:
                        regimes = []
                        win_rates = []
                        avg_returns = []
                        trade_counts = []
                        
                        for row in regime_data:
                            regime, total, wins, avg_ret = row
                            regimes.append(regime.title())
                            win_rates.append((wins / total) * 100)
                            avg_returns.append(avg_ret * 100 if avg_ret else 0)  # Convert to percentage
                            trade_counts.append(total)
                        
                        if regimes:
                            # Create dual-axis chart
                            ax1 = self.regime_ax
                            ax2 = ax1.twinx()
                            
                            # Win rate bars
                            bars = ax1.bar(regimes, win_rates, color=ACCENT_BLUE, alpha=0.7, width=0.6, label='Win Rate %')
                            ax1.set_ylabel('Win Rate (%)', color=ACCENT_BLUE, fontsize=8)
                            ax1.tick_params(axis='y', labelcolor=ACCENT_BLUE)
                            ax1.set_ylim(0, 100)
                            
                            # Average return line
                            line = ax2.plot(regimes, avg_returns, 'o-', color=ACCENT_GREEN, linewidth=2, 
                                          markersize=6, label='Avg Return %')
                            ax2.set_ylabel('Avg Return (%)', color=ACCENT_GREEN, fontsize=8)
                            ax2.tick_params(axis='y', labelcolor=ACCENT_GREEN)
                            
                            # Add trade count labels on bars
                            for bar, count in zip(bars, trade_counts):
                                height = bar.get_height()
                                ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                                        f'n={count}', ha='center', va='bottom', fontsize=7, color=FG_MAIN)
                            
                            # Format axes
                            ax1.set_title('Performance by Market Regime', fontsize=10, color=FG_BRIGHT, pad=10)
                            ax1.grid(True, alpha=0.3, color=FG_DIM)
                            
                            # Combine legends
                            lines1, labels1 = ax1.get_legend_handles_labels()
                            lines2, labels2 = ax2.get_legend_handles_labels()
                            ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc='upper right', framealpha=0.9)
                    
                conn.close()
            
            self.regime_canvas.draw()
            
        except Exception as e:
            self.log(f"[X] Error updating performance charts: {e}")
            import traceback
            traceback.print_exc()
    
    def run_ejection_evaluation(self):
        """Run auto-ejector evaluation and display results."""
        if not HAS_MEMORY_SYSTEM or not self.auto_ejector:
            self.log("[X] Auto-ejector not available")
            return
        
        try:
            dry_run = self.dry_run_var.get()
            self.log(f"[*] Running ejection evaluation (dry_run={dry_run})...")
            
            # Evaluate all tickers (returns dict with candidates list)
            result = self.auto_ejector.auto_eject_all(dry_run=dry_run)
            candidates = result.get('candidates', [])
            
            # Update display
            self.ejection_text.configure(state=tk.NORMAL)
            self.ejection_text.delete("1.0", tk.END)
            
            if not candidates:
                self.ejection_text.insert("1.0", "✅ No tickers meet ejection criteria.\n\n")
                self.ejection_text.insert(tk.END, "All active tickers are performing adequately.")
                self.log("[OK] Ejection evaluation complete - no actions needed")
            else:
                self.ejection_text.insert("1.0", f"⚠️  Found {len(candidates)} ejection candidate(s):\n\n")
                
                for i, candidate in enumerate(candidates, 1):
                    ticker = candidate['ticker']
                    reason = candidate['reason']
                    trades = candidate['total_trades']
                    win_rate = candidate['win_rate']
                    
                    # All candidates from auto_eject_all meet ejection criteria
                    status = "🚫 EJECT" if not dry_run else "⚠️  WOULD EJECT"
                    
                    self.ejection_text.insert(tk.END, 
                        f"{i}. {ticker}: {status}\n"
                        f"   Win Rate: {win_rate:.1f}% ({trades} trades)\n"
                        f"   Reason: {reason}\n\n"
                    )
                
                if dry_run:
                    self.ejection_text.insert(tk.END, 
                        "\n💡 Dry Run Mode: No changes made.\n"
                        "Uncheck 'Dry Run' to apply ejections."
                    )
                else:
                    # Ejections already performed by auto_eject_all (dry_run=False)
                    ejected_count = result.get('ejected', len(candidates))
                    
                    self.ejection_text.insert(tk.END, 
                        f"\n✅ Ejected {ejected_count} ticker(s)."
                    )
                    self.log(f"[OK] Auto-ejector: {ejected_count} tickers ejected")
            
            self.ejection_text.configure(state=tk.DISABLED)
            
            # Update memory panel to reflect changes
            self.update_memory_status()
            
        except Exception as e:
            self.log(f"[X] Error in ejection evaluation: {e}")
            import traceback
            traceback.print_exc()

    
    def show_settings(self):
        """Show settings dialog for adjustment parameters."""
        # Create modal dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("PennyHunter Settings")
        dialog.geometry("600x500")
        dialog.configure(bg=BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Title
        title = tk.Label(
            dialog,
            text="⚙️ Adjustment Settings",
            font=FONT_TITLE,
            bg=BG_DARK,
            fg=ACCENT_BLUE
        )
        title.pack(pady=20)
        
        # Settings frame
        settings_frame = tk.Frame(dialog, bg=BG_MEDIUM, relief=tk.RAISED, borderwidth=2)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Initialize setting_entries dictionary on dialog
        dialog.setting_entries = {}
        
        # Get current settings
        adjustments = self.config.get('adjustments', {})
        vix_mult = adjustments.get('vix_multiplier', 1.0)
        time_mult = adjustments.get('time_multiplier', 1.0)
        regime_mult = adjustments.get('regime_multiplier', 1.0)
        
        # VIX Multiplier
        self.create_setting_row(settings_frame, "VIX Multiplier", vix_mult, 0,
            "Higher values = more aggressive exits in high volatility (0.5 - 2.0)", dialog, 0.1, 5.0)
        
        # Time Multiplier
        self.create_setting_row(settings_frame, "Time Multiplier", time_mult, 1,
            "Higher values = faster target decay over time (0.5 - 2.0)", dialog, 0.1, 5.0)
        
        # Regime Multiplier
        self.create_setting_row(settings_frame, "Regime Multiplier", regime_mult, 2,
            "Adjustment factor for different market regimes (0.5 - 2.0)", dialog, 0.1, 5.0)
        
        # Scanner Capital
        scanner_config = self.config.get('scanner', {})
        capital = scanner_config.get('capital', 200.0)
        self.create_setting_row(settings_frame, "Scanner Capital ($)", capital, 3,
            "Amount of capital to allocate for paper trading (100 - 10000)", dialog, 100, 10000)
        
        # Memory thresholds
        memory_config = self.config.get('memory', {})
        active_threshold = memory_config.get('active_threshold', 0.50)
        eject_threshold = memory_config.get('eject_threshold', 0.30)
        
        self.create_setting_row(settings_frame, "Active Threshold (%)", active_threshold * 100, 4,
            "Win rate to keep ticker active (30 - 70)", dialog, 10, 90, True)
        
        self.create_setting_row(settings_frame, "Eject Threshold (%)", eject_threshold * 100, 5,
            "Win rate below which ticker is ejected (10 - 40)", dialog, 5, 50, True)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=BG_DARK)
        btn_frame.pack(pady=10)
        
        save_btn = tk.Button(
            btn_frame,
            text="💾 SAVE",
            command=lambda: self.save_settings(dialog),
            bg=ACCENT_GREEN,
            fg=FG_BRIGHT,
            font=FONT_BOLD,
            width=15,
            cursor="hand2"
        )
        save_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(
            btn_frame,
            text="✖️ CANCEL",
            command=dialog.destroy,
            bg=ACCENT_RED,
            fg=FG_BRIGHT,
            font=FONT_BOLD,
            width=15,
            cursor="hand2"
        )
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Store entry widgets for later access
        dialog.setting_entries = {}
    
    def create_setting_row(self, parent, label, value, row, tooltip, dialog, min_val=None, max_val=None, is_percentage=False):
        """Create a setting input row with validation and real-time feedback."""
        # Label
        lbl = tk.Label(
            parent,
            text=label,
            font=FONT_BOLD,
            bg=BG_MEDIUM,
            fg=FG_MAIN,
            anchor=tk.W
        )
        lbl.grid(row=row, column=0, sticky="w", padx=20, pady=10)
        
        # Entry frame for validation styling
        entry_frame = tk.Frame(parent, bg=BG_MEDIUM)
        entry_frame.grid(row=row, column=1, sticky="e", padx=20, pady=10)
        
        # Entry
        entry_var = tk.StringVar(value=str(value))
        entry = tk.Entry(
            entry_frame,
            textvariable=entry_var,
            font=FONT_MAIN,
            bg=BG_LIGHT,
            fg=FG_BRIGHT,
            width=15,
            insertbackground=FG_BRIGHT,
            relief=tk.FLAT,
            borderwidth=2
        )
        entry.pack()
        
        # Validation label (initially hidden)
        validation_label = tk.Label(
            entry_frame,
            text="",
            font=FONT_MONO,
            bg=BG_MEDIUM,
            fg=ACCENT_RED,
            anchor=tk.W
        )
        validation_label.pack(fill=tk.X)
        
        # Tooltip
        tip = tk.Label(
            parent,
            text=tooltip,
            font=FONT_MONO,
            bg=BG_MEDIUM,
            fg=FG_DIM,
            anchor=tk.W,
            wraplength=500
        )
        tip.grid(row=row, column=0, columnspan=2, sticky="w", padx=40, pady=(0, 5))
        
        # Store entry and validation info in dialog
        if not hasattr(dialog, 'setting_entries'):
            dialog.setting_entries = {}
        if not hasattr(dialog, 'validation_info'):
            dialog.validation_info = {}
            
        dialog.setting_entries[label] = entry_var
        dialog.validation_info[label] = {
            'entry': entry,
            'label': validation_label,
            'min': min_val,
            'max': max_val,
            'is_percentage': is_percentage
        }
        
        # Bind validation to entry changes
        entry_var.trace_add("write", lambda *args, l=label, d=dialog: self.validate_setting(l, d))
        
        # Initial validation
        self.validate_setting(label, dialog)
        
        # Configure grid
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
    
    def validate_setting(self, label, dialog):
        """Validate a setting value and provide real-time feedback."""
        if not hasattr(dialog, 'validation_info') or label not in dialog.validation_info:
            return
            
        info = dialog.validation_info[label]
        entry = info['entry']
        validation_label = info['label']
        min_val = info['min']
        max_val = info['max']
        is_percentage = info['is_percentage']
        
        try:
            value_str = dialog.setting_entries[label].get().strip()
            
            # Check if empty
            if not value_str:
                entry.config(bg="#ffcccc", relief=tk.SUNKEN)  # Light red background
                validation_label.config(text="Required field", fg=ACCENT_RED)
                return False
            
            # Parse numeric value
            try:
                value = float(value_str)
            except ValueError:
                entry.config(bg="#ffcccc", relief=tk.SUNKEN)
                validation_label.config(text="Must be a number", fg=ACCENT_RED)
                return False
            
            # Check range
            if min_val is not None and value < min_val:
                entry.config(bg="#ffcccc", relief=tk.SUNKEN)
                validation_label.config(text=f"Minimum: {min_val}", fg=ACCENT_RED)
                return False
                
            if max_val is not None and value > max_val:
                entry.config(bg="#ffcccc", relief=tk.SUNKEN)
                validation_label.config(text=f"Maximum: {max_val}", fg=ACCENT_RED)
                return False
            
            # Special validation for thresholds
            if "Threshold" in label:
                active_threshold = None
                eject_threshold = None
                
                # Get other threshold values for cross-validation
                if "Active Threshold" in label:
                    if "Eject Threshold (%)" in dialog.setting_entries:
                        try:
                            eject_val = float(dialog.setting_entries["Eject Threshold (%)"].get())
                            if value <= eject_val:
                                entry.config(bg="#ffcccc", relief=tk.SUNKEN)
                                validation_label.config(text="Must be > Eject Threshold", fg=ACCENT_RED)
                                return False
                        except:
                            pass
                elif "Eject Threshold" in label:
                    if "Active Threshold (%)" in dialog.setting_entries:
                        try:
                            active_val = float(dialog.setting_entries["Active Threshold (%)"].get())
                            if value >= active_val:
                                entry.config(bg="#ffcccc", relief=tk.SUNKEN)
                                validation_label.config(text="Must be < Active Threshold", fg=ACCENT_RED)
                                return False
                        except:
                            pass
            
            # Valid
            entry.config(bg=BG_LIGHT, relief=tk.FLAT)
            validation_label.config(text="✓ Valid", fg=ACCENT_GREEN)
            return True
            
        except Exception as e:
            entry.config(bg="#ffcccc", relief=tk.SUNKEN)
            validation_label.config(text="Invalid input", fg=ACCENT_RED)
            return False
    
    def save_settings(self, dialog):
        """Save settings to config file with validation."""
        try:
            # Validate all settings first
            all_valid = True
            for label in dialog.setting_entries.keys():
                if not self.validate_setting(label, dialog):
                    all_valid = False
            
            if not all_valid:
                messagebox.showerror("Validation Error", "Please fix the validation errors before saving.")
                return
            
            # Get values from dialog
            entries = dialog.setting_entries
            
            # Update config
            if 'adjustments' not in self.config:
                self.config['adjustments'] = {}
            
            self.config['adjustments']['vix_multiplier'] = float(entries["VIX Multiplier"].get())
            self.config['adjustments']['time_multiplier'] = float(entries["Time Multiplier"].get())
            self.config['adjustments']['regime_multiplier'] = float(entries["Regime Multiplier"].get())
            
            if 'scanner' not in self.config:
                self.config['scanner'] = {}
            self.config['scanner']['capital'] = float(entries["Scanner Capital ($)"].get())
            
            if 'memory' not in self.config:
                self.config['memory'] = {}
            self.config['memory']['active_threshold'] = float(entries["Active Threshold (%)"].get()) / 100
            self.config['memory']['eject_threshold'] = float(entries["Eject Threshold (%)"].get()) / 100
            
            # Save to file
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            
            self.log("[OK] Settings saved to config file")
            messagebox.showinfo("Success", "Settings saved successfully!\n\nRestart scanner for changes to take effect.")
            dialog.destroy()
            
        except Exception as e:
            self.log(f"[X] Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")
    
    def log(self, message):
        """Add message to log panel with color coding."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def pulse_connection_indicator(self):
        """Animate the connection status indicator with pulsing effect."""
        if not hasattr(self, 'pulse_state'):
            self.pulse_state = 0
        
        # Pulse colors based on connection status
        if self.ibkr_connected:
            colors = [ACCENT_GREEN, "#3fb950", "#4ade80", "#3fb950"]
        elif HAS_IBKR:
            # IBKR available but not connected - show warning
            colors = [ACCENT_YELLOW, "#d29922", "#f2cc60", "#d29922"]
        else:
            # IBKR not available - show grey
            colors = [FG_DIM, "#7d8590", "#8b949e", "#7d8590"]
        
        self.connection_indicator.config(fg=colors[self.pulse_state % len(colors)])
        self.pulse_state += 1
        
        # Schedule next pulse
        self.root.after(500, self.pulse_connection_indicator)
    
    def start_updates(self):
        """Start background update thread."""
        self.stop_update.clear()
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()
        
        # Initial data load
        self.root.after(100, self.refresh_data)
    
    def update_loop(self):
        """Background update loop."""
        while not self.stop_update.is_set():
            # Update data every 30 seconds
            time.sleep(30)
            if not self.stop_update.is_set():
                self.root.after(0, self.update_market_data)
                self.root.after(0, self.update_live_signal_feed)
    
    def on_closing(self):
        """Handle window close."""
        # Stop scanner if running
        if self.scanner_process and self.scanner_process.poll() is None:
            self.log("[NOTE] Stopping scanner before exit...")
            self.stop_scanner()
        
        # Disconnect IBKR
        if self.ibkr_connected and self.ib:
            try:
                self.ib.disconnect()
                self.log("[OK] IBKR disconnected")
            except:
                pass
        
        # Stop update thread
        self.stop_update.set()
        if self.update_thread:
            self.update_thread.join(timeout=2)
        
        self.root.destroy()
    
    def export_trades_csv(self):
        """Export trade history to CSV file."""
        try:
            from tkinter import filedialog
            import csv
            
            # Get file path
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Trades to CSV"
            )
            
            if not file_path:
                return
            
            # Load trade data
            if not self.cumulative_history_path.exists():
                messagebox.showerror("Export Error", "No trade history available to export.")
                return
            
            with open(self.cumulative_history_path) as f:
                trades = json.load(f)
            
            # Write CSV
            with open(file_path, 'w', newline='') as csvfile:
                fieldnames = ['entry_date', 'exit_date', 'symbol', 'gap_percent', 'volume', 
                            'score', 'entry_price', 'exit_price', 'pnl', 'return_pct', 'regime']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in trades:
                    writer.writerow({
                        'entry_date': trade.get('entry_date', ''),
                        'exit_date': trade.get('exit_date', ''),
                        'symbol': trade.get('symbol', ''),
                        'gap_percent': trade.get('gap_percent', ''),
                        'volume': trade.get('volume', ''),
                        'score': trade.get('score', ''),
                        'entry_price': trade.get('entry_price', ''),
                        'exit_price': trade.get('exit_price', ''),
                        'pnl': trade.get('pnl', ''),
                        'return_pct': trade.get('return_pct', ''),
                        'regime': trade.get('regime', '')
                    })
            
            self.log(f"[OK] Exported {len(trades)} trades to {file_path}")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(trades)} trades to CSV.")
            
        except Exception as e:
            self.log(f"[X] Error exporting trades to CSV: {e}")
            messagebox.showerror("Export Error", f"Failed to export trades: {e}")
    
    def export_trades_json(self):
        """Export trade history to JSON file."""
        try:
            from tkinter import filedialog
            
            # Get file path
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Export Trades to JSON"
            )
            
            if not file_path:
                return
            
            # Load and export trade data
            if not self.cumulative_history_path.exists():
                messagebox.showerror("Export Error", "No trade history available to export.")
                return
            
            with open(self.cumulative_history_path) as f:
                trades = json.load(f)
            
            # Write formatted JSON
            with open(file_path, 'w') as jsonfile:
                json.dump(trades, jsonfile, indent=2)
            
            self.log(f"[OK] Exported {len(trades)} trades to {file_path}")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(trades)} trades to JSON.")
            
        except Exception as e:
            self.log(f"[X] Error exporting trades to JSON: {e}")
            messagebox.showerror("Export Error", f"Failed to export trades: {e}")
    
    def export_signals_csv(self):
        """Export current signals to CSV file."""
        try:
            from tkinter import filedialog
            import csv
            
            # Get file path
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Signals to CSV"
            )
            
            if not file_path:
                return
            
            # Get signals from memory database
            signals = []
            if self.memory_db_path.exists():
                conn = sqlite3.connect(self.memory_db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        sq.created_at,
                        sq.symbol,
                        sq.quality_score,
                        sq.gap_percent,
                        sq.volume,
                        sq.price_at_signal,
                        sq.regime_at_signal,
                        CASE WHEN f.fill_id IS NOT NULL THEN 'Executed' ELSE 'Pending' END as status
                    FROM signal_quality sq
                    LEFT JOIN fills f ON sq.signal_id = f.signal_id
                    WHERE DATE(sq.created_at) = DATE('now')
                    ORDER BY sq.created_at DESC
                """)
                
                rows = cursor.fetchall()
                for row in rows:
                    signals.append({
                        'timestamp': row[0],
                        'symbol': row[1],
                        'score': row[2],
                        'gap_percent': row[3],
                        'volume': row[4],
                        'price': row[5],
                        'regime': row[6],
                        'status': row[7]
                    })
                
                conn.close()
            
            if not signals:
                messagebox.showwarning("Export Warning", "No signals found for today to export.")
                return
            
            # Write CSV
            with open(file_path, 'w', newline='') as csvfile:
                fieldnames = ['timestamp', 'symbol', 'score', 'gap_percent', 'volume', 'price', 'regime', 'status']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for signal in signals:
                    writer.writerow(signal)
            
            self.log(f"[OK] Exported {len(signals)} signals to {file_path}")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(signals)} signals to CSV.")
            
        except Exception as e:
            self.log(f"[X] Error exporting signals to CSV: {e}")
            messagebox.showerror("Export Error", f"Failed to export signals: {e}")
    
    def export_signals_json(self):
        """Export current signals to JSON file."""
        try:
            from tkinter import filedialog
            
            # Get file path
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Export Signals to JSON"
            )
            
            if not file_path:
                return
            
            # Get signals from memory database
            signals = []
            if self.memory_db_path.exists():
                conn = sqlite3.connect(self.memory_db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        sq.created_at,
                        sq.symbol,
                        sq.quality_score,
                        sq.gap_percent,
                        sq.volume,
                        sq.price_at_signal,
                        sq.regime_at_signal,
                        CASE WHEN f.fill_id IS NOT NULL THEN 'Executed' ELSE 'Pending' END as status
                    FROM signal_quality sq
                    LEFT JOIN fills f ON sq.signal_id = f.signal_id
                    WHERE DATE(sq.created_at) = DATE('now')
                    ORDER BY sq.created_at DESC
                """)
                
                rows = cursor.fetchall()
                for row in rows:
                    signals.append({
                        'timestamp': row[0],
                        'symbol': row[1],
                        'score': row[2],
                        'gap_percent': row[3],
                        'volume': row[4],
                        'price': row[5],
                        'regime': row[6],
                        'status': row[7]
                    })
                
                conn.close()
            
            if not signals:
                messagebox.showwarning("Export Warning", "No signals found for today to export.")
                return
            
            # Write JSON
            with open(file_path, 'w') as jsonfile:
                json.dump(signals, jsonfile, indent=2)
            
            self.log(f"[OK] Exported {len(signals)} signals to {file_path}")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(signals)} signals to JSON.")
            
        except Exception as e:
            self.log(f"[X] Error exporting signals to JSON: {e}")
            messagebox.showerror("Export Error", f"Failed to export signals: {e}")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = TradingDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
