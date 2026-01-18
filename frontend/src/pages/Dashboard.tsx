import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Card, Statistic, Timeline, Button, Space, Spin, Alert, Select, Switch, message } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  ClusterOutlined,
  DatabaseOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { statsAPI, servicesAPI } from '@/api/client';
import { useAppStore } from '@/store';
import { useServiceContext } from '@/contexts/ServiceContext';
import { Typography } from 'antd';

const { Text } = Typography;

const Dashboard = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { refreshIntervals } = useAppStore();
  const { selectedService } = useServiceContext();
  const [trendDays, setTrendDays] = useState(7);
  const [timeFilter, setTimeFilter] = useState('24h');

  // Fetch data based on selected service and time filter
  const { data: stats, isLoading, error, refetch } = useQuery({
    queryKey: ['stats', selectedService, timeFilter],
    queryFn: () => selectedService ? statsAPI.get(selectedService, timeFilter) : Promise.resolve(null),
    enabled: !!selectedService,
    refetchInterval: refreshIntervals.dashboard,
  });

  // Fetch trend data for selected service only
  const { data: trendData = [], isLoading: trendsLoading } = useQuery({
    queryKey: ['trends', trendDays, selectedService],
    queryFn: () => selectedService ? statsAPI.getTrends(trendDays, selectedService) : Promise.resolve([]),
    enabled: !!selectedService,
    refetchInterval: refreshIntervals.dashboard,
  });

  // Fetch services list to get service names
  const { data: services = [] } = useQuery({
    queryKey: ['services'],
    queryFn: () => servicesAPI.list(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Fetch current service details for log processing toggle
  const { data: currentService } = useQuery({
    queryKey: ['service', selectedService],
    queryFn: () => selectedService ? servicesAPI.get(selectedService) : Promise.resolve(null),
    enabled: !!selectedService,
    refetchInterval: 10000, // 10 seconds
  });

  // Mutation for log processing toggle (service-level)
  const toggleLogProcessingMutation = useMutation({
    mutationFn: (enabled: boolean) => servicesAPI.toggleLogProcessing(selectedService!, enabled),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['service', selectedService] });
      message.success(data.message);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to toggle log processing');
    },
  });

  if (error) {
    return (
      <Alert
        message="Error Loading Dashboard"
        description="Failed to load dashboard statistics. Please try again."
        type="error"
        showIcon
        action={
          <Button size="small" onClick={() => refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div style={{ maxWidth: '100%', overflowX: 'hidden' }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>Dashboard</h1>
        <Space size="large">
          {selectedService && (
            <>
              <Space>
                <span style={{ fontSize: 14, color: '#8c8c8c' }}>Time Range:</span>
                <Select
                  value={timeFilter}
                  onChange={setTimeFilter}
                  style={{ width: 140 }}
                  options={[
                    { value: '5m', label: '5 minutes' },
                    { value: '10m', label: '10 minutes' },
                    { value: '30m', label: '30 minutes' },
                    { value: '1h', label: '1 hour' },
                    { value: '6h', label: '6 hours' },
                    { value: '24h', label: '24 hours' },
                    { value: '7d', label: '7 days' },
                    { value: '30d', label: '30 days' },
                  ]}
                />
              </Space>
              <Space>
                <span style={{ fontSize: 14, color: '#8c8c8c' }}>Processing:</span>
                <Switch
                  checked={currentService?.log_processing_enabled ?? true}
                  onChange={(checked) => toggleLogProcessingMutation.mutate(checked)}
                  checkedChildren={<PlayCircleOutlined />}
                  unCheckedChildren={<PauseCircleOutlined />}
                  loading={toggleLogProcessingMutation.isPending}
                />
              </Space>
            </>
          )}
          <Button icon={<ReloadOutlined />} onClick={() => refetch()} disabled={!selectedService}>
            Refresh
          </Button>
        </Space>
      </div>

      {!selectedService ? (
        // Show service selection prompt when no service is selected
        <div style={{ textAlign: 'center', padding: '80px 20px' }}>
          <DatabaseOutlined style={{ fontSize: 64, color: '#d9d9d9', marginBottom: 16 }} />
          <h2 style={{ color: '#8c8c8c', marginBottom: 8 }}>Select a Service</h2>
          <p style={{ color: '#bfbfbf', fontSize: 16, marginBottom: 24 }}>
            Choose a service from the dropdown in the header to view its dashboard metrics and exception data.
          </p>
        </div>
      ) : (
        <Spin spinning={isLoading}>
        
        {/* Statistics Cards */}
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Active Exceptions"
                value={stats?.total_clusters || 0}
                prefix={<ExclamationCircleOutlined />}
                suffix={
                  stats?.trends?.clusters_change ? (
                    <span style={{ fontSize: 14, color: stats.trends.clusters_change > 0 ? '#cf1322' : '#3f8600' }}>
                      {stats.trends.clusters_change > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                      {Math.abs(stats.trends.clusters_change)}%
                    </span>
                  ) : null
                }
              />
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={6}>
            <Card
              hoverable
              onClick={() => {
                const params = selectedService ? `?service_id=${selectedService}` : '';
                navigate(`/clusters${params}`);
              }}
              style={{ cursor: 'pointer' }}
            >
              <Statistic
                title="Total Clusters"
                value={stats?.active_exceptions || 0}
                prefix={<ClusterOutlined />}
                valueStyle={{ color: stats?.active_exceptions && stats.active_exceptions > 10 ? '#cf1322' : '#3f8600' }}
              />
              <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 8 }}>Active only</div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="RCA Generated"
                value={stats?.rca_generated || 0}
                prefix={<CheckCircleOutlined />}
                valueStyle={{ color: '#3f8600' }}
              />
              <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 8 }}>Last 7 days</div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="System Health"
                value={stats?.system_health || 'healthy'}
                valueStyle={{
                  color: stats?.system_health === 'healthy' ? '#3f8600' : stats?.system_health === 'degraded' ? '#faad14' : '#cf1322',
                  fontSize: 20,
                  textTransform: 'capitalize',
                }}
              />
              <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 8 }}>
                {stats?.logs_processed?.toLocaleString() || 0} logs processed
              </div>
            </Card>
          </Col>
        </Row>

        {/* Exception Trends Chart */}
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24}>
              <Card 
                title={`Exception Trends - ${services.find(s => s.id === selectedService)?.name || 'Service'}`}
                bordered={false}
                extra={
                  <Space>
                    <span style={{ fontSize: 14, color: '#8c8c8c' }}>Show last:</span>
                    <Select
                      value={trendDays}
                      onChange={setTrendDays}
                      style={{ width: 120 }}
                      options={[
                        { label: '7 days', value: 7 },
                        { label: '14 days', value: 14 },
                        { label: '21 days', value: 21 },
                        { label: '30 days', value: 30 },
                      ]}
                    />
                  </Space>
                }
              >
                {trendsLoading ? (
                  <div style={{ textAlign: 'center', padding: 48 }}>
                    <Spin />
                  </div>
                ) : trendData.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 48 }}>
                    <ExclamationCircleOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
                    <Text type="secondary" style={{ display: 'block' }}>
                      No trend data available for the selected time period
                    </Text>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="date" 
                        tick={{ fontSize: 12 }}
                        angle={-45}
                        textAnchor="end"
                        height={60}
                      />
                      <YAxis 
                        tick={{ fontSize: 12 }}
                        allowDecimals={false}
                      />
                      <RechartsTooltip 
                        contentStyle={{ backgroundColor: '#fff', border: '1px solid #d9d9d9' }}
                        labelStyle={{ fontWeight: 'bold' }}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="exceptions" 
                        stroke="#2563eb" 
                        strokeWidth={2}
                        dot={{ fill: '#2563eb', r: 4 }}
                        activeDot={{ r: 6 }}
                        name="Exceptions"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </Card>
            </Col>
          </Row>



        {/* Recent Activity */}
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <Card title="Recent Activity" bordered={false}>
              <Timeline
                items={[
                  {
                    color: 'red',
                    children: (
                      <>
                        <p style={{ margin: 0, fontWeight: 500 }}>NullPointerException detected</p>
                        <p style={{ margin: 0, fontSize: 12, color: '#8c8c8c' }}>5 minutes ago • user-service</p>
                      </>
                    ),
                  },
                  {
                    color: 'green',
                    children: (
                      <>
                        <p style={{ margin: 0, fontWeight: 500 }}>RCA generated for cluster_abc123</p>
                        <p style={{ margin: 0, fontSize: 12, color: '#8c8c8c' }}>10 minutes ago</p>
                      </>
                    ),
                  },
                  {
                    color: 'blue',
                    children: (
                      <>
                        <p style={{ margin: 0, fontWeight: 500 }}>Task completed: fetch_and_process_logs</p>
                        <p style={{ margin: 0, fontSize: 12, color: '#8c8c8c' }}>30 minutes ago</p>
                      </>
                    ),
                  },
                  {
                    color: 'gray',
                    children: (
                      <>
                        <p style={{ margin: 0, fontWeight: 500 }}>SQLException cluster resolved</p>
                        <p style={{ margin: 0, fontSize: 12, color: '#8c8c8c' }}>1 hour ago • database-service</p>
                      </>
                    ),
                  },
                ]}
              />
            </Card>
          </Col>

        </Row>
        </Spin>
      )}
    </div>
  );
};

export default Dashboard;
