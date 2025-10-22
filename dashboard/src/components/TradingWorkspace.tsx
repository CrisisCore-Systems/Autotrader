/**
 * TradingWorkspace Component
 * Main trading interface combining all trading panels
 */

import React, { useState } from 'react';
import { TradingRunboard } from './TradingRunboard';
import { SignalsQueue } from './SignalsQueue';
import { OrdersPanel } from './OrdersPanel';
import { PositionsPanel } from './PositionsPanel';
import { BrokerStatus } from './BrokerStatus';
import './TradingWorkspace.css';

interface Signal {
  ticker: string;
  entry_price: number;
  stop_price: number;
  target_price: number;
  risk_reward: number;
}

export const TradingWorkspace: React.FC = () => {
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  const handleSelectSignal = (signal: any) => {
    setSelectedSignal({
      ticker: signal.ticker,
      entry_price: signal.entry_price,
      stop_price: signal.stop_price,
      target_price: signal.target_price,
      risk_reward: signal.risk_reward,
    });
  };

  return (
    <div className="trading-workspace">
      <div className="workspace-header">
        <h1>Trading Workspace</h1>
        <p className="workspace-subtitle">BounceHunter / PennyHunter Paper Trading</p>
      </div>

      {/* Runboard showing regime and Phase 2 progress */}
      <TradingRunboard />

      {/* Two-column layout for signals and orders */}
      <div className="workspace-main">
        <div className="left-column">
          <SignalsQueue onSelectSignal={handleSelectSignal} />
          <BrokerStatus />
        </div>

        <div className="right-column">
          <OrdersPanel selectedSignal={selectedSignal} />
          <PositionsPanel />
        </div>
      </div>
    </div>
  );
};
