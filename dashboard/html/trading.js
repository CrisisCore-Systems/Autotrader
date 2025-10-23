// Trading Interface JavaScript
// Handles scanner controls, order placement, and trading operations

const apiBaseUrl = 'http://localhost:8001/api';

class TradingInterface {
    constructor() {
        this.scannerRunning = false;
        this.pendingOrders = [];
        this.activityLog = [];
        this.accountInfo = null;
        this.init();
    }

    init() {
        this.loadAccountInfo();
        this.loadSignals();
        this.loadPendingOrders();
        this.loadActivityLog();
        this.updateRiskMetrics();
        this.startPeriodicUpdates();
    }

    startPeriodicUpdates() {
        // Refresh data every 30 seconds
        setInterval(() => {
            this.loadAccountInfo();
            if (this.scannerRunning) {
                this.loadSignals();
            }
            this.loadPendingOrders();
            this.updateRiskMetrics();
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

    // Scanner Controls
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
            this.addActivityLog('Scanner', 'STARTED', 'Monitoring tickers');
            this.startScannerLoop();
        } else {
            button.innerHTML = '▶️ START SCANNER';
            button.classList.remove('secondary');
            button.classList.add('primary');
            statusIndicator.classList.remove('running');
            statusIndicator.classList.add('stopped');
            statusText.textContent = 'Scanner Stopped';
            if (systemStatus) systemStatus.innerHTML = '<span class="status-indicator stopped">●</span> Ready';
            this.addActivityLog('Scanner', 'STOPPED', 'Scanner halted');
            this.stopScannerLoop();
        }
    }

    runSingleScan() {
        this.addActivityLog('Scanner', 'SCAN', 'Single scan initiated');
        // Simulate scan operation
        setTimeout(() => {
            this.addActivityLog('Scanner', 'COMPLETE', 'Scan found 2 signals');
            this.refreshSignals();
        }, 2000);
    }

    stopScanner() {
        if (this.scannerRunning) {
            this.toggleScanner();
        }
    }

    startScannerLoop() {
        // Simulate periodic scanning
        this.scannerInterval = setInterval(() => {
            if (this.scannerRunning) {
                this.performScan();
            }
        }, 30000); // Scan every 30 seconds
    }

    stopScannerLoop() {
        if (this.scannerInterval) {
            clearInterval(this.scannerInterval);
        }
    }

    performScan() {
        // Simulate scan operation
        const tickers = document.getElementById('scanner-tickers').value.split(',').map(t => t.trim());
        const minScore = parseFloat(document.getElementById('min-score').value);

        // Simulate finding signals
        const mockSignals = [
            { symbol: 'CLOV', score: 7.2, entry: 12.50, target: 14.00, stop: 11.50 },
            { symbol: 'TXMD', score: 6.8, entry: 0.85, target: 1.00, stop: 0.70 }
        ].filter(signal => signal.score >= minScore);

        if (mockSignals.length > 0) {
            this.addActivityLog('Scanner', 'SIGNALS', `Found ${mockSignals.length} signals`);
            this.updateSignals(mockSignals);
        }
    }

    // Signals Management
    async loadSignals() {
        try {
            const response = await fetch(`${apiBaseUrl}/trading/signals`);
            const data = await response.json();
            const signals = data.signals || [];
            this.updateSignals(signals);
        } catch (error) {
            console.error('Error loading signals:', error);
            this.updateSignals([]);
        }
    }

    updateSignals(signals) {
        const signalsList = document.getElementById('signals-list');
        if (!signalsList) return;

        signalsList.innerHTML = '';

        signals.forEach(signal => {
            const signalItem = document.createElement('div');
            signalItem.className = 'signal-item';
            signalItem.innerHTML = `
                <div class="signal-header">
                    <span class="signal-symbol">${signal.symbol}</span>
                    <span class="signal-score">${signal.score}</span>
                </div>
                <div class="signal-details">
                    <span>Entry: $${signal.entry.toFixed(2)}</span>
                    <span>Target: $${signal.target.toFixed(2)}</span>
                    <span>Stop: $${signal.stop.toFixed(2)}</span>
                </div>
                <div class="signal-actions">
                    <button class="signal-btn buy" onclick="placeOrder('${signal.symbol}', 'BUY', ${signal.entry}, ${Math.floor(1000/signal.entry)})">
                        BUY
                    </button>
                </div>
            `;
            signalsList.appendChild(signalItem);
        });
    }

    refreshSignals() {
        this.loadSignals();
    }

    // Order Management
    submitOrder(event) {
        event.preventDefault();

        const symbol = document.getElementById('order-symbol').value.toUpperCase();
        const action = document.getElementById('order-action').value;
        const quantity = parseInt(document.getElementById('order-quantity').value);
        const price = parseFloat(document.getElementById('order-price').value);
        const type = document.getElementById('order-type').value;

        // Create order object
        const order = {
            id: Date.now().toString(),
            symbol,
            action,
            quantity,
            price,
            type,
            status: 'PENDING',
            timestamp: new Date()
        };

        // Add to pending orders
        this.pendingOrders.push(order);
        this.updatePendingOrders();

        // Add to activity log
        this.addActivityLog(symbol, action, `${quantity} shares @ $${price.toFixed(2)} (${type})`);

        // Reset form
        event.target.reset();

        // Simulate order execution
        setTimeout(() => {
            this.executeOrder(order.id);
        }, 2000);
    }

    placeOrder(symbol, action, price, quantity) {
        // Auto-fill order form
        document.getElementById('order-symbol').value = symbol;
        document.getElementById('order-action').value = action;
        document.getElementById('order-price').value = price;
        document.getElementById('order-quantity').value = quantity;

        // Submit the form
        document.getElementById('order-form').dispatchEvent(new Event('submit'));
    }

    executeOrder(orderId) {
        const order = this.pendingOrders.find(o => o.id === orderId);
        if (order) {
            order.status = 'EXECUTED';
            this.updatePendingOrders();
            this.addActivityLog(order.symbol, 'EXECUTED', `${order.quantity} shares @ $${order.price.toFixed(2)}`);
        }
    }

    cancelOrder(orderId) {
        const orderIndex = this.pendingOrders.findIndex(o => o.id === orderId);
        if (orderIndex !== -1) {
            const order = this.pendingOrders[orderIndex];
            order.status = 'CANCELLED';
            this.updatePendingOrders();
            this.addActivityLog(order.symbol, 'CANCELLED', `Order cancelled`);
        }
    }

    async loadPendingOrders() {
        try {
            const response = await fetch(`${apiBaseUrl}/trading/orders?status=pending`);
            const data = await response.json();
            this.pendingOrders = data.orders || [];
            this.updatePendingOrders();
        } catch (error) {
            console.error('Error loading pending orders:', error);
            this.pendingOrders = [];
            this.updatePendingOrders();
        }
    }

    updatePendingOrders() {
        const ordersList = document.getElementById('pending-orders');
        if (!ordersList) return;

        const pendingOrders = this.pendingOrders.filter(order => order.status === 'PENDING');

        ordersList.innerHTML = '';

        if (pendingOrders.length === 0) {
            ordersList.innerHTML = '<div class="no-orders">No pending orders</div>';
            return;
        }

        pendingOrders.forEach(order => {
            const orderItem = document.createElement('div');
            orderItem.className = 'order-item';
            orderItem.innerHTML = `
                <div class="order-header">
                    <span class="order-symbol">${order.symbol}</span>
                    <span class="order-status ${order.status.toLowerCase()}">${order.status}</span>
                </div>
                <div class="order-details">
                    <span>${order.action} ${order.quantity} @ $${order.price.toFixed(2)}</span>
                    <span>${order.type}</span>
                </div>
                <div class="order-actions">
                    <button class="order-btn cancel" onclick="cancelOrder('${order.id}')">Cancel</button>
                </div>
            `;
            ordersList.appendChild(orderItem);
        });
    }

    // Activity Log
    loadActivityLog() {
        // Load recent activity
        this.updateActivityLog();
    }

    addActivityLog(symbol, action, details) {
        const activity = {
            time: new Date().toLocaleTimeString(),
            symbol,
            action,
            details
        };

        this.activityLog.unshift(activity);
        if (this.activityLog.length > 50) {
            this.activityLog = this.activityLog.slice(0, 50);
        }

        this.updateActivityLog();
    }

    updateActivityLog() {
        const activityList = document.getElementById('activity-list');
        if (!activityList) return;

        activityList.innerHTML = '';

        this.activityLog.slice(0, 10).forEach(activity => {
            const activityItem = document.createElement('div');
            activityItem.className = 'activity-item';
            activityItem.innerHTML = `
                <div class="activity-time">${activity.time}</div>
                <div class="activity-content">
                    <span class="activity-symbol">${activity.symbol}</span>
                    <span class="activity-action ${activity.action.toLowerCase()}">${activity.action}</span>
                    <span class="activity-details">${activity.details}</span>
                </div>
            `;
            activityList.appendChild(activityItem);
        });
    }

    // Risk Management
    updateRiskMetrics() {
        // Update risk display
        const riskMetrics = {
            'daily-loss-limit': '$500.00',
            'current-daily-pnl': '+$45.20',
            'max-positions-display': '5',
            'active-positions-count': '2'
        };

        Object.entries(riskMetrics).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
    }

    emergencyStop() {
        this.stopScanner();
        // Cancel all pending orders
        this.pendingOrders.forEach(order => {
            if (order.status === 'PENDING') {
                order.status = 'CANCELLED';
            }
        });
        this.updatePendingOrders();
        this.addActivityLog('System', 'EMERGENCY', 'Emergency stop activated - all operations halted');
        alert('Emergency stop activated! All scanner operations and pending orders cancelled.');
    }
}

// Global functions for HTML onclick handlers
function toggleScanner() {
    if (window.tradingInterface) {
        window.tradingInterface.toggleScanner();
    }
}

function runSingleScan() {
    if (window.tradingInterface) {
        window.tradingInterface.runSingleScan();
    }
}

function stopScanner() {
    if (window.tradingInterface) {
        window.tradingInterface.stopScanner();
    }
}

function submitOrder(event) {
    if (window.tradingInterface) {
        window.tradingInterface.submitOrder(event);
    }
}

function placeOrder(symbol, action, price, quantity) {
    if (window.tradingInterface) {
        window.tradingInterface.placeOrder(symbol, action, price, quantity);
    }
}

function cancelOrder(orderId) {
    if (window.tradingInterface) {
        window.tradingInterface.cancelOrder(orderId);
    }
}

function emergencyStop() {
    if (window.tradingInterface) {
        window.tradingInterface.emergencyStop();
    }
}

// Initialize trading interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.tradingInterface = new TradingInterface();
});