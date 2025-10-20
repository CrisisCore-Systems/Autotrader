#!/usr/bin/env python
"""
Generate Trade Journal Excel Template

Creates a formatted Excel spreadsheet for tracking paper trading performance.
"""

import pandas as pd
from datetime import datetime
from pathlib import Path

def create_trade_journal():
    """Create trade journal Excel template."""
    
    # Create reports directory
    Path("reports").mkdir(exist_ok=True)
    
    # Sample data (empty template with 1 example row)
    data = {
        'Date': [datetime.now().strftime('%Y-%m-%d')],
        'Ticker': ['COMP'],
        'Entry': [7.50],
        'Stop': [7.13],
        'Target': [8.25],
        'Size (%)': [1.0],
        'Confidence': [6.5],
        'Regime': ['NORMAL'],
        'Sentinel': ['✅'],
        'Screener': ['✅'],
        'Forecaster': ['✅'],
        'RiskOfficer': ['✅'],
        'NewsSentry': ['✅'],
        'Trader': ['✅'],
        'Consensus': [1.00],
        'Outcome': ['TARGET'],
        'Exit': [8.25],
        'Return (%)': [10.0],
        'P&L ($)': [75.00],
        'Notes': ['Perfect gap bounce, high volume confirmation'],
    }
    
    df = pd.DataFrame(data)
    
    # Create Excel writer
    output_path = "reports/paper_trading_journal.xlsx"
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Write main journal
        df.to_excel(writer, sheet_name='Trade Journal', index=False)
        
        # Create summary sheet
        summary_data = {
            'Metric': [
                'Total Trades',
                'Wins',
                'Losses',
                'Win Rate (%)',
                'Avg Win (%)',
                'Avg Loss (%)',
                'Profit Factor',
                'Total P&L ($)',
                'Total Return (%)',
                'Max Drawdown (%)',
                'Avg Hold Time (days)',
                'Best Trade ($)',
                'Worst Trade ($)',
            ],
            'Value': [
                '=COUNTA(\'Trade Journal\'!B:B)-1',  # Count non-empty tickers
                '=COUNTIF(\'Trade Journal\'!P:P,"TARGET")+COUNTIF(\'Trade Journal\'!P:P,"MANUAL_WIN")',
                '=COUNTIF(\'Trade Journal\'!P:P,"STOP")+COUNTIF(\'Trade Journal\'!P:P,"TIME")',
                '=B2/(B2+B3)*100',
                '=AVERAGEIF(\'Trade Journal\'!R:R,">0",\'Trade Journal\'!R:R)',
                '=AVERAGEIF(\'Trade Journal\'!R:R,"<0",\'Trade Journal\'!R:R)',
                '=SUMIF(\'Trade Journal\'!R:R,">0",\'Trade Journal\'!S:S)/ABS(SUMIF(\'Trade Journal\'!R:R,"<0",\'Trade Journal\'!S:S))',
                '=SUM(\'Trade Journal\'!S:S)',
                '=(SUM(\'Trade Journal\'!S:S)/25000)*100',
                '=MIN(\'Trade Journal\'!R:R)',
                '=AVERAGE(\'Trade Journal\'!A:A)',  # Placeholder
                '=MAX(\'Trade Journal\'!S:S)',
                '=MIN(\'Trade Journal\'!S:S)',
            ],
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Create agent performance sheet
        agent_data = {
            'Agent': [
                'Sentinel',
                'Screener', 
                'Forecaster',
                'RiskOfficer',
                'NewsSentry',
                'Trader',
            ],
            'Total Votes': [
                '=COUNTA(\'Trade Journal\'!I:I)-1',
                '=COUNTA(\'Trade Journal\'!J:J)-1',
                '=COUNTA(\'Trade Journal\'!K:K)-1',
                '=COUNTA(\'Trade Journal\'!L:L)-1',
                '=COUNTA(\'Trade Journal\'!M:M)-1',
                '=COUNTA(\'Trade Journal\'!N:N)-1',
            ],
            'Approvals': [
                '=COUNTIF(\'Trade Journal\'!I:I,"✅")',
                '=COUNTIF(\'Trade Journal\'!J:J,"✅")',
                '=COUNTIF(\'Trade Journal\'!K:K,"✅")',
                '=COUNTIF(\'Trade Journal\'!L:L,"✅")',
                '=COUNTIF(\'Trade Journal\'!M:M,"✅")',
                '=COUNTIF(\'Trade Journal\'!N:N,"✅")',
            ],
            'Vetoes': [
                '=COUNTIF(\'Trade Journal\'!I:I,"❌")',
                '=COUNTIF(\'Trade Journal\'!J:J,"❌")',
                '=COUNTIF(\'Trade Journal\'!K:K,"❌")',
                '=COUNTIF(\'Trade Journal\'!L:L,"❌")',
                '=COUNTIF(\'Trade Journal\'!M:M,"❌")',
                '=COUNTIF(\'Trade Journal\'!N:N,"❌")',
            ],
            'Approval Rate (%)': [
                '=C2/B2*100',
                '=C3/B3*100',
                '=C4/B4*100',
                '=C5/B5*100',
                '=C6/B6*100',
                '=C7/B7*100',
            ],
            'Weight': [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        }
        
        agent_df = pd.DataFrame(agent_data)
        agent_df.to_excel(writer, sheet_name='Agent Performance', index=False)
        
        # Format columns
        workbook = writer.book
        
        # Format Trade Journal sheet
        worksheet = writer.sheets['Trade Journal']
        worksheet.column_dimensions['A'].width = 12  # Date
        worksheet.column_dimensions['B'].width = 8   # Ticker
        worksheet.column_dimensions['C'].width = 8   # Entry
        worksheet.column_dimensions['D'].width = 8   # Stop
        worksheet.column_dimensions['E'].width = 8   # Target
        worksheet.column_dimensions['F'].width = 10  # Size
        worksheet.column_dimensions['G'].width = 11  # Confidence
        worksheet.column_dimensions['H'].width = 10  # Regime
        worksheet.column_dimensions['I'].width = 9   # Sentinel
        worksheet.column_dimensions['J'].width = 9   # Screener
        worksheet.column_dimensions['K'].width = 10  # Forecaster
        worksheet.column_dimensions['L'].width = 11  # RiskOfficer
        worksheet.column_dimensions['M'].width = 11  # NewsSentry
        worksheet.column_dimensions['N'].width = 8   # Trader
        worksheet.column_dimensions['O'].width = 10  # Consensus
        worksheet.column_dimensions['P'].width = 10  # Outcome
        worksheet.column_dimensions['Q'].width = 8   # Exit
        worksheet.column_dimensions['R'].width = 11  # Return %
        worksheet.column_dimensions['S'].width = 10  # P&L $
        worksheet.column_dimensions['T'].width = 40  # Notes
        
        # Format Summary sheet
        summary_ws = writer.sheets['Summary']
        summary_ws.column_dimensions['A'].width = 25
        summary_ws.column_dimensions['B'].width = 15
        
        # Format Agent Performance sheet
        agent_ws = writer.sheets['Agent Performance']
        agent_ws.column_dimensions['A'].width = 15
        agent_ws.column_dimensions['B'].width = 12
        agent_ws.column_dimensions['C'].width = 12
        agent_ws.column_dimensions['D'].width = 10
        agent_ws.column_dimensions['E'].width = 18
        agent_ws.column_dimensions['F'].width = 10
    
    print(f"✅ Trade journal template created: {output_path}")
    print(f"\n📋 Instructions:")
    print(f"   1. Open {output_path} in Excel")
    print(f"   2. Delete the example row (COMP)")
    print(f"   3. Add your trades as they execute")
    print(f"   4. Agent columns: Use ✅ for approve, ❌ for veto")
    print(f"   5. Outcome: TARGET, STOP, TIME, MANUAL_WIN, MANUAL_LOSS")
    print(f"   6. Summary tab auto-calculates performance metrics")
    print(f"   7. Agent Performance tab tracks each agent's accuracy")


if __name__ == "__main__":
    create_trade_journal()
