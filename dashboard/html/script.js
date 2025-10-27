// AutoTrader Dashboard JavaScript
// Handles real-time updates, user interactions, and data management

class AutoTraderDashboard {
    constructor() {
        this.scannerRunning = false;
        this.updateInterval = null;
        this.apiBaseUrl = 'http://localhost:8001/api'; // FastAPI backend
        this.init();
    }

    init() {
        this.updateTime();
        this.loadInitialData();
        this.setupEventListeners();
        this.startPeriodicUpdates();
    }

    // Time and status updates
    updateTime() {
        const now = new Date();
        const timeString = now.toLocaleString();
        const timeOnly = now.toLocaleTimeString();

        const timestampElement = document.getElementById('current-time');
        const lastUpdateElement = document.getElementById('last-update');

        if (timestampElement) timestampElement.textContent = timeString;
        if (lastUpdateElement) lastUpdateElement.textContent = timeOnly;
    }

    // Data loading and updates
    async loadInitialData() {
        try {
            // Load all data from API
            await this.loadMarketData();
            await this.loadBrokerStatus();
            await this.loadAccountInfo();
            await this.loadPositions();
            await this.loadPerformance();
            await this.loadMemorySystem();
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    }

    async loadMarketData() {
        try {
            // Call real API endpoint for market regime
            const response = await fetch(`${this.apiBaseUrl}/trading/regime`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Transform API response to dashboard format (no fallbacks)
            const marketData = {
                vix: { 
                    value: data.vix ?? '--',
                    status: data.vix_status || 'UNKNOWN' 
                },
                spy: { 
                    value: data.spy_price ?? '--',
                    change: data.spy_change ?? 0
                },
                regime: { 
                    value: data.regime || 'UNKNOWN',
                    trading: data.market_open ? 'TRADING' : 'CLOSED' 
                }
            };

            this.updateMarketIndicators(marketData);
            this.addLogEntry(`Market loaded: ${marketData.regime.value}, VIX: ${marketData.vix.value}`);
        } catch (error) {
            console.error('Failed to load market data:', error);
            this.addLogEntry(`Error loading market data: ${error.message}`);
        }
    }

    updateMarketIndicators(data) {
        // Update VIX
        const vixValue = document.getElementById('vix-value');
        const vixStatus = document.getElementById('vix-status');
        if (vixValue) vixValue.textContent = data.vix.value;
        if (vixStatus) {
            vixStatus.textContent = data.vix.status;
            vixStatus.setAttribute('data-status', data.vix.status.toLowerCase());
        }

        // Update SPY
        const spyValue = document.getElementById('spy-value');
        const spyChange = document.getElementById('spy-change');
        if (spyValue) spyValue.textContent = typeof data.spy.value === 'number' ? data.spy.value.toFixed(2) : data.spy.value;
        if (spyChange) {
            const changeText = typeof data.spy.change === 'number' 
                ? `${data.spy.change >= 0 ? '+' : ''}${data.spy.change.toFixed(2)}%`
                : '--';
            spyChange.textContent = changeText;
            spyChange.setAttribute('data-trend', data.spy.change >= 0 ? 'up' : 'down');
        }

        // Update Regime
        const regimeValue = document.getElementById('regime-value');
        const tradingStatus = document.getElementById('trading-status');
        if (regimeValue) regimeValue.textContent = data.regime.value;
        if (tradingStatus) tradingStatus.textContent = data.regime.trading;
    }

    async loadAccountInfo() {
        try {
            // Get broker status to find active account
            const response = await fetch(`${this.apiBaseUrl}/trading/broker-status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const brokers = await response.json();
            
            // Find the first connected broker
            let activeAccount = null;
            for (const [key, broker] of Object.entries(brokers)) {
                if (broker.connected) {
                    activeAccount = {
                        name: key.toUpperCase(),
                        id: broker.account_id || 'N/A',
                        capital: broker.account_value || 0
                    };
                    break;
                }
            }
            
            if (activeAccount) {
                const accountIdEl = document.getElementById('account-id');
                const accountCapitalEl = document.getElementById('account-capital');
                
                if (accountIdEl) accountIdEl.textContent = `${activeAccount.name} ${activeAccount.id}`;
                if (accountCapitalEl) accountCapitalEl.textContent = activeAccount.capital.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
                
                this.addLogEntry(`Account loaded: ${activeAccount.name} ${activeAccount.id}`);
            } else {
                this.addLogEntry('No active broker connection');
            }
        } catch (error) {
            console.error('Failed to load account info:', error);
            this.addLogEntry(`Error loading account: ${error.message}`);
        }
    }

    async loadBrokerStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/trading/broker-status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const brokers = await response.json();
            this.updateBrokerGrid(brokers);
            
            // Count connected brokers
            const connectedCount = Object.values(brokers).filter(b => b.connected).length;
            this.addLogEntry(`Brokers: ${connectedCount} connected`);
        } catch (error) {
            console.error('Failed to load broker status:', error);
            this.addLogEntry(`Error loading broker status: ${error.message}`);
        }
    }

    updateBrokerGrid(brokers) {
        const grid = document.getElementById('broker-grid');
        if (!grid) return;

        grid.innerHTML = '';

        for (const [key, broker] of Object.entries(brokers)) {
            const card = document.createElement('div');
            card.className = `broker-card ${broker.status}`;
            
            let statusClass = 'offline';
            if (broker.connected && broker.status === 'online') {
                statusClass = 'online';
            } else if (broker.status === 'not_configured' || broker.status === 'error') {
                statusClass = 'not-configured';
            }
            
            card.className = `broker-card ${statusClass}`;
            
            let detailsHTML = '';
            if (broker.connected) {
                detailsHTML = `
                    <div class="broker-details">
                        ${broker.account_id ? `Account: ${broker.account_id}<br>` : ''}
                        ${broker.host ? `${broker.host}<br>` : ''}
                        Value: $${broker.account_value ? broker.account_value.toLocaleString() : '0'}
                    </div>
                `;
            } else {
                detailsHTML = `
                    <div class="broker-details">
                        ${broker.message || broker.error || 'Not configured'}
                    </div>
                `;
            }
            
            card.innerHTML = `
                <div class="broker-name">${broker.name}</div>
                <div class="broker-status">${broker.message || broker.status}</div>
                ${detailsHTML}
                <span class="broker-badge ${statusClass}">${broker.connected ? 'CONNECTED' : 'DISCONNECTED'}</span>
            `;
            
            grid.appendChild(card);
        }
    }

    async loadPositions() {
        try {
            // Call real API endpoint for positions
            const response = await fetch(`${this.apiBaseUrl}/trading/positions`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const apiPositions = await response.json();
            
            // Transform API response to dashboard format
            const positions = apiPositions.map(pos => ({
                symbol: pos.symbol || pos.ticker,
                shares: pos.quantity || pos.shares || 0,
                entry: pos.entry_price || pos.avg_entry_price || 0,
                current: pos.current_price || pos.last_price || 0,
                target: pos.target_price || (pos.entry_price * 1.15),
                stop: pos.stop_loss || (pos.entry_price * 0.95)
            }));

            this.updatePositionsTable(positions);
            this.addLogEntry(`Loaded ${positions.length} active positions`);
        } catch (error) {
            console.error('Failed to load positions:', error);
            this.addLogEntry(`Error loading positions: ${error.message}`);
            // Show empty table on error
            this.updatePositionsTable([]);
        }
    }

    updatePositionsTable(positions) {
        const tbody = document.getElementById('positions-tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (positions.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td colspan="8" style="text-align: center; padding: 2rem; color: var(--fg-secondary);">
                    No active positions. Start the scanner to begin trading.
                </td>
            `;
            tbody.appendChild(row);
        } else {
            positions.forEach(pos => {
                const pnl = (pos.current - pos.entry) * pos.shares;
                const pnlPercent = ((pos.current - pos.entry) / pos.entry) * 100;

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${pos.symbol}</td>
                    <td>${pos.shares}</td>
                    <td>$${pos.entry.toFixed(2)}</td>
                    <td>$${pos.current.toFixed(2)}</td>
                    <td class="${pnl >= 0 ? 'positive' : 'negative'}">${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}</td>
                    <td class="${pnlPercent >= 0 ? 'positive' : 'negative'}">${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(1)}%</td>
                    <td>$${pos.target.toFixed(2)}</td>
                    <td>$${pos.stop.toFixed(2)}</td>
                `;
                tbody.appendChild(row);
            });
        }

        // Update active positions count (this is always updated from performance API)
    }

    async loadPerformance() {
        try {
            // Call real API endpoint for performance metrics
            const response = await fetch(`${this.apiBaseUrl}/trading/phase2-progress`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // Transform API response to dashboard format
            const performance = {
                totalPnl: data.total_pnl || data.realized_pnl || 0,
                winRate: data.win_rate || 0,
                totalTrades: data.total_trades || data.completed_trades || 0,
                wins: data.winning_trades || data.wins || 0,
                losses: data.losing_trades || data.losses || 0,
                activePositions: data.active_positions || 0
            };

            this.updatePerformanceMetrics(performance);
            this.addLogEntry(`Performance updated: ${performance.totalTrades} trades, ${performance.winRate.toFixed(1)}% win rate`);
        } catch (error) {
            console.error('Failed to load performance:', error);
            this.addLogEntry(`Error loading performance: ${error.message}`);
            // Keep showing zeros on error
        }
    }

    updatePerformanceMetrics(data) {
        const elements = {
            'total-pnl': `${data.totalPnl >= 0 ? '+' : ''}$${Math.abs(data.totalPnl).toFixed(2)}`,
            'win-rate': `${data.winRate.toFixed(1)}%`,
            'total-trades': data.totalTrades,
            'wins': data.wins,
            'losses': data.losses,
            'active-positions': data.activePositions
        };

        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
                // Add color classes for P&L
                if (id === 'total-pnl') {
                    element.className = data.totalPnl >= 0 ? 'metric-value positive' : 'metric-value negative';
                }
            }
        });
    }

    async loadMemorySystem() {
        try {
            // Try to load memory data from API (if endpoint exists)
            // For now, show empty state since memory system needs to be built up through trading
            const activeTickers = document.getElementById('active-tickers');
            const monitoredTickers = document.getElementById('monitored-tickers');
            const ejectedTickers = document.getElementById('ejected-tickers');
            
            if (activeTickers) {
                activeTickers.innerHTML = '<div class="memory-item" style="text-align: center; padding: 2rem; color: var(--fg-secondary);">No active tickers yet. Start trading to build memory.</div>';
            }
            if (monitoredTickers) {
                monitoredTickers.innerHTML = '<div class="memory-item" style="text-align: center; padding: 2rem; color: var(--fg-secondary);">No monitored tickers.</div>';
            }
            if (ejectedTickers) {
                ejectedTickers.innerHTML = '<div class="memory-item" style="text-align: center; padding: 2rem; color: var(--fg-secondary);">No ejected tickers.</div>';
            }
            
            this.addLogEntry('Memory system initialized (empty state)');
        } catch (error) {
            console.error('Failed to load memory system:', error);
            this.addLogEntry(`Error loading memory: ${error.message}`);
        }
    }

    // Event listeners
    setupEventListeners() {
        // Memory system tabs
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const tabName = e.target.getAttribute('onclick').match(/'([^']+)'/)[1];
                this.showMemoryTab(tabName);
            });
        });
    }

    // Memory system tabs
    showMemoryTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');

        // Update content
        document.querySelectorAll('.memory-list').forEach(list => {
            list.classList.remove('active');
        });
        document.getElementById(`${tabName}-tickers`).classList.add('active');
    }

    // Scanner controls
    toggleScanner() {
        this.scannerRunning = !this.scannerRunning;

        const button = document.getElementById('start-scanner-btn');
        const statusIndicator = document.querySelector('.status-indicator');
        const statusText = document.querySelector('.status-text');
        const systemStatus = document.getElementById('system-status');

        if (this.scannerRunning) {
            button.innerHTML = '⏹️ STOP SCANNER';
            button.classList.remove('primary');
            button.classList.add('secondary');
            statusIndicator.classList.remove('stopped');
            statusIndicator.classList.add('running');
            statusText.textContent = 'Scanner Running';
            if (systemStatus) systemStatus.innerHTML = '<span class="status-indicator running">●</span> Running';
            this.addLogEntry('Scanner started');
        } else {
            button.innerHTML = '▶️ START SCANNER';
            button.classList.remove('secondary');
            button.classList.add('primary');
            statusIndicator.classList.remove('running');
            statusIndicator.classList.add('stopped');
            statusText.textContent = 'Scanner Stopped';
            if (systemStatus) systemStatus.innerHTML = '<span class="status-indicator stopped">●</span> Ready';
            this.addLogEntry('Scanner stopped');
        }
    }

    refreshData() {
        this.addLogEntry('Manual data refresh initiated');
        this.loadInitialData();
    }

    showSettings() {
        // Navigate to settings page
        window.location.href = 'settings.html';
    }

    // Logging
    addLogEntry(message) {
        const logsContainer = document.getElementById('logs-container');
        if (!logsContainer) return;

        const now = new Date();
        const timeString = now.toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.textContent = `[${timeString}] ${message}`;

        logsContainer.appendChild(logEntry);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    // Periodic updates
    startPeriodicUpdates() {
        // Update time every second
        setInterval(() => {
            this.updateTime();
        }, 1000);
        
        // Update data every 5 seconds when scanner is running
        this.updateInterval = setInterval(() => {
            if (this.scannerRunning) {
                this.loadMarketData();
                this.loadAccountInfo();
                this.loadBrokerStatus();
                this.loadPositions();
                this.loadPerformance();
            }
        }, 5000); // Update every 5 seconds
        
        // Update data every 30 seconds when scanner is stopped
        setInterval(() => {
            if (!this.scannerRunning) {
                this.loadMarketData();
                this.loadAccountInfo();
                this.loadBrokerStatus();
                this.loadPositions();
                this.loadPerformance();
            }
        }, 30000); // Update every 30 seconds
    }

    // Cleanup
    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.pnlChart) {
            this.pnlChart.destroy();
        }
    }

    // Chart Rendering
    renderPnLChart() {
        const canvas = document.getElementById('pnl-chart');
        if (!canvas) return;

        // Destroy existing chart
        if (this.pnlChart) {
            this.pnlChart.destroy();
        }

        const ctx = canvas.getContext('2d');

        // Generate sample data (replace with real API data later)
        const dates = this.generateDateLabels(14);
        const pnlData = this.generatePnLData(dates.length);

        // Create gradient
        const gradient = ctx.createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, 'rgba(0, 255, 136, 0.3)');
        gradient.addColorStop(0.5, 'rgba(0, 212, 255, 0.1)');
        gradient.addColorStop(1, 'rgba(255, 46, 99, 0.1)');

        this.pnlChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Cumulative P&L',
                    data: pnlData,
                    borderColor: function(context) {
                        const value = context.parsed?.y;
                        return value >= 0 ? '#00ff88' : '#ff2e63';
                    },
                    backgroundColor: gradient,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 8,
                    pointBackgroundColor: '#0a0e27',
                    pointBorderWidth: 2,
                    pointBorderColor: function(context) {
                        const value = context.parsed?.y;
                        return value >= 0 ? '#00ff88' : '#ff2e63';
                    },
                    pointHoverBorderWidth: 3,
                    segment: {
                        borderColor: function(context) {
                            const value = context.p1.parsed.y;
                            return value >= 0 ? '#00ff88' : '#ff2e63';
                        }
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#e0e0e0',
                            font: {
                                size: 13,
                                family: "'Segoe UI', 'Arial', sans-serif",
                                weight: '500'
                            },
                            usePointStyle: true,
                            padding: 15
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(10, 14, 39, 0.95)',
                        borderColor: '#00d4ff',
                        borderWidth: 1,
                        titleColor: '#00d4ff',
                        bodyColor: '#e0e0e0',
                        padding: 12,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                const value = context.parsed.y;
                                const prefix = value >= 0 ? '+$' : '-$';
                                return 'P&L: ' + prefix + Math.abs(value).toFixed(2);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#a0a0a0',
                            font: {
                                size: 11
                            }
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#a0a0a0',
                            font: {
                                size: 11
                            },
                            callback: function(value) {
                                return (value >= 0 ? '+$' : '-$') + Math.abs(value).toFixed(0);
                            }
                        },
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // Helper: Generate date labels
    generateDateLabels(days) {
        const labels = [];
        const today = new Date();
        for (let i = days - 1; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
        }
        return labels;
    }

    // Helper: Generate P&L data
    generatePnLData(length) {
        const data = [];
        let cumulative = 0;
        for (let i = 0; i < length; i++) {
            const dailyPnL = (Math.random() - 0.45) * 50; // Slight upward bias
            cumulative += dailyPnL;
            data.push(Math.round(cumulative * 100) / 100);
        }
        return data;
    }
}

// Global functions for HTML onclick handlers
function toggleScanner() {
    if (window.dashboard) {
        window.dashboard.toggleScanner();
    }
}

function refreshData() {
    if (window.dashboard) {
        window.dashboard.refreshData();
    }
}

function showSettings() {
    if (window.dashboard) {
        window.dashboard.showSettings();
    }
}

function showMemoryTab(tabName) {
    if (window.dashboard) {
        window.dashboard.showMemoryTab(tabName);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new AutoTraderDashboard();
    // Render chart after a short delay to ensure DOM is ready
    setTimeout(() => {
        if (window.dashboard) {
            window.dashboard.renderPnLChart();
        }
    }, 500);
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.dashboard) {
        window.dashboard.destroy();
    }
});