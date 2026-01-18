# Luffy Frontend - AI-Powered Log Observability Platform

Modern React-based web UI for the Luffy observability platform.

## 🚀 Features

- **Dashboard** - System statistics, exception trends, and recent activity
- **Exception Clusters** - Browse, filter, and analyze exception clusters
- **Root Cause Analysis** - AI-generated RCA with recommendations
- **Task Management** - Control periodic background tasks (enable/disable/configure)
- **Log Sources** - Configure multiple log sources (OpenSearch, Elasticsearch, Loki, etc.)
- **Real-time Updates** - Auto-refresh with configurable intervals

## 🛠️ Tech Stack

- **React 18** with TypeScript
- **Ant Design** - UI component library
- **React Query** - Data fetching and caching
- **Zustand** - State management
- **React Router v6** - Routing
- **Recharts** - Data visualization
- **Vite** - Build tool
- **Axios** - HTTP client

## 📦 Installation

```bash
# Install dependencies
npm install

# or
yarn install
```

## 🏃 Running the Application

### Development Mode

```bash
npm run dev
```

The application will start on `http://localhost:3000`

### Production Build

```bash
npm run build
npm run preview
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

### API Proxy

The Vite dev server is configured to proxy `/api` requests to `http://localhost:8000`. This is configured in `vite.config.ts`.

## 📁 Project Structure

```
frontend/
├── src/
│   ├── api/              # API client and endpoints
│   │   └── client.ts     # Axios instance and API functions
│   ├── components/       # Reusable components
│   │   └── Layout/       # Layout components
│   ├── pages/            # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Clusters.tsx
│   │   ├── ClusterDetail.tsx
│   │   ├── RCAView.tsx
│   │   ├── TaskManagement.tsx
│   │   ├── LogSources.tsx
│   │   └── Settings.tsx
│   ├── store/            # Zustand store
│   │   └── index.ts
│   ├── types/            # TypeScript types
│   │   └── index.ts
│   ├── App.tsx           # Main app component
│   ├── main.tsx          # Entry point
│   └── index.css         # Global styles
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

## 🎨 Pages

### 1. Dashboard (`/dashboard`)
- System statistics cards
- Exception trends chart
- Recent activity timeline
- Quick actions

### 2. Exception Clusters (`/clusters`)
- List of all exception clusters
- Filters: severity, status, date range, services
- Search functionality
- Pagination

### 3. Cluster Detail (`/clusters/:clusterId`)
- Exception details
- Stack trace with syntax highlighting
- Sample log entries
- Generate/View RCA button

### 4. RCA View (`/rca/:clusterId`)
- Root cause explanation
- Impact analysis
- Step-by-step recommendations
- Code snippets
- Feedback form

### 5. Task Management (`/tasks`)
- 4 periodic task cards
- Enable/disable toggles
- Edit task configuration
- Task execution history

### 6. Log Sources (`/log-sources`)
- Configure multiple log sources
- Support for OpenSearch, Elasticsearch, Loki, CloudWatch, Splunk
- Test connections
- Set active source

### 7. Settings (`/settings`)
- Theme toggle (light/dark)
- Refresh intervals
- API configuration

## 🔌 API Integration

The frontend connects to the FastAPI backend at `http://localhost:8000/api/v1`.

### Key Endpoints

```typescript
// Clusters
GET    /api/v1/clusters
GET    /api/v1/clusters/{id}

// RCA
GET    /api/v1/rca/{cluster_id}
POST   /api/v1/rca/generate
POST   /api/v1/feedback

// Tasks
GET    /api/v1/tasks
POST   /api/v1/tasks/{name}/enable
POST   /api/v1/tasks/{name}/disable
PUT    /api/v1/tasks/{name}

// Stats
GET    /api/v1/stats

// Log Sources (Extended)
GET    /api/v1/log-sources
POST   /api/v1/log-sources
PUT    /api/v1/log-sources/{id}
DELETE /api/v1/log-sources/{id}
POST   /api/v1/log-sources/{id}/test
```

## 🎯 Key Features

### Multi-System Log Source Configuration

The Log Sources page allows you to:
- Add multiple log sources (OpenSearch, Elasticsearch, Loki, etc.)
- Configure connection details (URL, credentials, index patterns)
- Test connections
- Set active log source
- Enable/disable sources

### Task Management

Control periodic background tasks:
- **fetch_and_process_logs** - Every 30 minutes
- **generate_rca_for_clusters** - Every 15 minutes
- **index_code_repository** - Daily at 2 AM
- **cleanup_old_data** - Weekly on Sunday at 3 AM

Each task can be:
- Enabled/disabled via toggle
- Configured (change intervals)
- Reset to defaults

### Real-time Updates

Configurable auto-refresh intervals:
- Dashboard: 30 seconds
- Clusters: 60 seconds
- Tasks: 10 seconds

## 🚀 Deployment

### Docker

```dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Build Command

```bash
docker build -t luffy-frontend .
docker run -p 80:80 luffy-frontend
```

## 📝 Development Notes

### Adding a New Page

1. Create page component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add menu item in `src/components/Layout/AppLayout.tsx`
4. Create API functions in `src/api/client.ts` if needed
5. Add types in `src/types/index.ts` if needed

### State Management

- **React Query** - Server state (API data)
- **Zustand** - Client state (theme, filters, UI state)

### Styling

- Uses Ant Design components
- Custom styles in component files
- Global styles in `index.css`
- Theme configured in `main.tsx`

## 🐛 Troubleshooting

### API Connection Issues

1. Ensure backend is running on `http://localhost:8000`
2. Check CORS settings in backend
3. Verify proxy configuration in `vite.config.ts`

### Build Errors

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

## 📚 Resources

- [React Documentation](https://react.dev/)
- [Ant Design](https://ant.design/)
- [React Query](https://tanstack.com/query/latest)
- [Vite](https://vitejs.dev/)

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## 📄 License

MIT
