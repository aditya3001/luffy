import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from 'antd';
import AppLayout from './components/Layout/AppLayout';
import Dashboard from './pages/Dashboard';
import Clusters from './pages/Clusters';
import ClusterDetail from './pages/ClusterDetail';
import RCAView from './pages/RCAView';
import TaskManagement from './pages/TaskManagement';
import Settings from './pages/Settings';
import { ServiceProvider } from './contexts/ServiceContext';

function App() {
  return (
    <ServiceProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="clusters" element={<Clusters />} />
            <Route path="clusters/:clusterId" element={<ClusterDetail />} />
            <Route path="rca/:clusterId" element={<RCAView />} />
            <Route path="tasks" element={<TaskManagement />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ServiceProvider>
  );
}

export default App;
