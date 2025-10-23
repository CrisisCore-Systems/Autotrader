# Alert System Dashboard Components

React components for the Alert System MVP.

## Components

### RuleBuilder

A form component for creating and editing alert rules.

**Features:**
- Metric selection (GemScore, Confidence, Liquidity, etc.)
- Operator selection (≥, ≤, =, etc.)
- Threshold configuration
- Severity levels with visual indicators
- Channel selection (Telegram, Slack, Email, Webhook)
- Suppression duration configuration
- Tag management

**Usage:**
```tsx
import { RuleBuilder } from './components/RuleBuilder';

<RuleBuilder
  onSave={(rule) => {
    // Handle rule creation/update
    console.log('Rule saved:', rule);
  }}
  onCancel={() => {
    // Handle cancel action
    console.log('Cancelled');
  }}
  initialRule={existingRule}  // Optional, for editing
/>
```

---

### AlertsInbox

An inbox component for viewing and managing triggered alerts.

**Features:**
- Real-time alert list with auto-refresh
- Filter by status (pending, acknowledged, snoozed, resolved)
- Filter by severity (info, warning, high, critical)
- Acknowledge alerts with one click
- Snooze alerts for 1 hour or 24 hours
- Label management (add/remove labels)
- Provenance links to data sources
- Expandable alert details
- Metadata viewer

**Usage:**
```tsx
import { AlertsInbox } from './components/AlertsInbox';

<AlertsInbox
  apiBaseUrl="http://localhost:8001/api"  // Optional, defaults to localhost
/>
```

---

### AlertAnalytics

A dashboard component showing alert performance metrics.

**Features:**
- Key metrics cards (Total Alerts, Average Delivery, Acknowledgement Rate, Dedupe Rate)
- Alerts by severity visualization
- Top alert rules leaderboard
- Performance indicators
- Auto-refresh every minute

**Usage:**
```tsx
import { AlertAnalytics } from './components/AlertAnalytics';

<AlertAnalytics
  apiBaseUrl="http://localhost:8001/api"  // Optional, defaults to localhost
/>
```

---

## Installation

1. Install dependencies:
```bash
cd dashboard
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Start the backend API:
```bash
cd ..
uvicorn src.api.dashboard_api:app --host 0.0.0.0 --port 8001
```

---

## Component Architecture

```
┌─────────────────────────────────────┐
│         Alert System UI             │
├─────────────────────────────────────┤
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │ RuleBuilder  │  │ AlertsInbox │ │
│  │              │  │             │ │
│  │ - Create     │  │ - List      │ │
│  │ - Edit       │  │ - ACK       │ │
│  │ - Validate   │  │ - Snooze    │ │
│  └──────────────┘  │ - Labels    │ │
│                    └─────────────┘ │
│                                     │
│  ┌────────────────────────────────┐ │
│  │      AlertAnalytics            │ │
│  │                                │ │
│  │ - Metrics Cards                │ │
│  │ - Severity Chart               │ │
│  │ - Top Rules                    │ │
│  │ - Performance                  │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
              │
              ▼
    ┌──────────────────┐
    │  Backend API     │
    │  (FastAPI)       │
    │                  │
    │ - CRUD           │
    │ - Inbox          │
    │ - Analytics      │
    └──────────────────┘
              │
              ▼
    ┌──────────────────┐
    │  SQLite DB       │
    │                  │
    │ - alert_rules    │
    │ - alerts_inbox   │
    │ - delivery_...   │
    └──────────────────┘
```

---

## Styling

All components come with their own CSS files. The styling uses:
- Modern, clean design
- Responsive grid layouts
- Color-coded severity levels
- Smooth transitions and hover effects
- Accessible color contrast

Severity colors:
- **Info**: Blue (#2196F3)
- **Warning**: Orange (#FF9800)
- **High**: Deep Orange (#FF5722)
- **Critical**: Red (#F44336)

---

## API Integration

Components communicate with the backend via REST API:

### RuleBuilder
- `POST /api/alerts/rules` - Create rule
- `PUT /api/alerts/rules/{id}` - Update rule

### AlertsInbox
- `GET /api/alerts/inbox` - List alerts
- `POST /api/alerts/inbox/{id}/acknowledge` - ACK alert
- `POST /api/alerts/inbox/{id}/snooze` - Snooze alert
- `PUT /api/alerts/inbox/{id}/labels` - Update labels

### AlertAnalytics
- `GET /api/alerts/analytics/performance` - Get metrics

---

## Development

### Running Tests

The backend has comprehensive test coverage:

```bash
# Run all alert tests
pytest tests/test_alert*.py tests/test_notification*.py -v

# Run specific test file
pytest tests/test_alert_crud_api.py -v
```

### Type Checking

Components are written in TypeScript with proper type definitions.

### Code Structure

```
dashboard/src/components/
├── RuleBuilder.tsx
├── RuleBuilder.css
├── AlertsInbox.tsx
├── AlertsInbox.css
├── AlertAnalytics.tsx
└── AlertAnalytics.css
```

---

## Future Enhancements

- [ ] Real-time WebSocket updates
- [ ] Advanced query builder for complex conditions
- [ ] Alert templates
- [ ] Bulk actions in inbox
- [ ] Export analytics to CSV/PDF
- [ ] Dark mode support
- [ ] Mobile-responsive improvements
