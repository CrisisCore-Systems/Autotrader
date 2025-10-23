class ReportsManager {
    constructor() {
        this.currentReport = null;
        this.templates = this.loadTemplates();
        this.apiBaseUrl = 'http://localhost:8001/api';
        this.currentPage = 1;
        this.tradesPerPage = 10;
        this.allTrades = [];
        this.initialize();
    }

    initialize() {
        this.setupEventListeners();
        this.initializeCharts();
        this.loadTradeHistory();
        this.startRealTimeUpdates();
    }

    setupEventListeners() {
        // Date range selector
        const dateRangeSelect = document.getElementById('date-range');
        if (dateRangeSelect) {
            dateRangeSelect.addEventListener('change', (e) => {
                this.toggleCustomDateRange(e.target.value === 'custom');
            });
        }

        // Search functionality
        const searchInput = document.getElementById('trade-search');
        if (searchInput) {
            searchInput.addEventListener('input', () => this.filterTrades());
        }

        // Sort functionality
        const sortSelect = document.getElementById('sort-by');
        if (sortSelect) {
            sortSelect.addEventListener('change', () => this.sortTrades());
        }

        // Table pagination
        this.setupPagination();
    }

    toggleCustomDateRange(show) {
        const customRange = document.getElementById('custom-date-range');
        if (customRange) {
            customRange.style.display = show ? 'block' : 'none';
        }
    }

    initializeCharts() {
        this.initializePerformanceChart();
    }

    initializePerformanceChart() {
        const ctx = document.getElementById('performance-chart');
        if (!ctx) return;

        this.charts = this.charts || {};
        this.charts.performance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.generateDateLabels(30),
                datasets: [{
                    label: 'Daily P&L',
                    data: this.generatePerformanceData(),
                    borderColor: '#4ade80',
                    backgroundColor: 'rgba(74, 222, 128, 0.1)',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Cumulative P&L',
                    data: this.generateCumulativeData(),
                    borderColor: '#60a5fa',
                    backgroundColor: 'rgba(96, 165, 250, 0.1)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y1'
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
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af',
                            callback: function(value) {
                                return '$' + value;
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {
                            drawOnChartArea: false,
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9ca3af',
                            callback: function(value) {
                                return '$' + value.toLocaleString();
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

    generatePerformanceData() {
        const data = [];
        for (let i = 0; i < 30; i++) {
            // Generate realistic daily P&L with some volatility
            const pnl = (Math.random() - 0.45) * 800; // Bias toward positive
            data.push(Math.round(pnl * 100) / 100);
        }
        return data;
    }

    generateCumulativeData() {
        const dailyData = this.generatePerformanceData();
        const cumulative = [];
        let total = 0;

        dailyData.forEach(day => {
            total += day;
            cumulative.push(Math.round(total * 100) / 100);
        });

        return cumulative;
    }

    loadTemplates() {
        return {
            'basic-trade-history': {
                name: 'Basic Trade History',
                description: 'Simple list of all trades with basic details',
                config: {
                    columns: ['date', 'symbol', 'side', 'quantity', 'price', 'pnl'],
                    filters: {},
                    sort: 'date-desc'
                }
            },
            'detailed-performance': {
                name: 'Detailed Performance',
                description: 'Comprehensive performance analysis with charts',
                config: {
                    includeCharts: true,
                    metrics: ['total-pnl', 'win-rate', 'avg-win', 'avg-loss', 'sharpe-ratio'],
                    period: 'monthly'
                }
            },
            'tax-1099b': {
                name: 'Tax Report (1099-B)',
                description: 'IRS-ready tax reporting format',
                config: {
                    format: '1099b',
                    includeFees: true,
                    washSales: true
                }
            },
            'risk-analysis': {
                name: 'Risk Analysis',
                description: 'Detailed risk metrics and exposure analysis',
                config: {
                    metrics: ['var', 'max-drawdown', 'beta', 'volatility'],
                    timeframe: 'monthly'
                }
            },
            'strategy-comparison': {
                name: 'Strategy Comparison',
                description: 'Compare performance across different strategies',
                config: {
                    strategies: ['BounceHunter', 'PennyHunter', 'MeanReversion'],
                    metrics: ['pnl', 'win-rate', 'max-drawdown']
                }
            }
        };
    }

    filterTrades() {
        const searchTerm = document.getElementById('trade-search').value.toLowerCase();
        const rows = document.querySelectorAll('#trade-table-body tr');

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            const matches = text.includes(searchTerm);
            row.style.display = matches ? '' : 'none';
        });

        this.updatePaginationInfo();
    }

    sortTrades() {
        const sortBy = document.getElementById('sort-by').value;
        const tbody = document.getElementById('trade-table-body');
        const rows = Array.from(tbody.querySelectorAll('tr'));

        rows.sort((a, b) => {
            let aVal, bVal;

            switch (sortBy) {
                case 'date-desc':
                    aVal = new Date(a.cells[0].textContent);
                    bVal = new Date(b.cells[0].textContent);
                    return bVal - aVal;
                case 'date-asc':
                    aVal = new Date(a.cells[0].textContent);
                    bVal = new Date(b.cells[0].textContent);
                    return aVal - bVal;
                case 'pnl-desc':
                    aVal = parseFloat(a.cells[5].textContent.replace(/[+$]/g, ''));
                    bVal = parseFloat(b.cells[5].textContent.replace(/[+$]/g, ''));
                    return bVal - aVal;
                case 'pnl-asc':
                    aVal = parseFloat(a.cells[5].textContent.replace(/[+$]/g, ''));
                    bVal = parseFloat(b.cells[5].textContent.replace(/[+$]/g, ''));
                    return aVal - bVal;
                case 'symbol':
                    aVal = a.cells[1].textContent;
                    bVal = b.cells[1].textContent;
                    return aVal.localeCompare(bVal);
                default:
                    return 0;
            }
        });

        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
    }

    setupPagination() {
        const pageButtons = document.querySelectorAll('.page-number');
        pageButtons.forEach(button => {
            button.addEventListener('click', () => {
                // Remove active class from all buttons
                pageButtons.forEach(btn => btn.classList.remove('active'));
                // Add active class to clicked button
                button.classList.add('active');
                this.loadPage(parseInt(button.textContent));
            });
        });
    }

    loadPage(pageNumber) {
        // In a real implementation, this would load data for the specific page
        console.log(`Loading page ${pageNumber}`);
        this.updatePaginationInfo();
    }

    updatePaginationInfo() {
        const visibleRows = document.querySelectorAll('#trade-table-body tr:not([style*="display: none"])');
        const totalRows = document.querySelectorAll('#trade-table-body tr').length;

        const paginationInfo = document.querySelector('.pagination-info');
        if (paginationInfo) {
            paginationInfo.textContent = `Showing 1-${visibleRows.length} of ${totalRows} trades`;
        }
    }

    async loadTradeHistory() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/trading/history?limit=1000`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.allTrades = data.trades || [];
            
            // Update summary cards
            this.updateSummary(data.summary);
            
            // Render trades table
            this.renderTradesTable();
            
        } catch (error) {
            console.error('Failed to load trade history:', error);
            // Show error in table
            const tbody = document.getElementById('trade-table-body');
            if (tbody) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="9" style="text-align: center; padding: 2rem; color: var(--fg-secondary);">
                            Failed to load trade history. Make sure the API server is running.
                        </td>
                    </tr>
                `;
            }
        }
    }

    updateSummary(summary) {
        const summaryValues = document.querySelectorAll('.summary-value');
        if (summaryValues.length >= 2 && summary) {
            // Total P&L
            const pnl = summary.total_pnl || 0;
            summaryValues[0].textContent = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
            summaryValues[0].className = `summary-value ${pnl >= 0 ? 'positive' : 'negative'}`;
            
            // Win Rate
            const winRate = summary.win_rate || 0;
            summaryValues[1].textContent = `${winRate.toFixed(1)}%`;
            summaryValues[1].className = `summary-value ${winRate >= 60 ? 'positive' : 'negative'}`;
        }
    }

    renderTradesTable() {
        const tbody = document.getElementById('trade-table-body');
        if (!tbody) return;

        if (this.allTrades.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; padding: 2rem; color: var(--fg-secondary);">
                        No trades yet. Start trading to see history here.
                    </td>
                </tr>
            `;
            return;
        }

        // Pagination
        const startIdx = (this.currentPage - 1) * this.tradesPerPage;
        const endIdx = startIdx + this.tradesPerPage;
        const pageTrades = this.allTrades.slice(startIdx, endIdx);

        tbody.innerHTML = '';
        pageTrades.forEach(trade => {
            const pnl = trade.pnl || 0;
            const isProfitable = pnl > 0;
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${this.formatTimestamp(trade.timestamp)}</td>
                <td><strong>${trade.symbol}</strong></td>
                <td class="${trade.side === 'BUY' ? 'positive' : 'negative'}">${trade.side}</td>
                <td>${trade.quantity}</td>
                <td>$${(trade.entry_price || 0).toFixed(2)}</td>
                <td class="${isProfitable ? 'positive' : 'negative'}">
                    ${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}
                </td>
                <td>${trade.strategy || 'PennyHunter'}</td>
                <td><span class="status-badge ${trade.status}">${this.capitalizeFirst(trade.status)}</span></td>
                <td><button class="action-btn" onclick="viewTradeDetails('${trade.id}')">View</button></td>
            `;
            tbody.appendChild(row);
        });

        // Update pagination
        this.updatePagination();
    }

    updatePagination() {
        const totalPages = Math.ceil(this.allTrades.length / this.tradesPerPage);
        const paginationDiv = document.querySelector('.pagination');
        if (!paginationDiv) return;

        let paginationHTML = '';
        
        // Previous button
        if (this.currentPage > 1) {
            paginationHTML += `<button onclick="window.reportsManager.changePage(${this.currentPage - 1})">« Previous</button>`;
        }

        // Page numbers
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= this.currentPage - 2 && i <= this.currentPage + 2)) {
                const activeClass = i === this.currentPage ? 'active' : '';
                paginationHTML += `<button class="${activeClass}" onclick="window.reportsManager.changePage(${i})">${i}</button>`;
            } else if (i === this.currentPage - 3 || i === this.currentPage + 3) {
                paginationHTML += `<span>...</span>`;
            }
        }

        // Next button
        if (this.currentPage < totalPages) {
            paginationHTML += `<button onclick="window.reportsManager.changePage(${this.currentPage + 1})">Next »</button>`;
        }

        paginationHTML += `<span style="margin-left: 1rem; color: var(--fg-secondary);">
            Showing ${(this.currentPage - 1) * this.tradesPerPage + 1}-${Math.min(this.currentPage * this.tradesPerPage, this.allTrades.length)} of ${this.allTrades.length} trades
        </span>`;

        paginationDiv.innerHTML = paginationHTML;
    }

    changePage(page) {
        this.currentPage = page;
        this.renderTradesTable();
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';
        const date = new Date(timestamp);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }

    capitalizeFirst(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    }

    startRealTimeUpdates() {
        // Reload trade history every 30 seconds
        setInterval(() => {
            this.loadTradeHistory();
        }, 30000);
    }
}

// Global functions for HTML onclick handlers
function generateReport() {
    const reportType = document.getElementById('report-type').value;
    const dateRange = document.getElementById('date-range').value;
    const format = document.getElementById('format').value;

    // Show loading state
    const button = document.querySelector('button[onclick="generateReport()"]');
    const originalText = button.textContent;
    button.textContent = 'Generating...';
    button.disabled = true;

    // Simulate report generation
    setTimeout(() => {
        button.textContent = originalText;
        button.disabled = false;

        // Show success message
        showNotification(`Report generated successfully! Downloaded as ${reportType}_${dateRange}.${format}`, 'success');
    }, 3000);
}

function previewReport() {
    const reportType = document.getElementById('report-type').value;

    // Open preview in new window/tab
    const previewWindow = window.open('', '_blank');
    previewWindow.document.write(`
        <html>
        <head>
            <title>Report Preview - ${reportType}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }
                .preview-content { color: #666; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>${reportType.replace('-', ' ').toUpperCase()} - PREVIEW</h1>
                <p>Generated: ${new Date().toLocaleString()}</p>
            </div>
            <div class="preview-content">
                <p>This is a preview of the ${reportType} report.</p>
                <p>In a real implementation, this would show the actual report content.</p>
                <p>Report format: ${document.getElementById('format').value.toUpperCase()}</p>
                <p>Date range: ${document.getElementById('date-range').value}</p>
            </div>
        </body>
        </html>
    `);
}

function scheduleReport() {
    // Open schedule dialog (simplified)
    const scheduleName = prompt('Enter schedule name:');
    if (scheduleName) {
        const frequency = prompt('How often? (daily/weekly/monthly):');
        if (frequency) {
            showNotification(`Report "${scheduleName}" scheduled for ${frequency} generation`, 'success');
        }
    }
}

function saveTemplate() {
    const templateName = prompt('Enter template name:');
    if (templateName) {
        showNotification(`Template "${templateName}" saved successfully`, 'success');
    }
}

function generateQuickReport(type) {
    const reports = {
        'daily-pnl': 'Daily P&L Report',
        'weekly-summary': 'Weekly Summary',
        'monthly-review': 'Monthly Review',
        'tax-document': 'Tax Document',
        'risk-report': 'Risk Report',
        'performance': 'Performance Report'
    };

    const reportName = reports[type];
    showNotification(`${reportName} generated and downloaded`, 'success');
}

function viewTradeDetails(tradeId) {
    // Open trade details modal (simplified)
    const details = `Trade Details for ${tradeId}:
- Symbol: CLOV
- Side: BUY
- Quantity: 50
- Price: $1.23
- P&L: +$245.30
- Strategy: BounceHunter
- Status: Filled
- Timestamp: 2025-10-22 14:25:30`;

    alert(details);
}

function exportTable() {
    showNotification('Trade table exported to CSV', 'success');
}

function editSchedule(scheduleId) {
    alert(`Editing schedule: ${scheduleId}`);
}

function deleteSchedule(scheduleId) {
    if (confirm(`Are you sure you want to delete the "${scheduleId}" schedule?`)) {
        showNotification('Schedule deleted successfully', 'success');
        // In real implementation, remove from DOM
    }
}

function addNewSchedule() {
    alert('Add new schedule functionality would open a dialog here');
}

function loadTemplate(templateId) {
    if (window.reportsManager && window.reportsManager.templates[templateId]) {
        const template = window.reportsManager.templates[templateId];

        // Apply template settings to form
        document.getElementById('report-type').value = templateId;

        showNotification(`Template "${template.name}" loaded`, 'success');
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.reportsManager = new ReportsManager();
});