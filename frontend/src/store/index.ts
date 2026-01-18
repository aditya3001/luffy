import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { LogSource } from '@/types';

interface AppState {
  // Theme
  theme: 'light' | 'dark';
  setTheme: (theme: 'light' | 'dark') => void;

  // Active Log Source
  activeLogSource: string | null;
  setActiveLogSource: (sourceId: string) => void;

  // Sidebar
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;

  // Filters
  clusterFilters: {
    search: string;
    severity: string[];
    status: string[];
    services: string[];
  };
  setClusterFilters: (filters: Partial<AppState['clusterFilters']>) => void;
  resetClusterFilters: () => void;

  // Refresh intervals
  refreshIntervals: {
    dashboard: number;
    clusters: number;
    tasks: number;
  };
  setRefreshInterval: (key: keyof AppState['refreshIntervals'], value: number) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Theme
      theme: 'light',
      setTheme: (theme) => set({ theme }),

      // Active Log Source
      activeLogSource: null,
      setActiveLogSource: (sourceId) => set({ activeLogSource: sourceId }),

      // Sidebar
      sidebarCollapsed: false,
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      // Filters
      clusterFilters: {
        search: '',
        severity: [],
        status: [],
        services: [],
      },
      setClusterFilters: (filters) =>
        set((state) => ({
          clusterFilters: { ...state.clusterFilters, ...filters },
        })),
      resetClusterFilters: () =>
        set({
          clusterFilters: {
            search: '',
            severity: [],
            status: [],
            services: [],
          },
        }),

      // Refresh intervals (in milliseconds)
      refreshIntervals: {
        dashboard: 30000, // 30 seconds
        clusters: 60000, // 60 seconds
        tasks: 10000, // 10 seconds
      },
      setRefreshInterval: (key, value) =>
        set((state) => ({
          refreshIntervals: { ...state.refreshIntervals, [key]: value },
        })),
    }),
    {
      name: 'luffy-app-storage',
      partialize: (state) => ({
        theme: state.theme,
        activeLogSource: state.activeLogSource,
        sidebarCollapsed: state.sidebarCollapsed,
        refreshIntervals: state.refreshIntervals,
      }),
    }
  )
);
