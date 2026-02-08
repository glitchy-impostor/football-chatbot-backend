# Phase 5: Frontend — Implementation Plan

## Overview

Phase 5 implements a React + Vite + Tailwind CSS frontend for the football analytics chatbot.

## Tech Stack

- **React 18** - UI framework
- **Vite** - Build tool with fast HMR
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Data visualization
- **Lucide React** - Icons

## Features

### Core Features
- Real-time chat interface
- Message history
- Loading states
- Error handling

### UI/UX Features
- 🌙 Dark mode (system preference + toggle)
- 🏈 NFL team colors and theming
- 📱 Mobile responsive design
- ⚡ Quick action buttons

### Data Visualization
- EPA comparison charts (pass vs run)
- 4th down decision visualization
- Team profile summaries

### Personalization
- Favorite team selection
- Season selection
- Persistent settings (localStorage)

## Directory Structure

```
frontend/
├── public/
│   └── football.svg          # Favicon
├── src/
│   ├── components/
│   │   ├── ChatWindow.jsx    # Main chat interface
│   │   ├── Message.jsx       # Chat message display
│   │   ├── EPAChart.jsx      # EPA visualization
│   │   ├── QuickActions.jsx  # Quick action buttons
│   │   ├── Sidebar.jsx       # Settings sidebar
│   │   └── SettingsPanel.jsx # Settings modal
│   ├── hooks/
│   │   └── useApi.js         # API communication
│   ├── utils/
│   │   └── teams.js          # NFL team data
│   ├── App.jsx               # Main app
│   ├── main.jsx              # Entry point
│   └── index.css             # Tailwind + custom styles
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## API Integration

The frontend communicates with the backend via:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Check API status |
| `/api/chat` | POST | Send chat messages |
| `/api/teams/{team}/profile` | GET | Get team profile |
| `/api/models` | GET | List available LLM models |

## Styling

### Theme Colors
- Primary: Blue (#3B82F6)
- Success: Green (#10B981)
- Warning: Yellow (#EAB308)
- Error: Red (#EF4444)

### NFL Team Colors
All 32 teams with primary and secondary colors defined in both:
- `tailwind.config.js`
- `src/utils/teams.js`

## Setup Commands

```bash
# Install dependencies
cd frontend
npm install

# Development server (port 3000)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

## Configuration

### API Proxy (vite.config.js)
```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, '')
    }
  }
}
```

### Dark Mode (tailwind.config.js)
```javascript
darkMode: 'class'  // Toggle via class on <html>
```

## Component Details

### ChatWindow
- Input field with send button
- Message list with auto-scroll
- Welcome screen with quick actions
- Loading indicator

### Message
- User vs assistant styling
- Markdown-like formatting
- EPA chart integration
- Raw data toggle
- Timestamp and metadata

### EPAChart
- Horizontal bar chart
- Pass vs Run comparison
- Color-coded recommendation
- Responsive sizing

### Sidebar/SettingsPanel
- Team selection dropdown
- Season selection
- API status display
- Quick team buttons

## State Management

Uses React's built-in hooks:
- `useState` for local state
- `useEffect` for side effects
- `useCallback` for memoized functions
- Custom hooks for API calls

Persistence via `localStorage`:
- Dark mode preference
- User context (favorite team, season)
