import React, { createContext, useContext, useState, ReactNode } from 'react';

interface ServiceContextType {
  selectedService: string | undefined;
  setSelectedService: (serviceId: string | undefined) => void;
  timeFilter: '5m' | '10m' | '30m' | '1h' | '6h' | '24h' | '7d' | '30d';
  setTimeFilter: (filter: '5m' | '10m' | '30m' | '1h' | '6h' | '24h' | '7d' | '30d') => void;
}

const ServiceContext = createContext<ServiceContextType | undefined>(undefined);

export const useServiceContext = () => {
  const context = useContext(ServiceContext);
  if (!context) {
    throw new Error('useServiceContext must be used within a ServiceProvider');
  }
  return context;
};

interface ServiceProviderProps {
  children: ReactNode;
}

export const ServiceProvider: React.FC<ServiceProviderProps> = ({ children }) => {
  const [selectedService, setSelectedService] = useState<string | undefined>(undefined);
  const [timeFilter, setTimeFilter] = useState<'5m' | '10m' | '30m' | '1h' | '6h' | '24h' | '7d' | '30d'>('24h');

  return (
    <ServiceContext.Provider
      value={{
        selectedService,
        setSelectedService,
        timeFilter,
        setTimeFilter,
      }}
    >
      {children}
    </ServiceContext.Provider>
  );
};
