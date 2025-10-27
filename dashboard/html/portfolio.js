// Portfolio Management JavaScript
// Handles position tracking, P&L calculations, and portfolio analytics

const apiBaseUrl = 'http://localhost:8001/api';

class PortfolioManager {
    constructor() {
        this.positions = [];
        this.trades = [];
        this.currentView = 'table';
        this.currentFilter = 'all';
        this.accountInfo = null;
        this.init();
    }

    init() {
        this.loadAccountInfo();
        this.loadPositions();
        this.loadTrades();
        this.renderChart();
        this.startPeriodicUpdates();
    }

    startPeriodicUpdates() {
        // Refresh data every 30 seconds
        setInterval(() => {
            this.loadAccountInfo();
            this.loadPositions();
            this.loadTrades();
        }, 30000);
    }

    // Load account information
    async loadAccountInfo() {
        try {
            const response = await fetch(`${apiBaseUrl}/trading/broker-status`);
            const data = await response.json();
            
            if (data.brokers && data.brokers.length > 0) {
                const ibkr = data.brokers.find(b => b.name === 'IBKR');
                if (ibkr && ibkr.status === 'online') {
                    this.accountInfo = {
                        accountId: ibkr.account_id || '--',
                        accountValue: ibkr.account_value || 0,
                        cash: ibkr.cash_balance || 0
                    };
                    
                    // Update header account ID
                    const accountIdEl = document.getElementById('account-id');
                    if (accountIdEl) {
                        accountIdEl.textContent = this.accountInfo.accountId;
                    }
                    
                    this.updatePortfolioSummary();
                }
            }
        } catch (error) {
            console.error('Error loading account info:', error);
        }
    }

    // Data Loading
    async loadPositions() {
        try {
            const response = await fetch(`${apiBaseUrl}/trading/positions`);
            const data = await response.json();
            
            this.positions = (data.positions || []).map(pos => ({
                symbol: pos.symbol || pos.ticker,
                company: pos.company || pos.name || pos.symbol,
                shares: Math.abs(pos.position || pos.quantity || 0),
                avgCost: pos.avg_cost || pos.avgCost || pos.average_price || 0,
                currentPrice: pos.current_price || pos.market_price || pos.last || 0,
                marketValue: pos.market_value || pos.marketValue || 0,
                dayChange: pos.unrealized_pnl_percent || pos.pnl_percent || 0
            }));

            this.updatePositionsDisplay();
            this.updatePortfolioSummary();
        } catch (error) {
            console.error('Error loading positions:', error);
            this.positions = [];
            this.updatePositionsDisplay();
        }
    }

    async loadTrades() {
        try {
            const response = await fetch(`${apiBaseUrl}/trading/history?limit=50&status=all`);
            const data = await response.json();
            
            this.trades = (data.trades || []).map(trade => ({
                datetime: trade.timestamp || trade.datetime || trade.time,
                symbol: trade.symbol || trade.ticker,
                action: trade.action || trade.side || trade.type,
                quantity: Math.abs(trade.quantity || trade.shares || 0),
                price: trade.price || trade.fill_price || 0,
                total: trade.value || trade.total || 0,
                commission: trade.commission || trade.fees || 0
            }));

            this.updateTradesDisplay();
        } catch (error) {
            console.error('Error loading trades:', error);
            this.trades = [];
            this.updateTradesDisplay();
        }
    }

    // Portfolio Summary Calculations
    updatePortfolioSummary() {
        const totalPositionValue = this.positions.reduce((sum, pos) => sum + pos.marketValue, 0);
        const cash = this.accountInfo ? this.accountInfo.cash : 0;
        const totalValue = this.accountInfo ? this.accountInfo.accountValue : totalPositionValue + cash;
        const totalCost = this.positions.reduce((sum, pos) => sum + (pos.avgCost * pos.shares), 0);
        const totalPnl = this.positions.reduce((sum, pos) => sum + ((pos.currentPrice - pos.avgCost) * pos.shares), 0);
        const totalPnlPercent = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
        const dayPnl = this.positions.reduce((sum, pos) => sum + (pos.marketValue * pos.dayChange / 100), 0);

        // Update summary cards
        document.getElementById('total-value').textContent = totalValue > 0 ? `$${totalValue.toLocaleString()}` : '$--';
        document.getElementById('cash-available').textContent = cash > 0 ? `$${cash.toLocaleString()}` : '$--';
        document.getElementById('total-pnl').textContent = totalPnl !== 0 ? `$${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}` : '$--';
        document.getElementById('total-pnl').className = totalPnl >= 0 ? 'summary-value positive' : 'summary-value negative';
        document.getElementById('total-pnl-percent').textContent = totalPnlPercent !== 0 ? `${totalPnlPercent >= 0 ? '+' : ''}${totalPnlPercent.toFixed(2)}%` : '--';
        document.getElementById('total-pnl-percent').className = totalPnlPercent >= 0 ? 'summary-value positive' : 'summary-value negative';
        document.getElementById('day-pnl').textContent = dayPnl !== 0 ? `$${dayPnl >= 0 ? '+' : ''}${dayPnl.toFixed(2)}` : '$--';
        document.getElementById('day-pnl').className = dayPnl >= 0 ? 'summary-value positive' : 'summary-value negative';
        document.getElementById('active-positions').textContent = this.positions.length;
    }

    // Positions Display
    updatePositionsDisplay() {
        this.updateTableView();
        this.updateCardsView();
    }

    updateTableView() {
        const tbody = document.getElementById('positions-tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        const filteredPositions = this.filterPositions();

        filteredPositions.forEach(position => {
            const unrealizedPnl = (position.currentPrice - position.avgCost) * position.shares;
            const pnlPercent = ((position.currentPrice - position.avgCost) / position.avgCost) * 100;

            const row = document.createElement('tr');
            row.setAttribute('data-symbol', position.symbol);
            row.innerHTML = `
                <td>
                    <div class="symbol-info">
                        <span class="symbol-name">${position.symbol}</span>
                        <span class="symbol-company">${position.company}</span>
                    </div>
                </td>
                <td>${position.shares}</td>
                <td>$${position.avgCost.toFixed(2)}</td>
                <td>$${position.currentPrice.toFixed(2)}</td>
                <td>$${position.marketValue.toLocaleString()}</td>
                <td class="${unrealizedPnl >= 0 ? 'positive' : 'negative'}">$${unrealizedPnl >= 0 ? '+' : ''}${unrealizedPnl.toFixed(2)}</td>
                <td class="${pnlPercent >= 0 ? 'positive' : 'negative'}">${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(1)}%</td>
                <td class="${position.dayChange >= 0 ? 'positive' : 'negative'}">${position.dayChange >= 0 ? '+' : ''}${position.dayChange.toFixed(1)}%</td>
                <td>
                    <div class="action-buttons">
                        <button class="action-btn sell" onclick="sellPosition('${position.symbol}')">Sell</button>
                        <button class="action-btn modify" onclick="modifyPosition('${position.symbol}')">Modify</button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    updateCardsView() {
        const cardsContainer = document.getElementById('positions-cards');
        if (!cardsContainer) return;

        cardsContainer.innerHTML = '';

        const filteredPositions = this.filterPositions();

        filteredPositions.forEach(position => {
            const unrealizedPnl = (position.currentPrice - position.avgCost) * position.shares;
            const pnlPercent = ((position.currentPrice - position.avgCost) / position.avgCost) * 100;

            const card = document.createElement('div');
            card.className = 'position-card';
            card.setAttribute('data-symbol', position.symbol);
            card.innerHTML = `
                <div class="card-header">
                    <div class="card-symbol">${position.symbol}</div>
                    <div class="card-company">${position.company}</div>
                </div>
                <div class="card-body">
                    <div class="card-metric">
                        <span class="metric-label">Shares:</span>
                        <span class="metric-value">${position.shares}</span>
                    </div>
                    <div class="card-metric">
                        <span class="metric-label">Avg Cost:</span>
                        <span class="metric-value">$${position.avgCost.toFixed(2)}</span>
                    </div>
                    <div class="card-metric">
                        <span class="metric-label">Current:</span>
                        <span class="metric-value">$${position.currentPrice.toFixed(2)}</span>
                    </div>
                    <div class="card-metric">
                        <span class="metric-label">P&L:</span>
                        <span class="metric-value ${unrealizedPnl >= 0 ? 'positive' : 'negative'}">$${unrealizedPnl >= 0 ? '+' : ''}${unrealizedPnl.toFixed(2)} (${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(1)}%)</span>
                    </div>
                </div>
                <div class="card-actions">
                    <button class="action-btn sell" onclick="sellPosition('${position.symbol}')">Sell</button>
                    <button class="action-btn modify" onclick="modifyPosition('${position.symbol}')">Modify</button>
                </div>
            `;
            cardsContainer.appendChild(card);
        });
    }

    filterPositions() {
        let filtered = [...this.positions];

        switch (this.currentFilter) {
            case 'profitable':
                filtered = filtered.filter(pos => (pos.currentPrice - pos.avgCost) > 0);
                break;
            case 'losing':
                filtered = filtered.filter(pos => (pos.currentPrice - pos.avgCost) < 0);
                break;
            default:
                // 'all' - no filtering
                break;
        }

        return filtered;
    }

    // View Switching
    toggleView(viewType, targetElement) {
        this.currentView = viewType;

        // Update view buttons
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        if (targetElement) {
            targetElement.classList.add('active');
        }

        // Update view containers
        document.querySelectorAll('.positions-view').forEach(view => {
            view.classList.remove('active');
        });
        document.getElementById(`positions-${viewType}-view`).classList.add('active');
    }

    // Filtering
    setFilter(filterType, targetElement) {
        this.currentFilter = filterType;

        // Update filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        if (targetElement) {
            targetElement.classList.add('active');
        }

        // Re-render current view
        if (this.currentView === 'table') {
            this.updateTableView();
        } else {
            this.updateCardsView();
        }
    }

    // Trades Display
    updateTradesDisplay() {
        const tbody = document.getElementById('trades-tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        this.trades.forEach(trade => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${trade.datetime}</td>
                <td>${trade.symbol}</td>
                <td class="action-${trade.action.toLowerCase()}">${trade.action}</td>
                <td>${trade.quantity}</td>
                <td>$${trade.price.toFixed(2)}</td>
                <td>$${trade.total.toLocaleString()}</td>
                <td>$${trade.commission.toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });
    }

    // Position Actions
    sellPosition(symbol) {
        const position = this.positions.find(p => p.symbol === symbol);
        if (!position) return;

        // Show sell dialog (simplified)
        const quantity = prompt(`Sell ${symbol} - Enter quantity (max: ${position.shares}):`, position.shares);
        if (!quantity || quantity <= 0 || quantity > position.shares) return;

        const price = prompt(`Enter sell price for ${symbol}:`, position.currentPrice);
        if (!price || price <= 0) return;

        // Execute sell
        this.executeSell(symbol, parseInt(quantity), parseFloat(price));
    }

    executeSell(symbol, quantity, price) {
        const position = this.positions.find(p => p.symbol === symbol);
        if (!position) return;

        // Create trade record
        const trade = {
            datetime: new Date().toLocaleString(),
            symbol: symbol,
            action: 'SELL',
            quantity: quantity,
            price: price,
            total: quantity * price,
            commission: 0.50
        };

        this.trades.unshift(trade);

        // Update position
        position.shares -= quantity;
        if (position.shares <= 0) {
            // Remove position if fully sold
            this.positions = this.positions.filter(p => p.symbol !== symbol);
        }

        // Refresh displays
        this.updatePositionsDisplay();
        this.updateTradesDisplay();
        this.updatePortfolioSummary();

        alert(`Sold ${quantity} shares of ${symbol} at $${price.toFixed(2)}`);
    }

    modifyPosition(symbol) {
        // Placeholder for position modification
        alert(`Modify position for ${symbol} - Feature coming soon!`);
    }

    // Chart Rendering with Chart.js
    renderChart() {
        const canvas = document.getElementById('portfolio-chart');
        if (!canvas) return;

        // Destroy existing chart if it exists
        if (this.performanceChart) {
            this.performanceChart.destroy();
        }

        // Generate sample performance data (replace with real API data)
        const dates = this.generateDateLabels(30);
        const portfolioData = this.generatePerformanceData(dates.length, 24750, 200);
        const benchmarkData = this.generatePerformanceData(dates.length, 25000, 100);

        // Create gradient for portfolio line
        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(0, 255, 136, 0.4)');
        gradient.addColorStop(1, 'rgba(0, 255, 136, 0.0)');

        this.performanceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Portfolio Value',
                        data: portfolioData,
                        borderColor: '#00ff88',
                        backgroundColor: gradient,
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: '#00ff88',
                        pointHoverBorderColor: '#0a0e27',
                        pointHoverBorderWidth: 2
                    },
                    {
                        label: 'S&P 500 Benchmark',
                        data: benchmarkData,
                        borderColor: '#00d4ff',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: '#00d4ff',
                        pointHoverBorderColor: '#0a0e27',
                        pointHoverBorderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
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
                                size: 12,
                                family: "'Segoe UI', 'Arial', sans-serif"
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
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += '$' + context.parsed.y.toLocaleString('en-US', {
                                        minimumFractionDigits: 2,
                                        maximumFractionDigits: 2
                                    });
                                }
                                return label;
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
                            },
                            maxRotation: 45,
                            minRotation: 0
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
                                return '$' + value.toLocaleString('en-US');
                            }
                        }
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

    // Helper: Generate performance data
    generatePerformanceData(length, startValue, variance) {
        const data = [];
        let value = startValue;
        for (let i = 0; i < length; i++) {
            const change = (Math.random() - 0.48) * variance;
            value += change;
            data.push(Math.round(value * 100) / 100);
        }
        return data;
    }
}

// Global functions for HTML onclick handlers
function toggleView(viewType, event) {
    if (window.portfolioManager) {
        window.portfolioManager.toggleView(viewType, event ? event.target : null);
    }
}

function filterPositions(filterType, event) {
    if (window.portfolioManager) {
        window.portfolioManager.setFilter(filterType, event ? event.target : null);
    }
}

function sellPosition(symbol) {
    if (window.portfolioManager) {
        window.portfolioManager.sellPosition(symbol);
    }
}

function modifyPosition(symbol) {
    if (window.portfolioManager) {
        window.portfolioManager.modifyPosition(symbol);
    }
}

// Initialize portfolio manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.portfolioManager = new PortfolioManager();
});