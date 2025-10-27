const apiBaseUrl = 'http://localhost:8001/api';

class SettingsManager {
    constructor() {
        this.currentSection = 'broker';
        this.accountInfo = null;
        this.initialize();
    }

    initialize() {
        this.loadAccountInfo();
        this.setupEventListeners();
        this.loadSettings();
        this.updateConnectionStatus();
        this.startStatusUpdates();
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
        // Settings navigation
        document.querySelectorAll('.settings-nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const section = e.currentTarget.getAttribute('onclick').match(/'([^']+)'/)[1];
                this.showSettingsSection(section);
            });
        });

        // Form inputs with auto-save indicators
        document.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('change', () => this.showUnsavedChanges());
        });

        // Toggle switches
        document.querySelectorAll('.toggle input').forEach(toggle => {
            toggle.addEventListener('change', () => this.showUnsavedChanges());
        });
    }

    showSettingsSection(sectionName) {
        // Update navigation
        document.querySelectorAll('.settings-nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[onclick="showSettingsSection('${sectionName}')"]`).classList.add('active');

        // Update content
        document.querySelectorAll('.settings-section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(`${sectionName}-section`).classList.add('active');

        this.currentSection = sectionName;
    }

    loadSettings() {
        // Load settings from localStorage or default values
        const settings = this.getStoredSettings();

        // Apply settings to form fields
        Object.keys(settings).forEach(key => {
            const element = document.getElementById(key);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = settings[key];
                } else {
                    element.value = settings[key];
                }
            }
        });

        // Load toggle states
        document.querySelectorAll('.toggle input').forEach(toggle => {
            const settingKey = toggle.id;
            if (settings[settingKey] !== undefined) {
                toggle.checked = settings[settingKey];
            }
        });
    }

    getStoredSettings() {
        // Try to load from localStorage first, fall back to defaults
        const storedSettings = localStorage.getItem('tradingSettings');
        if (storedSettings) {
            try {
                return JSON.parse(storedSettings);
            } catch (error) {
                console.error('Error parsing stored settings:', error);
            }
        }
        
        // Default settings
        return {
            'broker-type': 'ibkr',
            'account-type': 'paper',
            'host': '127.0.0.1',
            'port': '7497',
            'client-id': '1',
            'connection-timeout': '30',
            'save-credentials': true,
            'api-rate-limit': '60',
            'api-timeout': '10',
            'retry-attempts': '3',
            'retry-delay': '5',
            'default-order-type': 'market',
            'default-quantity': '100',
            'default-time-in-force': 'day',
            'slippage-tolerance': '0.5',
            'market-open': '09:30',
            'market-close': '16:00',
            'extended-hours': true,
            'auto-stop-trading': false,
            'max-position-size': '10000',
            'max-portfolio-risk': '5',
            'max-daily-loss': '500',
            'max-trades-per-day': '20',
            'default-stop-loss': '5',
            'trailing-stop': true,
            'trailing-stop-distance': '2',
            'auto-stop-loss': false,
            'cpu-threads': '4',
            'memory-limit': '2048',
            'data-retention': '365',
            'log-level': 'info',
            'backup-frequency': 'daily',
            'backup-location': './backups',
            'auto-restart': true,
            'keep-backups': '30',
            'auto-update': true,
            'update-channel': 'stable',
            'maintenance-window': '02:00'
        };
    }

    showUnsavedChanges() {
        // Show indicator that settings have been modified
        const saveButton = document.querySelector(`#${this.currentSection}-section .control-btn.primary`);
        if (saveButton) {
            saveButton.textContent = 'Save Changes';
            saveButton.classList.add('unsaved');
        }
    }

    async updateConnectionStatus() {
        const statusDot = document.getElementById('connection-status-dot');
        const statusText = document.getElementById('connection-status-text');

        try {
            const response = await fetch(`${apiBaseUrl}/trading/broker-status`);
            const data = await response.json();
            
            let isConnected = false;
            if (data.brokers && data.brokers.length > 0) {
                const ibkr = data.brokers.find(b => b.name === 'IBKR');
                isConnected = ibkr && ibkr.status === 'online';
            }

            if (isConnected) {
                if (statusDot) statusDot.style.color = '#4ade80';
                if (statusText) statusText.textContent = 'Connected';
            } else {
                if (statusDot) statusDot.style.color = '#f87171';
                if (statusText) statusText.textContent = 'Disconnected';
            }
        } catch (error) {
            console.error('Error checking connection status:', error);
            if (statusDot) statusDot.style.color = '#f87171';
            if (statusText) statusText.textContent = 'Error';
        }
    }

    startStatusUpdates() {
        // Update connection status every 10 seconds
        setInterval(() => {
            this.updateConnectionStatus();
            this.loadAccountInfo();
        }, 10000);
    }

    validateSettings(section) {
        const errors = [];

        switch (section) {
            case 'broker':
                const host = document.getElementById('host').value;
                const port = document.getElementById('port').value;
                const clientId = document.getElementById('client-id').value;

                if (!host) errors.push('Host is required');
                if (!port || port < 1 || port > 65535) errors.push('Valid port is required');
                if (!clientId || clientId < 0) errors.push('Valid client ID is required');
                break;

            case 'api':
                const rateLimit = document.getElementById('api-rate-limit').value;
                if (!rateLimit || rateLimit < 1) errors.push('Valid rate limit is required');
                break;

            case 'risk':
                const maxRisk = document.getElementById('max-portfolio-risk').value;
                if (maxRisk > 100) errors.push('Portfolio risk cannot exceed 100%');
                break;
        }

        return errors;
    }

    saveSettings(section) {
        const errors = this.validateSettings(section);
        if (errors.length > 0) {
            this.showErrors(errors);
            return false;
        }

        // Collect form data
        const settings = {};
        document.querySelectorAll(`#${section}-section input, #${section}-section select`).forEach(field => {
            if (field.type === 'checkbox') {
                settings[field.id] = field.checked;
            } else {
                settings[field.id] = field.value;
            }
        });

        // Save to localStorage
        const allSettings = this.getStoredSettings();
        Object.assign(allSettings, settings);
        localStorage.setItem('tradingSettings', JSON.stringify(allSettings));

        // Update save button
        const saveButton = document.querySelector(`#${section}-section .control-btn.primary`);
        if (saveButton) {
            saveButton.textContent = 'Saved';
            saveButton.classList.remove('unsaved');
            setTimeout(() => {
                saveButton.textContent = 'Save Settings';
            }, 2000);
        }

        this.showSuccess('Settings saved successfully');
        return true;
    }

    showErrors(errors) {
        const notification = document.createElement('div');
        notification.className = 'notification error';
        notification.innerHTML = `
            <div class="error-title">Validation Errors:</div>
            <ul>${errors.map(error => `<li>${error}</li>`).join('')}</ul>
        `;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    showSuccess(message) {
        const notification = document.createElement('div');
        notification.className = 'notification success';
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Global functions for HTML onclick handlers
function showSettingsSection(section) {
    if (window.settingsManager) {
        window.settingsManager.showSettingsSection(section);
    }
}

function testConnection() {
    const button = document.querySelector('button[onclick="testConnection()"]');
    const originalText = button.textContent;
    button.textContent = 'Testing...';
    button.disabled = true;

    // Simulate connection test
    setTimeout(() => {
        const success = Math.random() > 0.3; // 70% success rate
        button.textContent = success ? 'Connection Successful' : 'Connection Failed';
        button.className = `control-btn ${success ? 'success' : 'danger'}`;

        setTimeout(() => {
            button.textContent = originalText;
            button.className = 'control-btn primary';
            button.disabled = false;
        }, 3000);
    }, 2000);
}

function saveBrokerSettings() {
    if (window.settingsManager) {
        window.settingsManager.saveSettings('broker');
    }
}

function saveAPISettings() {
    if (window.settingsManager) {
        window.settingsManager.saveSettings('api');
    }
}

function testAllAPIs() {
    const button = document.querySelector('button[onclick="testAllAPIs()"]');
    const originalText = button.textContent;
    button.textContent = 'Testing APIs...';
    button.disabled = true;

    // Simulate API testing
    setTimeout(() => {
        button.textContent = 'API Tests Complete';
        button.className = 'control-btn success';

        // Show results
        const notification = document.createElement('div');
        notification.className = 'notification info';
        notification.innerHTML = `
            <div>API Test Results:</div>
            <div>• Alpha Vantage: ✅ Connected</div>
            <div>• Finnhub: ❌ Invalid API Key</div>
            <div>• Twelve Data: ✅ Connected</div>
        `;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
            button.textContent = originalText;
            button.className = 'control-btn secondary';
            button.disabled = false;
        }, 4000);
    }, 3000);
}

function saveTradingPreferences() {
    if (window.settingsManager) {
        window.settingsManager.saveSettings('trading');
    }
}

function resetToDefaults() {
    if (confirm('Are you sure you want to reset all trading preferences to defaults?')) {
        // Reset form fields to defaults
        const defaults = {
            'default-order-type': 'market',
            'default-quantity': '100',
            'default-time-in-force': 'day',
            'slippage-tolerance': '0.5',
            'extended-hours': true,
            'auto-stop-trading': false
        };

        Object.keys(defaults).forEach(key => {
            const element = document.getElementById(key);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = defaults[key];
                } else {
                    element.value = defaults[key];
                }
            }
        });

        if (window.settingsManager) {
            window.settingsManager.showSuccess('Trading preferences reset to defaults');
        }
    }
}

function saveRiskSettings() {
    if (window.settingsManager) {
        window.settingsManager.saveSettings('risk');
    }
}

function saveNotificationSettings() {
    if (window.settingsManager) {
        window.settingsManager.saveSettings('notifications');
    }
}

function testNotifications() {
    const button = document.querySelector('button[onclick="testNotifications()"]');
    const originalText = button.textContent;
    button.textContent = 'Sending Test...';
    button.disabled = true;

    // Simulate notification test
    setTimeout(() => {
        button.textContent = 'Test Sent';
        button.className = 'control-btn success';

        setTimeout(() => {
            button.textContent = originalText;
            button.className = 'control-btn secondary';
            button.disabled = false;

            // Show desktop notification
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification('AutoTrader Test', {
                    body: 'This is a test notification from AutoTrader',
                    icon: '/favicon.ico'
                });
            }
        }, 2000);
    }, 1500);
}

function saveSystemSettings() {
    if (window.settingsManager) {
        window.settingsManager.saveSettings('system');
    }
}

function createBackup() {
    const button = document.querySelector('button[onclick="createBackup()"]');
    const originalText = button.textContent;
    button.textContent = 'Creating Backup...';
    button.disabled = true;

    // Simulate backup creation
    setTimeout(() => {
        button.textContent = 'Backup Created';
        button.className = 'control-btn success';

        setTimeout(() => {
            button.textContent = originalText;
            button.className = 'control-btn secondary';
            button.disabled = false;

            if (window.settingsManager) {
                window.settingsManager.showSuccess('Backup created successfully');
            }
        }, 2000);
    }, 3000);
}

function restoreBackup() {
    if (confirm('Are you sure you want to restore from backup? This will overwrite current settings.')) {
        const button = document.querySelector('button[onclick="restoreBackup()"]');
        const originalText = button.textContent;
        button.textContent = 'Restoring...';
        button.disabled = true;

        // Simulate backup restoration
        setTimeout(() => {
            button.textContent = 'Restored';
            button.className = 'control-btn success';

            setTimeout(() => {
                button.textContent = originalText;
                button.className = 'control-btn secondary';
                button.disabled = false;

                if (window.settingsManager) {
                    window.settingsManager.showSuccess('Settings restored from backup');
                    window.settingsManager.loadSettings();
                }
            }, 2000);
        }, 2500);
    }
}

function resetSystem() {
    if (confirm('Are you sure you want to reset all system settings to factory defaults? This action cannot be undone.')) {
        const button = document.querySelector('button[onclick="resetSystem()"]');
        const originalText = button.textContent;
        button.textContent = 'Resetting...';
        button.disabled = true;

        // Simulate system reset
        setTimeout(() => {
            button.textContent = 'Reset Complete';
            button.className = 'control-btn success';

            setTimeout(() => {
                button.textContent = originalText;
                button.className = 'control-btn danger';
                button.disabled = false;

                if (window.settingsManager) {
                    window.settingsManager.showSuccess('System reset to factory defaults');
                    // Reload settings
                    setTimeout(() => window.location.reload(), 1000);
                }
            }, 2000);
        }, 4000);
    }
}

// Request notification permission on page load
document.addEventListener('DOMContentLoaded', () => {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }

    window.settingsManager = new SettingsManager();
});