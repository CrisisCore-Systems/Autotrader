# UI/UX Enhancement Quick Reference

**Quick guide for using the enhanced VoidBloom Dashboard UI components**

---

## 🚀 Quick Start

### 1. Search & Filter Tokens

```tsx
import { SearchBar, FilterBar } from './components/SearchBar';

<SearchBar onSearch={setSearchQuery} placeholder="Search tokens..." />
<FilterBar options={filterOptions} selected={filterBy} onSelect={setFilterBy} />
```

### 2. Show Toast Notifications

```tsx
import { useToast } from './components/Toast';

const { showToast } = useToast();

// Success
showToast('Scan complete!', 'success');

// Error
showToast('Failed to load data', 'error');

// Warning
showToast('Low confidence score', 'warning');

// Info
showToast('Processing...', 'info', 2000);
```

### 3. Display Empty States

```tsx
import { EmptyState } from './components/EmptyState';

<EmptyState
  title="No Tokens Found"
  description="Try adjusting your search criteria."
  icon="🔍"
  actionLabel="Reset Filters"
  onAction={resetFilters}
/>
```

---

## 🎨 CSS Variables

### Colors
```css
var(--primary-gradient)  /* Main gradient */
var(--success-color)     /* #10b981 */
var(--warning-color)     /* #f59e0b */
var(--error-color)       /* #ef4444 */
var(--accent-color)      /* #8b5cf6 */
```

### Glassmorphism
```css
var(--glass-bg)          /* Background */
var(--glass-border)      /* Border color */
var(--glass-shadow)      /* Shadow */
```

### Transitions
```css
var(--transition-smooth) /* Standard transition */
var(--transition-bounce) /* Bouncy effect */
```

---

## 🎭 Utility Classes

```css
.fade-in          /* Fade in animation */
.slide-in-left    /* Slide from left */
.slide-in-right   /* Slide from right */
.loading-skeleton /* Shimmer effect */
```

---

## 📱 Responsive Breakpoints

```css
/* Mobile */
@media (max-width: 640px) { }

/* Tablet */
@media (max-width: 960px) { }

/* Desktop */
@media (min-width: 961px) { }
```

---

## 🎯 Common Patterns

### Glassmorphic Card
```css
.my-card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 1rem;
  backdrop-filter: blur(20px);
  box-shadow: var(--glass-shadow);
  transition: var(--transition-smooth);
}
```

### Hover Effect
```css
.my-element:hover {
  transform: translateY(-4px);
  border-color: rgba(139, 92, 246, 0.6);
  box-shadow: 0 8px 24px rgba(139, 92, 246, 0.3);
}
```

### Gradient Text
```css
.my-heading {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

---

## 🔧 Component Props

### SearchBar
```tsx
interface SearchBarProps {
  onSearch: (query: string) => void;
  placeholder?: string;
}
```

### FilterBar
```tsx
interface FilterBarProps {
  options: FilterOption[];
  selected: string;
  onSelect: (value: string) => void;
}
```

### Toast
```tsx
showToast(
  message: string,
  type: 'success' | 'error' | 'warning' | 'info',
  duration?: number  // default 4000ms
)
```

### EmptyState
```tsx
interface EmptyStateProps {
  title: string;
  description: string;
  icon?: string;
  actionLabel?: string;
  onAction?: () => void;
}
```

---

## 🎨 Animation Timings

| Element | Duration | Easing |
|---------|----------|--------|
| Hover | 0.3s | cubic-bezier(0.4, 0, 0.2, 1) |
| Page load | 0.6-0.8s | ease-out |
| Toast | 0.4s | cubic-bezier(0.68, -0.55, 0.265, 1.55) |
| Spinner | 1.5-2s | infinite |

---

## 📦 File Locations

```
dashboard/src/
├── components/
│   ├── SearchBar.tsx & .css
│   ├── Toast.tsx & .css
│   ├── EmptyState.tsx & .css
│   └── LoadingSpinner.css
├── styles.css (main styles)
└── App.tsx (integration)
```

---

## ⚡ Performance Tips

1. Use `useMemo` for filtered lists
2. Debounce search (300ms default)
3. Limit toast notifications
4. Use CSS transforms (GPU-accelerated)
5. Lazy load heavy components

---

## 🎯 Best Practices

✅ **DO**:
- Use CSS variables for consistency
- Apply transitions to interactive elements
- Provide visual feedback on actions
- Support keyboard navigation
- Test on mobile devices

❌ **DON'T**:
- Overuse animations
- Block user interactions during animations
- Ignore accessibility features
- Use inline styles
- Hardcode color values

---

**For detailed documentation, see**: `docs/UI_UX_ENHANCEMENT_GUIDE.md`
