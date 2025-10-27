"""
Market Hours Validator

Checks if US stock market is currently open and validates trading times.
Used by scheduled tasks to ensure operations only run during valid trading hours.
"""

from datetime import datetime, time
import pytz
import pandas_market_calendars as mcal


def is_market_open(tolerance_minutes=5):
    """
    Check if US stock market is currently open.
    
    Args:
        tolerance_minutes: Allow execution N minutes after close (for cleanup tasks)
    
    Returns:
        Tuple of (is_open: bool, status: str, next_open: datetime)
    """
    try:
        # Get NYSE calendar
        nyse = mcal.get_calendar('NYSE')
        
        # Get current time in ET
        et_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(et_tz)
        today = now_et.date()
        
        # Check if today is a trading day
        schedule = nyse.schedule(start_date=today, end_date=today)
        
        if schedule.empty:
            # Market closed today (weekend or holiday)
            next_schedule = nyse.schedule(start_date=today, end_date=today + pd.Timedelta(days=7))
            if not next_schedule.empty:
                next_open = next_schedule.iloc[0]['market_open']
                return False, f"Market closed (holiday/weekend). Next open: {next_open}", next_open
            return False, "Market closed", None
        
        # Get today's market hours
        market_open = schedule.iloc[0]['market_open'].to_pydatetime()
        market_close = schedule.iloc[0]['market_close'].to_pydatetime()
        
        # Add tolerance for after-hours cleanup
        close_with_tolerance = market_close + pd.Timedelta(minutes=tolerance_minutes)
        
        # Check current status
        if now_et < market_open:
            minutes_until_open = (market_open - now_et).total_seconds() / 60
            return False, f"Pre-market: Opens in {minutes_until_open:.0f} minutes", market_open
        elif now_et > close_with_tolerance:
            return False, f"After-hours: Closed at {market_close.strftime('%I:%M %p ET')}", None
        elif now_et > market_close:
            return True, f"Post-market tolerance window (cleanup allowed)", market_close
        else:
            return True, f"Market OPEN (closes at {market_close.strftime('%I:%M %p ET')})", market_close
    
    except Exception as e:
        # Fallback to simple time check if market calendar fails
        et_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(et_tz)
        
        # Check if weekend
        if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
            return False, "Weekend - Market closed", None
        
        # Check time (9:30 AM - 4:00 PM ET)
        market_time = now_et.time()
        market_open_time = time(9, 30)
        market_close_time = time(16, 0)
        
        if market_open_time <= market_time <= market_close_time:
            return True, "Market OPEN (simple check)", None
        else:
            return False, f"Outside market hours: {market_time.strftime('%I:%M %p ET')}", None


def get_optimal_execution_times():
    """
    Return optimal execution times for different trading operations.
    
    Returns:
        Dict with operation names and their ideal execution times (ET)
    """
    return {
        'pre_market_scan': {
            'time': '07:30',
            'description': 'Scan for gap-up candidates before market open',
            'timezone': 'US/Eastern',
            'run_on': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        },
        'market_open_entry': {
            'time': '09:35',
            'description': 'Enter positions 5 minutes after market open (avoid volatility)',
            'timezone': 'US/Eastern',
            'run_on': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        },
        'mid_day_review': {
            'time': '12:00',
            'description': 'Review positions and check for exit signals',
            'timezone': 'US/Eastern',
            'run_on': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        },
        'market_close_exit': {
            'time': '15:45',
            'description': 'Check positions 15 minutes before close',
            'timezone': 'US/Eastern',
            'run_on': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        },
        'end_of_day_cleanup': {
            'time': '16:15',
            'description': 'Generate reports and clean up memory',
            'timezone': 'US/Eastern',
            'run_on': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        },
        'weekly_report': {
            'time': '17:00',
            'description': 'Generate weekly performance report',
            'timezone': 'US/Eastern',
            'run_on': ['Friday']
        }
    }


def should_execute_now(operation_name):
    """
    Check if a scheduled operation should execute now.
    
    Args:
        operation_name: Name of operation from get_optimal_execution_times()
    
    Returns:
        Tuple of (should_run: bool, reason: str)
    """
    operations = get_optimal_execution_times()
    
    if operation_name not in operations:
        return False, f"Unknown operation: {operation_name}"
    
    op = operations[operation_name]
    et_tz = pytz.timezone('US/Eastern')
    now_et = datetime.now(et_tz)
    
    # Check if today is a valid run day
    day_name = now_et.strftime('%A')
    if day_name not in op['run_on']:
        return False, f"Not scheduled for {day_name}s"
    
    # For market-dependent operations, check market status
    if operation_name in ['market_open_entry', 'mid_day_review', 'market_close_exit']:
        is_open, status, _ = is_market_open()
        if not is_open:
            return False, f"Market not open: {status}"
    
    # For cleanup operations, allow post-market window
    if operation_name == 'end_of_day_cleanup':
        is_open, status, _ = is_market_open(tolerance_minutes=30)
        if not is_open:
            return False, f"Outside cleanup window: {status}"
    
    return True, f"Ready to execute: {op['description']}"


if __name__ == '__main__':
    import sys
    
    # Test current market status
    is_open, status, next_open = is_market_open()
    print(f"\n{'='*60}")
    print(f"Market Hours Validator")
    print(f"{'='*60}")
    print(f"Status: {status}")
    print(f"Market Open: {'YES ✓' if is_open else 'NO ✗'}")
    if next_open:
        print(f"Next Open: {next_open}")
    
    # Show optimal execution times
    print(f"\n{'='*60}")
    print(f"Optimal Execution Schedule")
    print(f"{'='*60}")
    
    times = get_optimal_execution_times()
    for op_name, details in times.items():
        print(f"\n{op_name.upper().replace('_', ' ')}")
        print(f"  Time: {details['time']} {details['timezone']}")
        print(f"  Days: {', '.join(details['run_on'])}")
        print(f"  Purpose: {details['description']}")
        
        # Check if would run now
        should_run, reason = should_execute_now(op_name)
        print(f"  Status: {'✓ WOULD RUN' if should_run else '✗ SKIP'} - {reason}")
    
    # If operation name provided, check just that one
    if len(sys.argv) > 1:
        op_name = sys.argv[1]
        should_run, reason = should_execute_now(op_name)
        print(f"\n{'='*60}")
        print(f"Check: {op_name}")
        print(f"Result: {should_run}")
        print(f"Reason: {reason}")
        print(f"{'='*60}\n")
        sys.exit(0 if should_run else 1)
