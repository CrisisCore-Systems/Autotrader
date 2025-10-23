/**
 * OrdersPanel Component
 * Paper order placement with two-step confirmation and order tracking
 */

import React, { useState, useEffect } from 'react';
import './OrdersPanel.css';

interface Order {
  order_id: string;
  ticker: string;
  side: string;
  order_type: string;
  quantity: number;
  filled_qty: number;
  limit_price: number | null;
  stop_price: number | null;
  filled_price: number | null;
  status: string;
  submitted_at: string | null;
  filled_at: string | null;
}

interface OrdersPanelProps {
  selectedSignal?: {
    ticker: string;
    entry_price: number;
    stop_price: number;
    target_price: number;
    risk_reward: number;
  } | null;
}

export const OrdersPanel: React.FC<OrdersPanelProps> = ({ selectedSignal }) => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Order form state
  const [ticker, setTicker] = useState('');
  const [quantity, setQuantity] = useState(100);
  const [entryPrice, setEntryPrice] = useState(0);
  const [stopPrice, setStopPrice] = useState(0);
  const [targetPrice, setTargetPrice] = useState(0);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [orderPreview, setOrderPreview] = useState<any>(null);

  useEffect(() => {
    if (selectedSignal) {
      setTicker(selectedSignal.ticker);
      setEntryPrice(selectedSignal.entry_price);
      setStopPrice(selectedSignal.stop_price);
      setTargetPrice(selectedSignal.target_price);
    }
  }, [selectedSignal]);

  useEffect(() => {
    fetchOrders();
    const interval = setInterval(fetchOrders, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchOrders = async () => {
    try {
      const res = await fetch('/api/trading/orders?limit=20');
      if (!res.ok) throw new Error('Failed to fetch orders');
      const data = await res.json();
      setOrders(data);
    } catch (err) {
      console.error('Error fetching orders:', err);
    }
  };

  const handlePlaceOrder = async () => {
    if (!ticker || quantity <= 0 || entryPrice <= 0 || stopPrice <= 0 || targetPrice <= 0) {
      setError('Please fill in all order fields');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/trading/paper-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker,
          quantity,
          entry_price: entryPrice,
          stop_price: stopPrice,
          target_price: targetPrice,
          confirmed: false,
        }),
      });

      if (!res.ok) throw new Error('Failed to place order');

      const data = await res.json();

      if (data.status === 'confirmation_required') {
        setOrderPreview(data.order_preview);
        setShowConfirmation(true);
      } else if (data.status === 'success') {
        setShowConfirmation(false);
        setOrderPreview(null);
        fetchOrders();
        // Reset form
        setTicker('');
        setQuantity(100);
        setEntryPrice(0);
        setStopPrice(0);
        setTargetPrice(0);
      }

      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  const handleConfirmOrder = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/trading/paper-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker,
          quantity,
          entry_price: entryPrice,
          stop_price: stopPrice,
          target_price: targetPrice,
          confirmed: true,
        }),
      });

      if (!res.ok) throw new Error('Failed to confirm order');

      const data = await res.json();

      if (data.status === 'success') {
        setShowConfirmation(false);
        setOrderPreview(null);
        fetchOrders();
        // Reset form
        setTicker('');
        setQuantity(100);
        setEntryPrice(0);
        setStopPrice(0);
        setTargetPrice(0);
      }

      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'filled':
        return '#10b981';
      case 'submitted':
      case 'pending':
        return '#3b82f6';
      case 'cancelled':
        return '#6b7280';
      case 'rejected':
        return '#ef4444';
      default:
        return '#a0a0a0';
    }
  };

  return (
    <div className="orders-panel">
      <h3>Paper Orders</h3>

      {/* Order Form */}
      <div className="order-form">
        <h4>Place Bracket Order</h4>

        <div className="form-row">
          <div className="form-field">
            <label>Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="TICKER"
            />
          </div>
          <div className="form-field">
            <label>Quantity</label>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(parseInt(e.target.value) || 0)}
              min="1"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-field">
            <label>Entry Price</label>
            <input
              type="number"
              value={entryPrice}
              onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
              step="0.01"
              min="0"
            />
          </div>
          <div className="form-field">
            <label>Stop Price</label>
            <input
              type="number"
              value={stopPrice}
              onChange={(e) => setStopPrice(parseFloat(e.target.value) || 0)}
              step="0.01"
              min="0"
            />
          </div>
          <div className="form-field">
            <label>Target Price</label>
            <input
              type="number"
              value={targetPrice}
              onChange={(e) => setTargetPrice(parseFloat(e.target.value) || 0)}
              step="0.01"
              min="0"
            />
          </div>
        </div>

        {error && <div className="error-message">{error}</div>}

        <button
          className="place-order-btn"
          onClick={handlePlaceOrder}
          disabled={loading}
        >
          {loading ? 'Processing...' : 'Place Order'}
        </button>
      </div>

      {/* Confirmation Modal */}
      {showConfirmation && orderPreview && (
        <div className="confirmation-modal">
          <div className="modal-content">
            <h4>Confirm Order</h4>
            <div className="order-summary">
              <div className="summary-row">
                <span>Ticker:</span>
                <strong>{orderPreview.ticker}</strong>
              </div>
              <div className="summary-row">
                <span>Quantity:</span>
                <strong>{orderPreview.quantity} shares</strong>
              </div>
              <div className="summary-row">
                <span>Entry:</span>
                <strong>${orderPreview.entry_price.toFixed(2)}</strong>
              </div>
              <div className="summary-row">
                <span>Stop:</span>
                <strong className="stop">${orderPreview.stop_price.toFixed(2)}</strong>
              </div>
              <div className="summary-row">
                <span>Target:</span>
                <strong className="target">${orderPreview.target_price.toFixed(2)}</strong>
              </div>
              <div className="summary-row highlight">
                <span>Risk Amount:</span>
                <strong>${orderPreview.risk_amount.toFixed(2)}</strong>
              </div>
              <div className="summary-row highlight">
                <span>Profit Target:</span>
                <strong>${orderPreview.profit_target.toFixed(2)}</strong>
              </div>
              <div className="summary-row highlight">
                <span>R:R Ratio:</span>
                <strong>{orderPreview.risk_reward_ratio.toFixed(2)}</strong>
              </div>
            </div>
            <div className="modal-actions">
              <button onClick={() => setShowConfirmation(false)} disabled={loading}>
                Cancel
              </button>
              <button className="confirm-btn" onClick={handleConfirmOrder} disabled={loading}>
                {loading ? 'Confirming...' : 'Confirm Order'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Orders List */}
      <div className="orders-list">
        <h4>Recent Orders</h4>
        {orders.length === 0 ? (
          <div className="no-orders">No orders yet</div>
        ) : (
          <div className="orders-table">
            <div className="table-header">
              <div className="col">Ticker</div>
              <div className="col">Type</div>
              <div className="col">Qty</div>
              <div className="col">Price</div>
              <div className="col">Status</div>
              <div className="col">Time</div>
            </div>
            {orders.map((order) => (
              <div key={order.order_id} className="table-row">
                <div className="col ticker">{order.ticker}</div>
                <div className="col">{order.side}</div>
                <div className="col">
                  {order.filled_qty}/{order.quantity}
                </div>
                <div className="col">
                  ${order.limit_price?.toFixed(2) || order.stop_price?.toFixed(2) || '-'}
                </div>
                <div className="col">
                  <span
                    className="status-badge"
                    style={{ backgroundColor: getStatusColor(order.status) }}
                  >
                    {order.status}
                  </span>
                </div>
                <div className="col time">
                  {order.submitted_at
                    ? new Date(order.submitted_at).toLocaleTimeString()
                    : '-'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
