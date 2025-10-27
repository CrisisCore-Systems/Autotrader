const apiBaseUrl = 'http://localhost:8001/api';

class AnalyticsManager {
    constructor() {
        this.charts = {};
        this.currentAnalysisTab = 'distribution';
        this.accountInfo = null;
        this.initialize();
    }

    initialize() {
        this.loadAccountInfo();
        this.setupEventListeners();
        this.initializeCharts();
        this.updateData();
        this.startRealTimeUpdates();
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
                        accountValue: ibkr.account_value || 0
                    };
                    
                    // Update header account ID
                    const accountIdEl = document.getElementById('account-id');
                    if (accountIdEl) {
                        accountIdEl.textContent = this.accountInfo.accountId;
                    }
                }
            }
        } catch (error) {
            console.error('Error loading account info:', error);
        }
    }

    setupEventListeners() {
        // Timeframe selector
        const timeframeSelect = document.getElementById('timeframe-select');
        if (timeframeSelect) {
            timeframeSelect.addEventListener('change', () => this.updateEquityChart());
        }

        // Chart legend toggles
        document.querySelectorAll('.legend-toggle input').forEach(toggle => {
            toggle.addEventListener('change', () => this.updateEquityChart());
        });

        // Analysis tabs
        document.querySelectorAll('.analysis-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.target.textContent.toLowerCase();
                this.showAnalysisTab(tabName);
            });
        });

        // Strategy selector
        const strategySelect = document.getElementById('strategy-select');
        if (strategySelect) {
            strategySelect.addEventListener('change', () => this.updateBacktestResults());
        }
    }

    initializeCharts() {
        this.initializeEquityChart();
        this.initializePnLDistributionChart();
        this.initializeTradeTimelineChart();
        this.initializeBacktestChart();
    }

    initializeEquityChart() {
        const ctx = document.getElementById('equity-chart');
        if (!ctx) return;

        this.charts.equity = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.generateDateLabels(365),
                datasets: [{
                    label: 'Portfolio Value',
                    data: this.generateEquityData(),
                    borderColor: '#4ade80',
                    backgroundColor: 'rgba(74, 222, 128, 0.1)',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Benchmark (SPY)',
                    data: this.generateBenchmarkData(),
                    borderColor: '#60a5fa',
                    backgroundColor: 'rgba(96, 165, 250, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false // Using custom legend
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af'
                        }
                    },
                    y: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af',
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }

    initializePnLDistributionChart() {
        const ctx = document.getElementById('pnl-distribution-chart');
        if (!ctx) return;

        const pnlData = this.generatePnLDistributionData();

        this.charts.pnlDistribution = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: pnlData.labels,
                datasets: [{
                    label: 'Trade P&L',
                    data: pnlData.values,
                    backgroundColor: pnlData.colors,
                    borderColor: pnlData.borderColors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af'
                        }
                    },
                    y: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af',
                            callback: function(value) {
                                return '$' + value;
                            }
                        }
                    }
                }
            }
        });
    }

    initializeTradeTimelineChart() {
        const ctx = document.getElementById('trade-timeline-chart');
        if (!ctx) return;

        const timelineData = this.generateTradeTimelineData();

        this.charts.tradeTimeline = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Winning Trades',
                    data: timelineData.wins,
                    backgroundColor: '#4ade80',
                    pointRadius: 6
                }, {
                    label: 'Losing Trades',
                    data: timelineData.losses,
                    backgroundColor: '#f87171',
                    pointRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day'
                        },
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af'
                        }
                    },
                    y: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af',
                            callback: function(value) {
                                return '$' + value;
                            }
                        }
                    }
                }
            }
        });
    }

    initializeBacktestChart() {
        const ctx = document.getElementById('backtest-chart');
        if (!ctx) return;

        this.charts.backtest = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.generateDateLabels(252), // Trading days in a year
                datasets: [{
                    label: 'Strategy Performance',
                    data: this.generateBacktestData(),
                    borderColor: '#fbbf24',
                    backgroundColor: 'rgba(251, 191, 36, 0.1)',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Buy & Hold',
                    data: this.generateBuyHoldData(),
                    borderColor: '#9ca3af',
                    backgroundColor: 'rgba(156, 163, 175, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af'
                        }
                    },
                    y: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af',
                            callback: function(value) {
                                return (value * 100).toFixed(1) + '%';
                            }
                        }
                    }
                }
            }
        });
    }

    generateDateLabels(days) {
        const labels = [];
        const today = new Date();

        for (let i = days - 1; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            labels.push(date.toISOString().split('T')[0]);
        }

        return labels;
    }

    generateEquityData() {
        const data = [];
        let value = 10000; // Starting value

        for (let i = 0; i < 365; i++) {
            // Simulate daily returns with some volatility
            const dailyReturn = (Math.random() - 0.48) * 0.02; // Slightly positive bias
            value *= (1 + dailyReturn);
            data.push(Math.round(value * 100) / 100);
        }

        return data;
    }

    generateBenchmarkData() {
        const data = [];
        let value = 10000;

        for (let i = 0; i < 365; i++) {
            const dailyReturn = (Math.random() - 0.5) * 0.015; // Market-like volatility
            value *= (1 + dailyReturn);
            data.push(Math.round(value * 100) / 100);
        }

        return data;
    }

    generatePnLDistributionData() {
        // Simulate 23 trades
        const trades = [];
        for (let i = 0; i < 23; i++) {
            const pnl = (Math.random() - 0.4) * 400; // Bias toward positive
            trades.push(Math.round(pnl * 100) / 100);
        }

        // Group into bins
        const bins = [-200, -100, -50, 0, 50, 100, 200, 300];
        const labels = ['<-200', '-200 to -100', '-100 to -50', '-50 to 0', '0 to 50', '50 to 100', '100 to 200', '>200'];
        const values = new Array(bins.length).fill(0);
        const colors = [];
        const borderColors = [];

        trades.forEach(trade => {
            let binIndex = bins.length - 1;
            for (let i = 0; i < bins.length - 1; i++) {
                if (trade < bins[i + 1]) {
                    binIndex = i;
                    break;
                }
            }
            values[binIndex]++;

            if (trade >= 0) {
                colors.push('rgba(74, 222, 128, 0.7)');
                borderColors.push('#4ade80');
            } else {
                colors.push('rgba(248, 113, 113, 0.7)');
                borderColors.push('#f87171');
            }
        });

        return { labels, values, colors, borderColors };
    }

    generateTradeTimelineData() {
        const wins = [];
        const losses = [];
        const startDate = new Date();
        startDate.setMonth(startDate.getMonth() - 1);

        for (let i = 0; i < 23; i++) {
            const tradeDate = new Date(startDate);
            tradeDate.setDate(tradeDate.getDate() + Math.floor(Math.random() * 30));

            const pnl = (Math.random() - 0.4) * 400;

            const trade = {
                x: tradeDate,
                y: pnl
            };

            if (pnl >= 0) {
                wins.push(trade);
            } else {
                losses.push(trade);
            }
        }

        return { wins, losses };
    }

    generateBacktestData() {
        const data = [];
        let value = 1; // Starting at 100%

        for (let i = 0; i < 252; i++) {
            const dailyReturn = (Math.random() - 0.45) * 0.03; // Strategy returns
            value *= (1 + dailyReturn);
            data.push(value - 1); // Convert to percentage return
        }

        return data;
    }

    generateBuyHoldData() {
        const data = [];
        let value = 1;

        for (let i = 0; i < 252; i++) {
            const dailyReturn = (Math.random() - 0.5) * 0.02; // Buy & hold returns
            value *= (1 + dailyReturn);
            data.push(value - 1);
        }

        return data;
    }

    showAnalysisTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.analysis-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelectorAll('.analysis-tab').forEach(tab => {
            if (tab.textContent.toLowerCase() === tabName) {
                tab.classList.add('active');
            }
        });

        // Update content views
        document.querySelectorAll('.analysis-view').forEach(view => {
            view.classList.remove('active');
        });

        const viewId = `${tabName}-view`;
        const viewElement = document.getElementById(viewId);
        if (viewElement) {
            viewElement.classList.add('active');
        }

        this.currentAnalysisTab = tabName;
    }

    updateEquityChart() {
        if (!this.charts.equity) return;

        const timeframe = document.getElementById('timeframe-select').value;
        const showPortfolio = document.querySelector('.legend-toggle input:nth-child(1)').checked;
        const showBenchmark = document.querySelector('.legend-toggle input:nth-child(2)').checked;

        // Update datasets visibility
        this.charts.equity.data.datasets[0].hidden = !showPortfolio;
        this.charts.equity.data.datasets[1].hidden = !showBenchmark;

        this.charts.equity.update();
    }

    updateBacktestResults() {
        const strategy = document.getElementById('strategy-select').value;

        // Simulate different results for different strategies
        const results = {
            'bouncehunter': {
                totalReturn: '+24.7%',
                annualReturn: '+18.3%',
                maxDrawdown: '-15.2%',
                winRate: '67.8%',
                profitFactor: '1.65',
                totalTrades: '156'
            },
            'pennyhunter': {
                totalReturn: '+31.2%',
                annualReturn: '+22.1%',
                maxDrawdown: '-18.7%',
                winRate: '71.3%',
                profitFactor: '1.89',
                totalTrades: '203'
            },
            'mean-reversion': {
                totalReturn: '+15.8%',
                annualReturn: '+12.4%',
                maxDrawdown: '-12.1%',
                winRate: '63.2%',
                profitFactor: '1.34',
                totalTrades: '89'
            }
        };

        const result = results[strategy];
        const metrics = document.querySelectorAll('.backtest-metric .metric-value');

        metrics[0].textContent = result.totalReturn;
        metrics[1].textContent = result.annualReturn;
        metrics[2].textContent = result.maxDrawdown;
        metrics[3].textContent = result.winRate;
        metrics[4].textContent = result.profitFactor;
        metrics[5].textContent = result.totalTrades;

        // Update chart data
        this.charts.backtest.data.datasets[0].data = this.generateBacktestData();
        this.charts.backtest.update();
    }

    async updateData() {
        // Load real performance metrics from API
        try {
            const response = await fetch(`${apiBaseUrl}/trading/phase2-progress`);
            const data = await response.json();
            
            const metrics = document.querySelectorAll('.metric-value');
            if (metrics.length > 0 && data.metrics) {
                // Update metrics from API
                if (data.metrics.total_return !== undefined) {
                    metrics[0].textContent = `${data.metrics.total_return >= 0 ? '+' : ''}${data.metrics.total_return.toFixed(2)}%`;
                }
                if (data.metrics.win_rate !== undefined) {
                    metrics[1].textContent = `${data.metrics.win_rate.toFixed(1)}%`;
                }
            }
            
            // Update account info in header
            this.loadAccountInfo();
        } catch (error) {
            console.error('Error loading analytics data:', error);
        }
    }

    startRealTimeUpdates() {
        // Update data every 30 seconds
        setInterval(() => {
            this.updateData();
            this.loadAccountInfo();
        }, 30000);
    }
}

// Global functions for HTML onclick handlers
function showAnalysisTab(tabName) {
    if (window.analyticsManager) {
        window.analyticsManager.showAnalysisTab(tabName);
    }
}

function runBacktest() {
    // Simulate running a backtest
    const button = document.querySelector('button[onclick="runBacktest()"]');
    const originalText = button.textContent;
    button.textContent = 'Running...';
    button.disabled = true;

    setTimeout(() => {
        button.textContent = originalText;
        button.disabled = false;

        // Show success message
        const notification = document.createElement('div');
        notification.className = 'notification success';
        notification.textContent = 'Backtest completed successfully!';
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }, 2000);
}

function exportResults() {
    // Simulate exporting results
    const notification = document.createElement('div');
    notification.className = 'notification info';
    notification.textContent = 'Exporting results to CSV...';
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.textContent = 'Results exported successfully!';
        notification.className = 'notification success';

        setTimeout(() => {
            notification.remove();
        }, 2000);
    }, 1500);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.analyticsManager = new AnalyticsManager();
});